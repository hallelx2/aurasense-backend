"""
Food agent LangGraph nodes.

End-to-end flow per turn::

    intent → context → health_screen → search → recommend → confirm_or_order
                                                                  ↓
                                            place_order ← (if confirmed)
                                                  ↓
                                              record (Graphiti)

Cross-agent collaboration: ``context_node`` calls
``profile_service.get_user_context`` so allergies / dietary / cuisines
flow in from the Profile agent. The food agent never imports the
profile agent directly.

Safety: ``record_node`` is the LAST chance to bail. The recommend node
already runs the deterministic allergy filter, but record_node's job
is to write the audit episode to Graphiti so future turns see exactly
what was suggested + accepted.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.app.core.config import settings
from src.app.services.graphiti import contract
from src.app.services.mcp_service import mcp_service
from src.app.services.profile_service import profile_service

from .allergy_filter import filter_recommendations
from .schemas import IntentClassification, RecommendationList
from .state import FoodAgentState

logger = logging.getLogger(__name__)


# ============================================================ INTENT


_INTENT_SYSTEM = """
You classify a single utterance from a user who is talking to a food
recommendation agent. Pick the closest intent label.

- recommend: user wants food suggestions ("what's good for dinner?",
  "I want Thai food").
- reorder: user wants to repeat a past order ("get me what I had last
  Friday").
- followup: user is reacting to a previous recommendation list and
  wants more options or clarification ("show me cheaper ones",
  "any vegan options?").
- confirm_order: user is selecting a specific item from a previously
  shown list ("order the second one", "I'll take the pad thai"). When
  picking, return selected_index as the 1-based position the user named.
- decline: user is bailing ("never mind", "no thanks").
- off_topic: user is not talking about food at all ("what's the
  weather"). The supervisor handles routing this away.
""".strip()


def _build_intent_prompt(user_text: str, prior_recs: list[dict]) -> str:
    if not prior_recs:
        return f"User said: {user_text!r}\n\nNo prior recommendations were shown."
    bullets = "\n".join(
        f"  {i+1}. {r.get('name', '?')}" for i, r in enumerate(prior_recs[:5])
    )
    return (
        f"User said: {user_text!r}\n\n"
        f"Previous recommendations shown:\n{bullets}"
    )


async def intent_node(state: FoodAgentState, *, llm) -> FoodAgentState:
    """Classify the user's intent for this turn."""
    user_text = (state.get("transcribed_text") or state.get("user_input") or "").strip()
    if not user_text:
        state["food_intent"] = "followup"
        return state

    prior_recs: list[dict] = list(state.get("recommendations") or [])

    try:
        classifier = llm.with_structured_output(IntentClassification)
        result = await classifier.ainvoke(
            f"{_INTENT_SYSTEM}\n\n{_build_intent_prompt(user_text, prior_recs)}"
        )
        state["food_intent"] = result.intent
        if result.selected_index is not None:
            state["selected_index"] = result.selected_index
    except Exception:
        logger.exception("food_agent.intent classification failed")
        state["food_intent"] = "recommend"  # safe default

    return state


# ============================================================ CONTEXT


async def context_node(state: FoodAgentState) -> FoodAgentState:
    """Pull personalization context from the Profile agent.

    Channel #1 of cross-agent collaboration: we call
    ``profile_service.get_user_context`` (a stable interface) instead of
    reaching into the profile agent directly.
    """
    user_id = state.get("user_id")
    if not user_id:
        state["user_context"] = {}
        state["allergens"] = []
        state["dietary_restrictions"] = []
        return state

    try:
        snapshot = await profile_service.get_user_context(user_id, intent="food")
        state["user_context"] = snapshot.to_dict()
        state["allergens"] = list(snapshot.allergies)
        state["dietary_restrictions"] = list(snapshot.dietary_restrictions)
    except Exception:
        logger.exception("food_agent.context_node failed")
        state["user_context"] = {}
        state["allergens"] = []
        state["dietary_restrictions"] = []

    return state


# ============================================================ HEALTH SCREEN


async def health_screen_node(state: FoodAgentState) -> FoodAgentState:
    """Build the hard filter set from allergens + dietary restrictions.

    Currently this just normalizes the lists already populated by
    context_node — separated as a node so we can extend later (e.g.
    pull medication interactions from health_service when it ships)
    without touching the rest of the graph.
    """
    allergens = [a for a in (state.get("allergens") or []) if isinstance(a, str)]
    dietary = [
        d for d in (state.get("dietary_restrictions") or []) if isinstance(d, str)
    ]
    state["allergens"] = sorted({a.strip() for a in allergens if a.strip()})
    state["dietary_restrictions"] = sorted({d.strip() for d in dietary if d.strip()})
    return state


# ============================================================ SEARCH


async def search_node(state: FoodAgentState) -> FoodAgentState:
    """Search the (mock or real) restaurant catalog.

    The query string is built from the user utterance + cuisine hints
    pulled from their context. Allergy filtering happens AFTER the LLM
    in the recommend node — search returns candidates broadly so the
    LLM has enough material to compose a good list.
    """
    user_text = (state.get("transcribed_text") or state.get("user_input") or "").strip()

    ctx = state.get("user_context") or {}
    cuisines = ctx.get("cuisines_liked") or []
    cuisine_hint: Optional[str] = cuisines[0] if cuisines else None

    price_range = (ctx.get("profile") or {}).get("price_range")

    state["search_query"] = user_text or "food"

    try:
        results = await mcp_service.search_restaurants(
            query=user_text or "",
            cuisine=cuisine_hint,
            price_range=price_range if isinstance(price_range, str) else None,
            limit=10,
        )
        # If too narrow, broaden by dropping cuisine.
        if len(results) < 3 and cuisine_hint:
            results = await mcp_service.search_restaurants(
                query=user_text or "",
                cuisine=None,
                price_range=None,
                limit=10,
            )
    except Exception:
        logger.exception("food_agent.search_node failed")
        results = []

    state["search_results"] = results
    return state


# ============================================================ RECOMMEND


_RECOMMEND_SYSTEM = """
You are a food recommendation agent for the user described in the
context block. You will receive a list of candidate dishes from a
search.

Rules (non-negotiable):
1. NEVER include a dish that contains an allergen the user has listed.
2. Respect dietary restrictions (vegan / vegetarian / halal / kosher / etc.).
3. Recommend 3-5 items, ranked best-fit first.
4. Each recommendation must include the dish name, a 1-2 sentence
   description, the explicit ingredients list (so the safety filter can
   verify), and a one-line `why_recommended` that references the user's
   context where relevant.
5. Provide a short `summary` that acknowledges any personalization
   you applied (e.g. "I noticed you're allergic to peanuts so I
   excluded the pad thai").

If the candidates don't have enough safe options, explain in the
summary and return the safe ones you found.
""".strip()


def _format_user_context(state: FoodAgentState) -> str:
    ctx = state.get("user_context") or {}
    parts: list[str] = []
    allergens = state.get("allergens") or []
    if allergens:
        parts.append(f"Allergies: {', '.join(allergens)}")
    dietary = state.get("dietary_restrictions") or []
    if dietary:
        parts.append(f"Dietary restrictions: {', '.join(dietary)}")
    cuisines = ctx.get("cuisines_liked") or []
    if cuisines:
        parts.append(f"Cuisines liked: {', '.join(cuisines)}")
    health = ctx.get("health_conditions") or []
    if health:
        parts.append(f"Health conditions: {', '.join(health)}")
    if not parts:
        return "(No specific constraints known about the user yet.)"
    return "\n".join("- " + p for p in parts)


def _format_candidates(candidates: List[Dict[str, Any]]) -> str:
    if not candidates:
        return "(No candidates were returned by search.)"
    out: list[str] = []
    for i, c in enumerate(candidates[:10], 1):
        ingredients = ", ".join(c.get("ingredients") or [])
        out.append(
            f"{i}. {c.get('name', '?')} — {c.get('cuisine', 'unknown')} "
            f"({c.get('restaurant', '?')}). Ingredients: {ingredients}. "
            f"{c.get('description', '')}"
        )
    return "\n".join(out)


async def recommend_node(state: FoodAgentState, *, llm) -> FoodAgentState:
    """Use the LLM to compose a structured recommendation list.

    Followed immediately by the deterministic allergy filter — the LLM
    is NOT trusted as the safety boundary.
    """
    candidates = state.get("search_results") or []
    if not candidates:
        state["recommendations"] = []
        state["rejected_recommendations"] = []
        state["system_response"] = (
            "I couldn't find any matching dishes right now. "
            "Want to try a different cuisine or budget?"
        )
        return state

    user_text = (state.get("transcribed_text") or state.get("user_input") or "").strip()

    prompt = (
        f"{_RECOMMEND_SYSTEM}\n\n"
        f"User utterance: {user_text!r}\n\n"
        f"User context:\n{_format_user_context(state)}\n\n"
        f"Search candidates:\n{_format_candidates(candidates)}"
    )

    try:
        recommender = llm.with_structured_output(RecommendationList)
        out = await recommender.ainvoke(prompt)
        rec_dicts = [r.model_dump() for r in out.recommendations]
        summary = out.summary or ""
    except Exception:
        logger.exception("food_agent.recommend_node failed")
        # Fallback: surface the top 3 candidates verbatim. They still get
        # filtered for allergens below.
        rec_dicts = [
            {
                "name": c.get("name"),
                "description": c.get("description") or "",
                "cuisine": c.get("cuisine"),
                "price_range": c.get("price_range"),
                "estimated_price": c.get("estimated_price"),
                "ingredients": list(c.get("ingredients") or []),
                "why_recommended": "Top match from search.",
            }
            for c in candidates[:3]
        ]
        summary = "Here are some options based on your search:"

    # ------------------------------ Deterministic allergy post-filter
    strict = bool(getattr(settings, "STRICT_ALLERGY_FILTER", True))
    allergens = state.get("allergens") or []
    if strict and allergens:
        safe, rejected = filter_recommendations(rec_dicts, allergens)
    else:
        safe, rejected = rec_dicts, []

    state["recommendations"] = safe
    state["rejected_recommendations"] = rejected

    if not safe:
        state["system_response"] = (
            "I couldn't find any options that are safe given your allergies. "
            "Want me to broaden the search or try a different cuisine?"
        )
    else:
        lines = [summary] if summary else []
        for i, rec in enumerate(safe, 1):
            lines.append(
                f"{i}. **{rec.get('name')}** ({rec.get('cuisine', 'cuisine unknown')}) — "
                f"{rec.get('description', '')} {rec.get('why_recommended') or ''}".strip()
            )
        if rejected:
            lines.append(
                f"\n(Filtered {len(rejected)} unsafe item(s) for your allergies.)"
            )
        state["system_response"] = "\n".join(lines)

    return state


# ============================================================ CONFIRM / ORDER


async def confirm_or_order_node(state: FoodAgentState) -> FoodAgentState:
    """Branch decision after recommend.

    If the classified intent on this turn is 'confirm_order' AND the
    state has a previously-shown recommendation list, route to
    place_order. Otherwise, just emit the rec list and END.
    """
    intent = state.get("food_intent")
    has_recs = bool(state.get("recommendations"))
    if intent == "confirm_order" and has_recs:
        state["status"] = "ready"  # place_order will set the final status
        return state
    state["status"] = "ready"
    return state


def needs_order_placement(state: FoodAgentState) -> bool:
    """Conditional edge: should we route to place_order_node?"""
    return (
        state.get("food_intent") == "confirm_order"
        and bool(state.get("recommendations"))
        and isinstance(state.get("selected_index"), int)
    )


# ============================================================ PLACE ORDER


async def place_order_node(state: FoodAgentState) -> FoodAgentState:
    """Place the order with the external provider + Neo4j."""
    recs = state.get("recommendations") or []
    idx = state.get("selected_index")
    if not isinstance(idx, int) or idx < 1 or idx > len(recs):
        state["system_response"] = (
            "I couldn't tell which option you meant. "
            "Could you say the number or the dish name?"
        )
        return state

    chosen = dict(recs[idx - 1])

    try:
        provider_resp = await mcp_service.place_order(
            {
                "user_id": state.get("user_id"),
                "dish_name": chosen.get("name"),
                "restaurant": chosen.get("restaurant") or chosen.get("cuisine"),
                "estimated_price": chosen.get("estimated_price"),
            }
        )
    except Exception:
        logger.exception("food_agent.place_order_node external call failed")
        provider_resp = {
            "provider": "unknown",
            "provider_order_id": None,
            "status": "failed",
        }

    order_uid: Optional[str] = None
    try:
        order_uid = await _persist_order_to_neo4j(
            user_id=state.get("user_id"),
            chosen=chosen,
            provider_resp=provider_resp,
        )
    except Exception:
        logger.exception("food_agent.place_order_node Neo4j persist failed")

    placed = {
        "uid": order_uid,
        "provider_order_id": provider_resp.get("provider_order_id"),
        "status": provider_resp.get("status", "pending_payment"),
        "dish_name": chosen.get("name"),
        "restaurant": chosen.get("restaurant"),
    }
    state["placed_order"] = placed
    state["system_response"] = (
        f"Order placed for **{chosen.get('name')}** "
        f"at {chosen.get('restaurant', 'the restaurant')}. "
        f"Status: {placed['status']}."
    )
    state["status"] = "complete"
    return state


async def _persist_order_to_neo4j(
    *,
    user_id: Optional[str],
    chosen: Dict[str, Any],
    provider_resp: Dict[str, Any],
) -> Optional[str]:
    """Create an Order node + connect it to the User. Best-effort."""
    if not user_id:
        return None

    from src.app.core.database import run_in_thread
    from src.app.models.order import Order
    from src.app.models.user import User

    def _persist() -> Optional[str]:
        user = User.nodes.filter(uid=user_id).first()
        if not user:
            return None
        try:
            order = Order(
                restaurant_name=str(chosen.get("restaurant") or ""),
                dish_name=str(chosen.get("name") or ""),
                status=str(provider_resp.get("status", "pending_payment")),
                total_amount=float(chosen.get("estimated_price") or 0.0),
            ).save()
        except Exception:
            logger.exception("Order(...).save() failed")
            return None
        try:
            user.orders.connect(order)
        except Exception:
            logger.exception("User.orders.connect(order) failed")
        return getattr(order, "uid", None)

    return await run_in_thread(_persist)


# ============================================================ RECORD


async def record_node(state: FoodAgentState) -> FoodAgentState:
    """Write recommendation + (optional) acceptance to Graphiti.

    Two episodes per turn:
      * record_user_utterance — the post-STT message
      * record_recommendation — the structured rec list, with
        accepted=True/False/None
    """
    user_id = state.get("user_id")
    if not user_id:
        return state

    utterance = (state.get("transcribed_text") or state.get("user_input") or "").strip()
    if utterance:
        await contract.record_user_utterance(
            user_id=user_id, transcript=utterance, agent_name="food"
        )

    recs = state.get("recommendations") or []
    placed = state.get("placed_order")
    if recs:
        accepted: Optional[bool]
        if placed:
            accepted = True
        elif state.get("food_intent") == "decline":
            accepted = False
        else:
            accepted = None
        await contract.record_recommendation(
            user_id=user_id,
            agent_name="food",
            recommendation={
                "intent": state.get("food_intent"),
                "items": recs,
                "selected_index": state.get("selected_index"),
            },
            accepted=accepted,
        )

    if placed and placed.get("dish_name") and placed.get("restaurant"):
        await contract.record_visit(
            user_id=user_id,
            restaurant=str(placed["restaurant"]),
            visit_data={
                "dish_name": placed.get("dish_name"),
                "via": "food_agent.place_order",
                "status": placed.get("status"),
            },
        )

    return state
