"""Execute command MCP tool handler."""

import logging
from typing import Any

from mcp_persistent_shell.models import CommandResult
from mcp_persistent_shell.security.validator import SecurityValidator
from mcp_persistent_shell.session.manager import SessionManager


async def handle_execute_command(
    session_id: str,
    command: str,
    timeout: int,
    session_manager: SessionManager,
    security_validator: SecurityValidator,
    logger: logging.Logger,
) -> dict[str, Any]:
    """Handle execute_command tool call."""
    # Validate command security
    try:
        security_validator.validate_command(command)
    except ValueError as e:
        logger.warning(f"Command validation failed: {e}")
        return {
            "status": "error",
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Security validation failed: {str(e)}",
            "command": command,
            "execution_time": 0.0,
        }

    # Get shell process
    shell = await session_manager.get_session(session_id)
    if not shell:
        return {
            "status": "error",
            "exit_code": -1,
            "stdout": "",
            "stderr": "Session not found or expired",
            "command": command,
            "execution_time": 0.0,
        }

    # Execute command
    result = await shell.execute(command, timeout=timeout)
    return result.model_dump()
