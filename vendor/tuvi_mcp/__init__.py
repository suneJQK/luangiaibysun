# -*- coding: utf-8 -*-
"""Locally vendored TuViMCP package.

The chart engine is consumed from ``vendor.tuvi_mcp._engine``. The full MCP
server layer is intentionally not imported here so the Streamlit app does
not require the external MCP server dependencies.
"""

__version__ = "0.4.1-vendored"
