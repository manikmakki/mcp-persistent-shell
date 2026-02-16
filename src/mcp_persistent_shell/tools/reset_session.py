"""Reset session MCP tool handler."""

from typing import Any

from mcp_persistent_shell.session.manager import SessionManager


async def handle_reset_session(session_id: str, session_manager: SessionManager) -> dict[str, Any]:
    """Handle reset_session tool call."""
    shell = await session_manager.get_session(session_id)
    if not shell:
        return {"error": "Session not found or expired"}

    await shell.reset()
    return {"status": "reset", "message": "Shell session has been reset to clean state"}
