"""Upload file MCP tool handler."""

import base64
import os
from pathlib import Path
from typing import Any

from mcp_persistent_shell.session.manager import SessionManager


async def handle_upload_file(
    session_id: str,
    file_path: str,
    content: str,
    encoding: str,
    session_manager: SessionManager,
) -> dict[str, Any]:
    """Handle upload_file tool call."""
    shell = await session_manager.get_session(session_id)
    if not shell:
        return {"error": "Session not found or expired"}

    try:
        # Decode content
        if encoding == "base64":
            file_content = base64.b64decode(content)
        else:
            file_content = content.encode("utf-8")

        # Get absolute path relative to workspace
        cwd = await shell.get_cwd()
        if not file_path.startswith("/"):
            abs_path = os.path.join(cwd, file_path)
        else:
            abs_path = file_path

        # Create parent directory if needed
        Path(abs_path).parent.mkdir(parents=True, exist_ok=True)

        # Write file
        with open(abs_path, "wb") as f:
            f.write(file_content)

        size = len(file_content)
        return {"status": "uploaded", "path": abs_path, "size": size}

    except Exception as e:
        return {"error": f"Failed to upload file: {str(e)}"}
