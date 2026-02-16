"""Download file MCP tool handler."""

import base64
import os
from typing import Any

from mcp_persistent_shell.session.manager import SessionManager


async def handle_download_file(
    session_id: str,
    file_path: str,
    encoding: str,
    session_manager: SessionManager,
) -> dict[str, Any]:
    """Handle download_file tool call."""
    shell = await session_manager.get_session(session_id)
    if not shell:
        return {"error": "Session not found or expired"}

    try:
        # Get absolute path relative to workspace
        cwd = await shell.get_cwd()
        if not file_path.startswith("/"):
            abs_path = os.path.join(cwd, file_path)
        else:
            abs_path = file_path

        # Read file
        with open(abs_path, "rb") as f:
            file_content = f.read()

        # Encode content
        if encoding == "base64":
            content = base64.b64encode(file_content).decode("ascii")
        else:
            content = file_content.decode("utf-8")

        size = len(file_content)
        return {"content": content, "size": size, "encoding": encoding}

    except FileNotFoundError:
        return {"error": f"File not found: {file_path}"}
    except Exception as e:
        return {"error": f"Failed to download file: {str(e)}"}
