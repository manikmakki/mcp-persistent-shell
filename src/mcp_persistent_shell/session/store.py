"""Session storage for shell processes."""

import asyncio
import logging
from typing import Dict, Optional

from mcp_persistent_shell.shell.process import ShellProcess


class SessionStore:
    """In-memory storage for session → shell process mapping."""

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(__name__)
        self._sessions: Dict[str, ShellProcess] = {}
        self._lock = asyncio.Lock()

    async def create(self, session_id: str, shell_process: ShellProcess) -> None:
        """Store a new session."""
        async with self._lock:
            self._sessions[session_id] = shell_process
            self.logger.info(f"Session created: {session_id}")

    async def get(self, session_id: str) -> Optional[ShellProcess]:
        """Retrieve shell process for a session."""
        async with self._lock:
            return self._sessions.get(session_id)

    async def delete(self, session_id: str) -> bool:
        """Remove a session."""
        async with self._lock:
            if session_id in self._sessions:
                shell = self._sessions.pop(session_id)
                await shell.terminate()
                self.logger.info(f"Session deleted: {session_id}")
                return True
            return False

    async def get_all_ids(self) -> list[str]:
        """Get all session IDs."""
        async with self._lock:
            return list(self._sessions.keys())

    async def count(self) -> int:
        """Get total session count."""
        async with self._lock:
            return len(self._sessions)
