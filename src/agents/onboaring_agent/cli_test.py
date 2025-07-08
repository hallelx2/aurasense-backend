#!/usr/bin/env python3
"""
CLI Test Script for Onboarding Agent
Test the onboarding flow locally with text input/output
"""

import asyncio
import sys
import os
from typing import Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../"))

from src.agents.onboaring_agent.graph import run_onboarding_agent, continue_onboarding_conversation
from src.agents.onboaring_agent.state import OnboardingAgentState
from src.agents.onboaring_agent.nodes import ONBOARDING_REQUIRED_FIELDS

console = Console()

# Mock user data (simulating what would come from sign-up)
MOCK_USER_DATA = {
    "email": "john.doe@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "username": "johndoe",
    "password": "already_hashed",  # This would be hashed in real system
}

def display_welcome():
    """Display welcome message and mock user info"""
    console.print(Panel.fit(
        "[bold blue]🎯 Aurasense Onboarding Agent - CLI Test[/bold blue]\n"
        "[yellow]Testing onboarding flow with mock user data[/yellow]",
        title="Welcome"
    ))

    # Show mock user data
    table = Table(title="Mock User Data (from sign-up)")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    for key, value in MOCK_USER_DATA.items():
        if key != "password":  # Don't show password
            table.add_row(key, str(value))

    console.print(table)
    console.print()

def display_required_fields():
    """Display what fields the onboarding agent needs to collect"""
    console.print(Panel(
        "[bold yellow]Required Onboarding Fields:[/bold yellow]\n" +
        "\n".join([f"• {field.replace('_', ' ').title()}" for field in ONBOARDING_REQUIRED_FIELDS]),
        title="What We Need to Collect"
    ))
    console.print()

def display_current_progress(extracted_info: Dict[str, Any]):
    """Display current progress of onboarding"""
    table = Table(title="Current Onboarding Progress")
    table.add_column("Field", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Value", style="yellow")

    for field in ONBOARDING_REQUIRED_FIELDS:
        value = extracted_info.get(field)
        if value:
            status = "✅ Complete"
            display_value = str(value) if not isinstance(value, list) else ", ".join(value)
        else:
            status = "❌ Missing"
            display_value = "Not provided"

        table.add_row(field.replace('_', ' ').title(), status, display_value)

    console.print(table)
    console.print()

def check_completion_status(extracted_info: Dict[str, Any]) -> tuple[bool, list]:
    """Check if onboarding is complete and return missing fields"""
    missing_fields = []
    for field in ONBOARDING_REQUIRED_FIELDS:
        if not extracted_info.get(field):
            missing_fields.append(field)

    return len(missing_fields) == 0, missing_fields

async def main():
    """Main CLI test function"""
    display_welcome()
    display_required_fields()

    console.print("[bold green]Starting onboarding conversation...[/bold green]")
    console.print("[dim]Type 'quit' to exit, 'status' to see progress[/dim]\n")

    # Initialize state with mock user data
    current_state = None

    while True:
        try:
            # Get user input
            user_input = Prompt.ask("[bold blue]You")

            if user_input.lower() == 'quit':
                console.print("[yellow]Goodbye![/yellow]")
                break

            if user_input.lower() == 'status':
                if current_state:
                    display_current_progress(current_state.get("extracted_information", {}))
                else:
                    console.print("[red]No conversation started yet[/red]")
                continue

            # Process with onboarding agent
            if current_state is None:
                # First interaction - start new conversation
                current_state = await run_onboarding_agent(user_input)

                # Pre-populate with mock user data (simulating WebSocket behavior)
                extracted_info = current_state.get("extracted_information", {})
                extracted_info.update(MOCK_USER_DATA)
                current_state["extracted_information"] = extracted_info

                console.print(f"[dim]Debug: Pre-populated with mock user data[/dim]")
            else:
                # Continue existing conversation
                current_state = await continue_onboarding_conversation(current_state, user_input)

            # Display agent response
            agent_response = current_state.get("system_response", "I'm processing...")
            onboarding_status = current_state.get("onboarding_status", "unknown")

            console.print(f"[bold green]Agent:[/bold green] {agent_response}")
            console.print(f"[dim]Status: {onboarding_status}[/dim]\n")

            # Check if there's an error
            if current_state.get("error"):
                console.print(f"[red]Error: {current_state['error']}[/red]\n")

            # Check completion status
            extracted_info = current_state.get("extracted_information", {})
            is_complete, missing_fields = check_completion_status(extracted_info)

            if onboarding_status == "onboarded" or is_complete:
                console.print(Panel.fit(
                    "[bold green]🎉 Onboarding Complete![/bold green]\n"
                    "[yellow]All required information has been collected.[/yellow]",
                    title="Success"
                ))

                # Show final collected information
                display_current_progress(extracted_info)

                console.print("[bold blue]Final collected information:[/bold blue]")
                for field in ONBOARDING_REQUIRED_FIELDS:
                    value = extracted_info.get(field, "Not provided")
                    console.print(f"  • {field.replace('_', ' ').title()}: {value}")

                console.print(f"\n[green]✅ User would now be marked as onboarded (is_onboarded = True)[/green]")
                break

            elif missing_fields:
                console.print(f"[yellow]Still need: {', '.join([f.replace('_', ' ') for f in missing_fields[:3]])}{'...' if len(missing_fields) > 3 else ''}[/yellow]\n")

        except KeyboardInterrupt:
            console.print("\n[yellow]Goodbye![/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]\n")

if __name__ == "__main__":
    asyncio.run(main())
