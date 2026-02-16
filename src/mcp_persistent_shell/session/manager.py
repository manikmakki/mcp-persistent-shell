"""Session lifecycle management."""

import asyncio
import logging
import uuid
from typing import Optional

from mcp_persistent_shell.config import SessionConfig, ShellConfig, SecurityConfig
from mcp_persistent_shell.session.store import SessionStore
from mcp_persistent_shell.shell.process import ShellProcess


class SessionManager:
    """Manages shell session lifecycle and cleanup."""

    def __init__(
        self,
        session_config: SessionConfig,
        shell_config: ShellConfig,
        security_config: SecurityConfig,
        logger: logging.Logger | None = None,
    ):
        self.session_config = session_config
        self.shell_config = shell_config
        self.security_config = security_config
        self.logger = logger or logging.getLogger(__name__)
        self.store = SessionStore(logger)
        self._cleanup_task: Optional[asyncio.Task] = None

    async def create_session(self) -> tuple[str, ShellProcess]:
        """Create a new session with a shell process."""
        # Check max sessions limit
        if await self.store.count() >= self.session_config.max_sessions:
            raise RuntimeError(
                f"Maximum sessions limit reached ({self.session_config.max_sessions})"
            )

        # Generate cryptographically secure session ID
        session_id = str(uuid.uuid4())

        # Create and start shell process
        shell = ShellProcess(
            shell_config=self.shell_config,
            working_dir=self.security_config.working_directory,
            logger=self.logger,
        )
        await shell.start()

        # Store session
        await self.store.create(session_id, shell)

        self.logger.info(f"Created session {session_id}")
        return session_id, shell

    async def get_session(self, session_id: str) -> Optional[ShellProcess]:
        """Get shell process for session ID."""
        shell = await self.store.get(session_id)
        if shell and not shell.is_alive():
            # Clean up dead process
            await self.store.delete(session_id)
            return None
        return shell

    async def delete_session(self, session_id: str) -> bool:
        """Explicitly terminate a session."""
        return await self.store.delete(session_id)

    async def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            self.logger.info("Started session cleanup task")

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            self.logger.info("Stopped session cleanup task")

    async def _cleanup_loop(self) -> None:
        """Background task to cleanup expired sessions."""
        while True:
            try:
                await asyncio.sleep(self.session_config.cleanup_interval)
                await self._cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup task: {e}")

    async def _cleanup_expired_sessions(self) -> None:
        """Clean up sessions that have exceeded timeout."""
        session_ids = await self.store.get_all_ids()

        for session_id in session_ids:
            shell = await self.store.get(session_id)
            if shell:
                idle_time = shell.idle_time()
                if idle_time > self.session_config.timeout:
                    self.logger.info(
                        f"Cleaning up expired session {session_id} (idle: {idle_time:.0f}s)"
                    )
                    await self.store.delete(session_id)
                elif not shell.is_alive():
                    self.logger.info(f"Cleaning up dead session {session_id}")
                    await self.store.delete(session_id)

    async def shutdown(self) -> None:
        """Shutdown all sessions and cleanup task."""
        await self.stop_cleanup_task()

        # Terminate all sessions
        session_ids = await self.store.get_all_ids()
        for session_id in session_ids:
            await self.store.delete(session_id)

        self.logger.info("Session manager shutdown complete")
