from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status, WebSocketException
from fastapi.responses import JSONResponse
from typing import Dict, Any
import json
import requests
import uuid
from datetime import datetime
from src.app.models.user import User
from src.app.api.routes.auth import security_manager
from src.agents.onboaring_agent.graph import run_onboarding_agent, continue_onboarding_conversation
from src.agents.onboaring_agent.state import OnboardingAgentState

router = APIRouter()

# Track ongoing onboarding sessions
onboarding_sessions: Dict[str, OnboardingAgentState] = {}

async def get_current_user_from_token(
    websocket: WebSocket,
    token: str | None = None,
) -> User:
    if token is None:
        # Try to get token from query params if not passed directly
        token = websocket.query_params.get("token")

    if not token:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")

    try:
        # Verify the JWT token using the security manager
        token_data = await security_manager.verify_token(token)
        if not token_data:
            raise Exception("Invalid or expired token")
        
        # Get user ID from token payload
        user_id = token_data.get("sub")
        if not user_id:
            raise Exception("Invalid token payload")
        
        # Find user by ID
        user = User.nodes.filter(uid=user_id).first()
        if not user:
            raise Exception("User not found")
        
        return user
    except Exception as e:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason=str(e))

async def download_audio_from_url(audio_url: str) -> bytes:
    """Download audio from URL and return bytes"""
    try:
        response = requests.get(audio_url)
        response.raise_for_status()
        return response.content
    except Exception as e:
        raise Exception(f"Failed to download audio: {str(e)}")

def map_onboarding_step_to_progress(step: str, is_complete: bool) -> Dict[str, Any]:
    """Map onboarding step to progress key for frontend"""
    step_mapping = {
        "dietary_restrictions": "dietaryPreferences",
        "cuisine_preferences": "dietaryPreferences",
        "allergies": "restrictions",
        "health_conditions": "allergies",
        "voice_sample": "voiceSample",
        "cultural_background": "communityInterests",
        "general": "dietaryPreferences"  # Default fallback
    }
    return {
        "key": step_mapping.get(step, "dietaryPreferences"),
        "value": is_complete
    }

