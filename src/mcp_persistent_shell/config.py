"""Configuration management for MCP persistent shell server."""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecurityConfig(BaseSettings):
    """Security configuration."""

    enabled: bool = Field(default=False, description="Enable security validation")
    allowed_executables: list[str] = Field(
        default_factory=list,
        description="Allowlist of executable commands (strict mode)",
    )
    blocked_patterns: list[str] = Field(
        default_factory=list,
        description="Blocklist of regex patterns to reject",
    )
    max_execution_time: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Maximum execution time per command (seconds)",
    )
    max_output_size: int = Field(
        default=1048576,  # 1MB
        ge=1024,
        le=10485760,  # 10MB
        description="Maximum output size per command (bytes)",
    )
    working_directory: str = Field(
        default="/workspace",
        description="Working directory for shell processes",
    )
    run_as_user: str = Field(
        default="",
        description="Unix user to run commands as (empty = current user)",
    )
    audit_log: bool = Field(
        default=True,
        description="Enable audit logging for security events",
    )


class SessionConfig(BaseSettings):
    """Session management configuration."""

    timeout: int = Field(
        default=3600,
        ge=60,
        description="Session timeout in seconds (default: 1 hour)",
    )
    max_sessions: int = Field(
        default=100,
        ge=1,
        description="Maximum concurrent sessions",
    )
    cleanup_interval: int = Field(
        default=300,
        ge=30,
        description="Interval for cleanup task in seconds (default: 5 minutes)",
    )


class ServerConfig(BaseSettings):
    """HTTP server configuration."""

    name: str = Field(
        default="mcp-persistent-shell",
        description="Server name",
    )
    version: str = Field(
        default="0.1.0",
        description="Server version",
    )
    host: str = Field(
        default="127.0.0.1",
        description="Host to bind to (use 127.0.0.1 for security)",
    )
    port: int = Field(
        default=3000,
        ge=1024,
        le=65535,
        description="Port to bind to",
    )


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    level: str = Field(
        default="info",
        description="Log level (debug, info, warning, error, critical)",
    )
    format: str = Field(
        default="json",
        description="Log format (json or console)",
    )


class ShellConfig(BaseSettings):
    """Shell process configuration."""

    default_shell: str = Field(
        default="/bin/bash",
        description="Default shell to use",
    )
    prompt_marker: str = Field(
        default="__MCP_SHELL_PROMPT__",
        description="Custom prompt marker for detection",
    )


class Config(BaseSettings):
    """Main configuration container."""

    model_config = SettingsConfigDict(
        env_prefix="MCP_SHELL_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    security: SecurityConfig = Field(default_factory=SecurityConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    shell: ShellConfig = Field(default_factory=ShellConfig)

    config_file: str = Field(default="", env="MCP_SHELL_CONFIG_FILE")

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from environment and optional YAML file."""
        # Load base config from environment variables
        config = cls()

        # If config file is specified, overlay YAML values
        config_file_path = os.environ.get("MCP_SHELL_CONFIG_FILE", config.config_file)
        if config_file_path and Path(config_file_path).exists():
            with open(config_file_path, "r") as f:
                yaml_data = yaml.safe_load(f)

            if yaml_data:
                # Update config with YAML values
                if "security" in yaml_data:
                    config.security = SecurityConfig(**yaml_data["security"])
                if "session" in yaml_data:
                    config.session = SessionConfig(**yaml_data["session"])
                if "server" in yaml_data:
                    config.server = ServerConfig(**yaml_data["server"])
                if "logging" in yaml_data:
                    config.logging = LoggingConfig(**yaml_data["logging"])
                if "shell" in yaml_data:
                    config.shell = ShellConfig(**yaml_data["shell"])

        return config

    def warn_if_insecure(self) -> None:
        """Print warnings if security is disabled."""
        if not self.security.enabled:
            print(
                "\n⚠️  WARNING: Security is DISABLED! All commands will be executed without validation."
            )
            print("⚠️  Set MCP_SHELL_CONFIG_FILE with security.enabled=true to enable restrictions.")
            print("⚠️  This is DANGEROUS in production environments.\n")

        if self.server.host == "0.0.0.0":
            print(
                "\n⚠️  WARNING: Server is binding to all interfaces (0.0.0.0)!"
            )
            print("⚠️  This exposes the shell to your entire network.")
            print("⚠️  Consider using 127.0.0.1 for localhost-only access.\n")
