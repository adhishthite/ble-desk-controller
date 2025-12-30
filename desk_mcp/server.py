"""
MCP Server for IKEA Standing Desk Control.

Exposes desk control as tools that LLMs can call via the Model Context Protocol.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import Context, FastMCP

from ble_controller import (
    DeskCommunicationError,
    DeskConnectionError,
    DeskController,
    DeskNotFoundError,
)

# Create MCP server
mcp = FastMCP(
    "Standing Desk Controller",
    instructions="Control your IKEA Idåsen / Linak standing desk via BLE. "
    "Tools: get_height (check position), move_up/move_down (relative movement), "
    "move_to_height (absolute positioning), go_to_preset/save_preset (memory positions 1-4), "
    "stop_desk (emergency stop).",
)


@asynccontextmanager
async def get_desk() -> AsyncIterator[DeskController]:
    """Context manager for desk connection with automatic cleanup."""
    desk = DeskController("Desk", quiet=True)
    try:
        await desk.connect()
        yield desk
    finally:
        await desk.disconnect()


@mcp.tool()
async def get_height(ctx: Context) -> str:
    """
    Get the current desk height.

    Returns the height in both millimeters and inches.
    """
    try:
        async with get_desk() as desk:
            height_mm = await desk.get_height()
            height_in = height_mm / 25.4
            return f"Current height: {height_mm}mm ({height_in:.1f} inches)"
    except DeskNotFoundError:
        return "Error: Desk not found. Is it powered on?"
    except DeskConnectionError as e:
        return f"Error: Could not connect to desk - {e}"
    except DeskCommunicationError as e:
        return f"Error: Communication failed - {e}"


@mcp.tool()
async def move_up(ctx: Context, inches: float = 1.0) -> str:
    """
    Move the desk up by the specified number of inches.

    Args:
        inches: How many inches to move up (default: 1.0)

    Returns:
        Result of the movement including final height.
    """
    if inches <= 0:
        return "Error: inches must be positive"
    if inches > 10:
        return "Error: Maximum movement is 10 inches at a time for safety"

    try:
        async with get_desk() as desk:
            start = await desk.get_height()
            final, collision = await desk.move_by_inches(inches)
            moved = (final - start) / 25.4

            if collision:
                return f'Collision detected! Stopped at {final}mm ({final / 25.4:.1f}"). Moved {moved:.1f}" before hitting obstacle.'
            return f'Moved up to {final}mm ({final / 25.4:.1f}"). Movement: {moved:.1f}"'
    except DeskNotFoundError:
        return "Error: Desk not found. Is it powered on?"
    except DeskConnectionError as e:
        return f"Error: Could not connect to desk - {e}"
    except DeskCommunicationError as e:
        return f"Error: Communication failed - {e}"


@mcp.tool()
async def move_down(ctx: Context, inches: float = 1.0) -> str:
    """
    Move the desk down by the specified number of inches.

    Args:
        inches: How many inches to move down (default: 1.0)

    Returns:
        Result of the movement including final height.
    """
    if inches <= 0:
        return "Error: inches must be positive"
    if inches > 10:
        return "Error: Maximum movement is 10 inches at a time for safety"

    try:
        async with get_desk() as desk:
            start = await desk.get_height()
            final, collision = await desk.move_by_inches(-inches)
            moved = (start - final) / 25.4

            if collision:
                return f'Collision detected! Stopped at {final}mm ({final / 25.4:.1f}"). Moved {moved:.1f}" before hitting obstacle.'
            return f'Moved down to {final}mm ({final / 25.4:.1f}"). Movement: {moved:.1f}"'
    except DeskNotFoundError:
        return "Error: Desk not found. Is it powered on?"
    except DeskConnectionError as e:
        return f"Error: Could not connect to desk - {e}"
    except DeskCommunicationError as e:
        return f"Error: Communication failed - {e}"


@mcp.tool()
async def move_to_height(ctx: Context, height_mm: int) -> str:
    """
    Move the desk to a specific height in millimeters.

    Args:
        height_mm: Target height in millimeters (valid range: 620-1270mm)

    Returns:
        Result of the movement including final height.
    """
    if height_mm < 620:
        return 'Error: Minimum height is 620mm (24.4")'
    if height_mm > 1270:
        return 'Error: Maximum height is 1270mm (50.0")'

    try:
        async with get_desk() as desk:
            final, collision = await desk.move_to_height(height_mm)

            if collision:
                return f'Collision detected! Stopped at {final}mm ({final / 25.4:.1f}"). Target was {height_mm}mm.'
            return f'Moved to {final}mm ({final / 25.4:.1f}"). Target was {height_mm}mm, error: {abs(final - height_mm)}mm'
    except DeskNotFoundError:
        return "Error: Desk not found. Is it powered on?"
    except DeskConnectionError as e:
        return f"Error: Could not connect to desk - {e}"
    except DeskCommunicationError as e:
        return f"Error: Communication failed - {e}"


@mcp.tool()
async def stop_desk(ctx: Context) -> str:
    """
    Emergency stop - immediately halt desk movement.

    Use this if the desk is moving and you need to stop it immediately.
    """
    try:
        async with get_desk() as desk:
            await desk.stop()
            height = await desk.get_height()
            return f'Desk stopped at {height}mm ({height / 25.4:.1f}")'
    except DeskNotFoundError:
        return "Error: Desk not found. Is it powered on?"
    except DeskConnectionError as e:
        return f"Error: Could not connect to desk - {e}"
    except DeskCommunicationError as e:
        return f"Error: Communication failed - {e}"


@mcp.tool()
async def go_to_preset(ctx: Context, preset: int = 1) -> str:
    """
    Move the desk to a saved memory preset position.

    The desk has 4 memory slots that can store favorite heights.
    Reading a preset triggers the desk to move to that saved position.

    Args:
        preset: Preset number 1-4 (default: 1)

    Returns:
        Final height after moving to the preset position.
    """
    if preset < 1 or preset > 4:
        return "Error: Preset must be 1, 2, 3, or 4"

    try:
        async with get_desk() as desk:
            final = await desk.go_to_preset(preset)
            return f'Moved to preset {preset}: {final}mm ({final / 25.4:.1f}")'
    except DeskNotFoundError:
        return "Error: Desk not found. Is it powered on?"
    except DeskConnectionError as e:
        return f"Error: Could not connect to desk - {e}"
    except DeskCommunicationError as e:
        return f"Error: Communication failed - {e}"
    except ValueError as e:
        return f"Error: {e}"


@mcp.tool()
async def save_preset(ctx: Context, preset: int = 1) -> str:
    """
    Save the current desk height to a memory preset.

    Stores the current height in one of the 4 memory slots.
    You can later recall this position using go_to_preset.

    Args:
        preset: Preset number 1-4 to save to (default: 1)

    Returns:
        Confirmation of the saved height.
    """
    if preset < 1 or preset > 4:
        return "Error: Preset must be 1, 2, 3, or 4"

    try:
        async with get_desk() as desk:
            height = await desk.save_preset(preset)
            return f'Saved preset {preset} at {height}mm ({height / 25.4:.1f}")'
    except DeskNotFoundError:
        return "Error: Desk not found. Is it powered on?"
    except DeskConnectionError as e:
        return f"Error: Could not connect to desk - {e}"
    except DeskCommunicationError as e:
        return f"Error: Communication failed - {e}"
    except ValueError as e:
        return f"Error: {e}"


def run_server():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    run_server()