@router.websocket("/ws/onboarding")
async def onboarding_ws(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    
    try:
        # Get user from token after accepting connection
        user = await get_current_user_from_token(websocket)
        print(f"WebSocket connected for user: {user.email if user else 'None'}")
        
        if not user:
            print("No user found, closing connection")
            await websocket.send_json({
                "type": "error",
                "payload": {"message": "Authentication failed."}
            })
            await websocket.close()
            return
    except WebSocketException as e:
        print(f"Authentication error: {e.reason}")
        await websocket.send_json({
            "type": "error",
            "payload": {"message": f"Authentication failed: {e.reason}"}
        })
        await websocket.close()
        return

    try:

        # Pre-populate with existing user data from sign-up
        existing_user_data = {
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": getattr(user, "username", None),
            "phone": getattr(user, "phone", None),
            "age": getattr(user, "age", None),
            "dietary_restrictions": getattr(user, "dietary_restrictions", []),
            "cuisine_preferences": getattr(user, "cuisine_preferences", []),
            "price_range": getattr(user, "price_range", None),
            "is_tourist": getattr(user, "is_tourist", False),
        }

        # Send initial onboarding status based on existing data
        missing_fields = []
        for field in ["age", "dietary_restrictions", "cuisine_preferences", "price_range", "is_tourist"]:
            if not getattr(user, field, None):
                missing_fields.append(field)
        
        if missing_fields:
            await websocket.send_json({
                "type": "agent_message",
                "payload": {
                    "id": str(uuid.uuid4()),
                    "sender": "agent",
                    "text": f"I need a few more details to personalize your experience. Let's start with your age - how old are you?",
                    "timestamp": datetime.utcnow().isoformat()
                }
            })
        else:
            await websocket.send_json({
                "type": "agent_message",
                "payload": {
                    "id": str(uuid.uuid4()),
                    "sender": "agent",
                    "text": "Your profile looks complete! Is there anything specific you'd like to update or add?",
                    "timestamp": datetime.utcnow().isoformat()
                }
            })

        # Main loop: handle onboarding messages
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)
            msg_type = data.get("type")
            payload = data.get("payload", {})

            if msg_type == "user_audio":
                step = payload.get("step", "general")
                audio_url = payload.get("audioUrl")
                timestamp = payload.get("timestamp", datetime.utcnow().isoformat())

                try:
                    # Download audio from URL
                    audio_bytes = await download_audio_from_url(audio_url)

                    # Run onboarding agent with pre-populated data
                    if session_id in onboarding_sessions:
                        # Continue existing conversation
                        final_state = await continue_onboarding_conversation(
                            onboarding_sessions[session_id],
                            audio_bytes
                        )
                    else:
                        # Start new conversation with existing user data
                        final_state = await run_onboarding_agent(audio_bytes, existing_user_data)

                    # Store session state
                    onboarding_sessions[session_id] = final_state

                    # Get agent response
                    agent_response = final_state.get("system_response", "I'm processing your information...")
                    onboarding_status = final_state.get("onboarding_status", "pending_info")

                    # Send agent message
                    await websocket.send_json({
                        "type": "agent_message",
                        "payload": {
                            "id": str(uuid.uuid4()),
                            "sender": "agent",
                            "text": agent_response,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    })

                    # Determine if step is complete
                    is_step_complete = onboarding_status in ["ready", "onboarded"]

                    # Send onboarding progress
                    progress = map_onboarding_step_to_progress(step, is_step_complete)
                    await websocket.send_json({
                        "type": "onboarding_progress",
                        "payload": progress
                    })

                    # If onboarding is complete, update user in database
                    if onboarding_status == "onboarded":
                        # Clean up session
                        if session_id in onboarding_sessions:
                            del onboarding_sessions[session_id]

                        # Send completion message
                        await websocket.send_json({
                            "type": "agent_message",
                            "payload": {
                                "id": str(uuid.uuid4()),
                                "sender": "agent",
                                "text": f"Fantastic, {user.first_name}! Your personalization is complete. Aurasense is now tailored to your preferences and ready to provide you with amazing recommendations!",
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        })

                        # Mark all steps as complete
                        for step_key in ["dietaryPreferences", "restrictions", "allergies", "voiceSample", "communityInterests"]:
                            await websocket.send_json({
                                "type": "onboarding_progress",
                                "payload": {"key": step_key, "value": True}
                            })

                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": f"Error processing audio: {str(e)}"}
                    })

            elif msg_type == "user_message":
                step = payload.get("step", "general")
                text = payload.get("text", "")
                timestamp = payload.get("timestamp", datetime.utcnow().isoformat())

                try:
                    # Process text message with onboarding agent
                    if session_id in onboarding_sessions:
                        # Continue existing conversation with text input
                        final_state = await continue_onboarding_conversation(
                            onboarding_sessions[session_id],
                            text  # Pass text directly instead of audio_bytes
                        )
                    else:
                        # Start new conversation with text input and existing user data
                        final_state = await run_onboarding_agent(text, existing_user_data)

                    # Store session state
                    onboarding_sessions[session_id] = final_state

                    # Get agent response
                    agent_response = final_state.get("system_response", "I'm processing your information...")
                    onboarding_status = final_state.get("onboarding_status", "pending_info")

                    # Send agent message
                    await websocket.send_json({
                        "type": "agent_message",
                        "payload": {
                            "id": str(uuid.uuid4()),
                            "sender": "agent",
                            "text": agent_response,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    })

                    # Determine if step is complete
                    is_step_complete = onboarding_status in ["ready", "onboarded"]

                    # Send onboarding progress
                    progress = map_onboarding_step_to_progress(step, is_step_complete)
                    await websocket.send_json({
                        "type": "onboarding_progress",
                        "payload": progress
                    })

                    # If onboarding is complete, update user in database
                    if onboarding_status == "onboarded":
                        # Clean up session
                        if session_id in onboarding_sessions:
                            del onboarding_sessions[session_id]

                        # Send completion message
                        await websocket.send_json({
                            "type": "agent_message",
                            "payload": {
                                "id": str(uuid.uuid4()),
                                "sender": "agent",
                                "text": f"Fantastic, {user.first_name}! Your personalization is complete. Aurasense is now tailored to your preferences and ready to provide you with amazing recommendations!",
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        })

                        # Mark all steps as complete
                        for step_key in ["dietaryPreferences", "restrictions", "allergies", "voiceSample", "communityInterests"]:
                            await websocket.send_json({
                                "type": "onboarding_progress",
                                "payload": {"key": step_key, "value": True}
                            })

                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": f"Error processing text: {str(e)}"}
                    })

            else:
                # Silently ignore unknown message types instead of sending error
                print(f"Unknown message type received: {msg_type}")
                pass

    except WebSocketDisconnect:
        # Clean up session on disconnect
        if session_id in onboarding_sessions:
            del onboarding_sessions[session_id]
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "payload": {"message": str(e)}
        })
        await websocket.close()
