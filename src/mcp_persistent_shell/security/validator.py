"""Security validator for command execution (ported from Go reference)."""

import logging
import re
from typing import List

from mcp_persistent_shell.config import SecurityConfig


class SecurityValidator:
    """Validates commands based on security configuration."""

    def __init__(self, config: SecurityConfig, logger: logging.Logger | None = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self._compiled_patterns = [re.compile(p) for p in config.blocked_patterns]

    def is_enabled(self) -> bool:
        """Check if security validation is enabled."""
        return self.config.enabled

    def validate_command(self, command: str) -> None:
        """Validate command against security policies. Raises ValueError if invalid."""
        if not self.config.enabled:
            return

        command = command.strip()
        if not command:
            raise ValueError("Empty command")

        # Extract executable (first token)
        executable = command.split()[0] if command else ""

        # Check allowlist (if configured)
        if self.config.allowed_executables:
            if executable not in self.config.allowed_executables:
                if self.config.audit_log:
                    self.logger.warning(
                        f"Blocked command (not in allowlist): {command}",
                        extra={"audit": True, "command": command},
                    )
                raise ValueError(
                    f"Command '{executable}' is not in the allowlist. "
                    f"Allowed: {', '.join(self.config.allowed_executables)}"
                )

        # Check blocklist patterns
        for pattern in self._compiled_patterns:
            if pattern.search(command):
                if self.config.audit_log:
                    self.logger.warning(
                        f"Blocked command (matches pattern): {command}",
                        extra={"audit": True, "command": command, "pattern": pattern.pattern},
                    )
                raise ValueError(
                    f"Command matches blocked pattern: {pattern.pattern}"
                )

        # Audit log successful validation
        if self.config.audit_log:
            self.logger.info(
                f"Command validated: {command}",
                extra={"audit": True, "command": command},
            )
