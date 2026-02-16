"""Get working directory MCP tool handler."""

from typing import Any

from mcp_persistent_shell.session.manager import SessionManager


async def handle_get_cwd(session_id: str, session_manager: SessionManager) -> dict[str, Any]:
    """Handle get_working_directory tool call."""
    shell = await session_manager.get_session(session_id)
    if not shell:
        return {"error": "Session not found or expired"}

    cwd = await shell.get_cwd()
    return {"cwd": cwd}
