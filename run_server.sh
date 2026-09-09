#!/usr/bin/env bash
# Run the OpenWebNet-MCP server via stdio transport on macOS/Linux

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
exec "$DIR/.venv/bin/python" -m openwebnet_mcp.server "$@"
