# Claude Guide

## Package Management
- Use `uv` for package management
- Add packages: `uv add <package-name>`
- Sync dependencies: `uv sync`

## Running Commands
```bash
# CLI tools (after uv sync)
desk-scan              # Scan for BLE devices
desk-control           # Control desk
desk-mcp               # Start MCP server

# Or with uv run
uv run desk-scan
uv run desk-control up 2
uv run desk-mcp
```

## Development
```bash
make check    # Format + lint
make format   # Format only
make lint     # Lint only
make clean    # Remove caches
```

## Project Structure
- `ble_controller/` - BLE scanning and desk control library
- `desk_mcp/` - FastMCP server exposing desk tools for LLMs
- `BLE_EXPLORATION.md` - Technical protocol reference

## Key Files
- `ble_controller/controller.py` - DeskController class
- `ble_controller/scanner.py` - BLE device scanning
- `desk_mcp/server.py` - MCP tool definitions
