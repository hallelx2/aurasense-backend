# ... existing code from auth_agent.py ...

import asyncio
from .graph import run_onboarding_agent, continue_onboarding_conversation
from .state import OnboardingAgentState

async def cli_registration():
    print("Welcome to the CLI Registration Demo!")
    state = None
    while True:
        if state is None:
            user_input = input("You: ")
            state = await run_onboarding_agent(user_input)
        else:
            print(f"Agent: {state.get('system_response', '')}")
            if state.get("authentication_status") == "authenticated" or state.get("authentication_status") == "failed":
                print("Agent: Registration complete. Thank you!")
                break
            user_input = input("You: ")
            state = await continue_onboarding_conversation(state, user_input)

if __name__ == "__main__":
    asyncio.run(cli_registration())
