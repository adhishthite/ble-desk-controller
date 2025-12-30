"""
Interactive Chat with Standing Desk Agent.

Maintains conversation history within the session for context-aware responses.
Each run starts fresh - no persistence between sessions.
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

load_dotenv()

console = Console()


def format_tool_call(name: str, args: dict) -> Text:
    """Format a tool call for display."""
    args_str = ", ".join(f"{k}={v}" for k, v in args.items()) if args else ""
    text = Text()
    text.append("⚡ ", style="yellow")
    text.append(name, style="cyan bold")
    if args_str:
        text.append(f"({args_str})", style="dim")
    return text


def format_tool_result(name: str, result: str) -> Text:
    """Format a tool result for display."""
    text = Text()
    text.append("  → ", style="dim")
    truncated = result[:100] + "..." if len(result) > 100 else result
    text.append(truncated, style="green")
    return text


async def chat():
    """Run interactive chat with streaming responses."""
    if not os.getenv("OPENAI_API_KEY"):
        console.print("[red]Error:[/] OPENAI_API_KEY not found. Create .env with your key.")
        return

    project_dir = Path(__file__).parent
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "desk-mcp"],
        cwd=str(project_dir),
    )

    console.print("[dim]Connecting to desk...[/]")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Suppress FastMCP banner
            old_stderr = sys.stderr
            sys.stderr = open(os.devnull, "w")
            try:
                await session.initialize()
            finally:
                sys.stderr.close()
                sys.stderr = old_stderr

            tools = await load_mcp_tools(session)
            tool_names = [t.name for t in tools]

            console.print()
            console.print(
                Panel(
                    "[bold]Desk Control Agent[/]\n"
                    f"[dim]{len(tools)} tools: {', '.join(tool_names)}[/]",
                    border_style="blue",
                )
            )
            console.print("[dim]Type 'quit' to exit[/]\n")

            agent = create_agent("openai:gpt-4.1-mini", tools)
            messages: list[HumanMessage | AIMessage] = []

            while True:
                try:
                    user_input = Prompt.ask("[bold green]You[/]")
                except (EOFError, KeyboardInterrupt):
                    console.print("\n[dim]Goodbye![/]")
                    break

                if not user_input.strip():
                    continue
                if user_input.strip().lower() in ("quit", "exit", "q"):
                    console.print("[dim]Goodbye![/]")
                    break

                messages.append(HumanMessage(content=user_input))

                try:
                    # Stream the response
                    console.print("[bold blue]Agent:[/] ", end="")
                    full_response = ""
                    tool_calls_shown = set()

                    with Live("", console=console, refresh_per_second=20, transient=True) as live:
                        async for event in agent.astream_events(
                            {"messages": messages}, version="v2"
                        ):
                            kind = event["event"]

                            # Tool call started
                            if kind == "on_tool_start":
                                tool_name = event.get("name", "tool")
                                tool_input = event.get("data", {}).get("input", {})
                                if tool_name not in tool_calls_shown:
                                    console.print()  # New line
                                    console.print(format_tool_call(tool_name, tool_input))
                                    tool_calls_shown.add(tool_name)

                            # Tool call ended
                            elif kind == "on_tool_end":
                                tool_name = event.get("name", "tool")
                                output = event.get("data", {}).get("output", "")
                                if output:
                                    console.print(format_tool_result(tool_name, str(output)))

                            # Streaming tokens from the model
                            elif kind == "on_chat_model_stream":
                                chunk = event.get("data", {}).get("chunk")
                                if chunk and hasattr(chunk, "content") and chunk.content:
                                    # Only show content if it's the final response (not tool calls)
                                    if not hasattr(chunk, "tool_calls") or not chunk.tool_calls:
                                        full_response += chunk.content
                                        live.update(Text(full_response))

                    # Print final response
                    if full_response:
                        console.print(full_response)
                        messages.append(AIMessage(content=full_response))
                    console.print()

                except Exception as e:
                    console.print(f"\n[red]Error:[/] {e}\n")
                    messages.pop()


def main():
    asyncio.run(chat())


if __name__ == "__main__":
    main()
