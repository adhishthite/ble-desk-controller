"""
MCP Server for Standing Desk Control.

This package provides a Model Context Protocol (MCP) server that exposes
desk control functionality as tools that LLMs can call.
"""

from desk_mcp.server import mcp, run_server

__all__ = ["mcp", "run_server"]
