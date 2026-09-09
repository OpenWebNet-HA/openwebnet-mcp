@echo off
REM Run the OpenWebNet-MCP server via stdio transport
"%~dp0.venv\Scripts\python.exe" -m openwebnet_mcp.server %*
