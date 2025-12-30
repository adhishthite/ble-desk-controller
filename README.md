# BLE Standing Desk Controller

Control your IKEA Idåsen / Linak standing desk via Bluetooth Low Energy, with MCP integration for LLM tool calling.

## Features

- **BLE Scanning** - Discover nearby Bluetooth devices
- **Desk Control** - Height adjustment (up/down, absolute positioning)
- **Memory Presets** - Save and recall 4 favorite positions
- **Collision Detection** - Automatic stop when obstacles detected
- **MCP Server** - Expose desk control as LLM tools via Model Context Protocol
- **LangChain Chat Agent** - Interactive AI with streaming responses and tool visibility

## Quick Start

### Prerequisites

- **macOS** with Bluetooth (Linux support via bleak, untested)
- **Python 3.13+**
- **IKEA Idåsen** or compatible Linak desk with BLE
- **Bluetooth Permission**: Grant Terminal access in System Settings > Privacy & Security > Bluetooth

### Installation

```bash
# Clone the repo
git clone https://github.com/adhishthite/ble-desk-controller.git
cd desk-controller

# Install dependencies
uv sync

# Verify installation
desk-control --help
```

### Usage

**Scan for BLE devices:**

```bash
desk-scan
```

**Control your desk:**

```bash
desk-control              # Show current height
desk-control height       # Show height in mm
desk-control up 2         # Move up 2 inches
desk-control down 1       # Move down 1 inch
desk-control goto 1000    # Move to 1000mm
desk-control preset 1     # Go to preset 1
desk-control save 2       # Save current position to preset 2
```

**Start MCP server:**

```bash
desk-mcp
```

## MCP Integration

Add to your Claude Desktop or Claude Code config:

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "standing-desk": {
      "command": "uv",
      "args": ["run", "desk-mcp"],
      "cwd": "/path/to/bt"
    }
  }
}
```

**Claude Code** (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "standing-desk": {
      "command": "uv",
      "args": ["run", "desk-mcp"],
      "cwd": "/path/to/bt"
    }
  }
}
```

### Available MCP Tools

| Tool                        | Description                            |
| --------------------------- | -------------------------------------- |
| `get_height`                | Get current desk height (mm + inches)  |
| `move_up(inches)`           | Move up by N inches (max 10)           |
| `move_down(inches)`         | Move down by N inches (max 10)         |
| `move_to_height(height_mm)` | Move to absolute position (620-1270mm) |
| `go_to_preset(preset)`      | Move to saved position (1-4)           |
| `save_preset(preset)`       | Save current height to slot (1-4)      |
| `stop_desk`                 | Emergency stop                         |

## LangChain Chat Agent

Run an interactive AI agent that controls your desk via natural language with streaming responses:

```bash
# Copy .env.example and add your OpenAI key
cp .env.example .env
# Edit .env with your OPENAI_API_KEY

# Run the chat agent
make chat
# or: desk-chat
```

Features:
- **Streaming responses** - See tokens as they're generated
- **Tool call visibility** - Watch MCP tools execute in real-time
- **Conversation memory** - Agent remembers context within the session
- **Rich terminal UI** - Colored output with panels and formatting

Example interaction:

```
╭─────────────────────────────────────────────────────────────────╮
│ Desk Control Agent                                              │
│ 7 tools: get_height, move_up, move_down, move_to_height, ...    │
╰─────────────────────────────────────────────────────────────────╯

You: What's my current desk height?
⚡ get_height
  → {"height_mm": 750, "height_inches": 29.5}
Agent: Your desk is currently at 750mm (29.5 inches).

You: Raise it 3 inches
⚡ move_up(inches=3)
  → {"new_height_mm": 826, "message": "Moved up 3 inches"}
Agent: Done! The desk is now at 826mm (32.5 inches).

You: What was it before?
Agent: It was 750mm before I raised it.
```

## Configuration

The desk is found by name pattern matching. By default, it looks for devices containing "Desk".

To use a specific desk, modify the name in your code:

```python
from ble_controller import DeskController

desk = DeskController("Desk 3440")  # Your desk's name
await desk.connect()
```

## Troubleshooting

### "Desk not found"

1. **Check power**: Ensure desk is powered on
2. **Scan first**: Run `desk-scan` to verify the desk is visible
3. **Check name**: Your desk may have a different name (e.g., "Desk 3440")

### "Permission denied" / Python crashes

macOS requires explicit Bluetooth permission:

1. Open **System Settings** > **Privacy & Security** > **Bluetooth**
2. Add your terminal app (Terminal.app, iTerm, VS Code, etc.)
3. Restart your terminal

### Connection timeouts

- Move closer to the desk (BLE range ~10-30m)
- Ensure no other app is connected to the desk
- Try running `desk-scan` first to "wake" the BLE stack

## Project Structure

```bash
desk-controller/
├── ble_controller/          # BLE controller package
│   ├── __init__.py          # Public API exports
│   ├── controller.py        # DeskController class
│   ├── scanner.py           # BLE device scanning
│   └── cli.py               # CLI entry points
├── desk_mcp/                # MCP server package
│   ├── __init__.py
│   └── server.py            # FastMCP server
├── chat.py                  # LangChain streaming chat agent
├── .env.example             # Environment template
├── pyproject.toml           # Project config & dependencies
├── Makefile                 # Dev commands
├── README.md                # This file
├── CLAUDE.md                # Claude Code instructions
└── BLE_EXPLORATION.md       # Technical protocol reference
```

## Development

```bash
# Install dev dependencies
uv sync

# Format code
make format

# Lint code
make lint

# Run all checks
make check

# Clean build artifacts
make clean
```

## Technical Details

See [BLE_EXPLORATION.md](BLE_EXPLORATION.md) for:

- GATT service/characteristic UUIDs
- Command protocol (UP, DOWN, STOP, WAKEUP bytes)
- Height encoding formula
- Collision detection mechanism
- Precision movement control with momentum compensation

## Security Notice

The IKEA Idåsen desk BLE protocol has **no authentication**. Anyone within BLE range (~10-30 meters) can control your desk. This is a hardware/protocol limitation.

**Mitigations:**

- Use in trusted environments (home office)
- The desk has built-in collision detection for safety
- Consider physical workspace security

## License

MIT
