"""FastAPI server with MCP Streamable HTTP transport."""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from mcp.server import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from mcp_persistent_shell.config import Config
from mcp_persistent_shell.security.validator import SecurityValidator
from mcp_persistent_shell.session.manager import SessionManager
from mcp_persistent_shell.shell.process import ShellProcess
from mcp_persistent_shell.tools.execute_command import handle_execute_command
from mcp_persistent_shell.tools.get_cwd import handle_get_cwd
from mcp_persistent_shell.tools.reset_session import handle_reset_session
from mcp_persistent_shell.tools.upload_file import handle_upload_file
from mcp_persistent_shell.tools.download_file import handle_download_file
from mcp_persistent_shell.utils.logger import setup_logging


# Global state
config: Config
session_manager: SessionManager
security_validator: SecurityValidator
logger: logging.Logger
mcp: FastMCP
global_shell: ShellProcess | None = None  # Single shared shell session for MVP


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    global config, session_manager, security_validator, logger, mcp, global_shell

    # Load configuration
    config = Config.load()

    # Setup logging
    logger = setup_logging(config.logging)
    logger.info("Starting MCP Persistent Shell Server")

    # Warn if security is disabled
    config.warn_if_insecure()

    # Initialize components
    security_validator = SecurityValidator(config.security, logger)
    session_manager = SessionManager(
        config.session,
        config.shell,
        config.security,
        logger,
    )

    # Create FastMCP server with relaxed transport security
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=False  # Disable for Docker/network access
    )
    mcp = FastMCP(
        name="mcp-persistent-shell",
        transport_security=transport_security,
    )

    async def ensure_shell() -> ShellProcess:
        """Ensure global shell is created and return it."""
        global global_shell
        if global_shell is None or not global_shell.is_alive():
            global_shell = ShellProcess(
                shell_config=config.shell,
                working_dir=config.security.working_directory,
                logger=logger,
            )
            await global_shell.start()
            logger.info("Global shell session initialized")
        return global_shell

    # Register tools
    @mcp.tool()
    async def execute_command(command: str, timeout: int = 30) -> dict[str, Any]:
        """Execute a shell command in the persistent session.

        State is preserved across commands (cwd, env vars, etc.).

        Args:
            command: The shell command to execute
            timeout: Timeout in seconds (default: 30)
        """
        logger.info(f"execute_command called with: command={command!r}, timeout={timeout}")

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

        # Get or create global shell
        shell = await ensure_shell()
        logger.debug(f"Shell alive: {shell.is_alive()}")

        # Execute command
        result = await shell.execute(command, timeout=timeout)
        logger.info(f"Command result: status={result.status}, exit_code={result.exit_code}, stdout_len={len(result.stdout)}")
        return result.model_dump()

    @mcp.tool()
    async def get_working_directory() -> dict[str, Any]:
        """Get the current working directory of the shell session."""
        shell = await ensure_shell()
        cwd = await shell.get_cwd()
        return {"cwd": cwd}

    @mcp.tool()
    async def reset_session() -> dict[str, Any]:
        """Reset the shell session to a clean state (equivalent to spawning a new shell)."""
        shell = await ensure_shell()
        await shell.reset()
        return {"status": "reset", "message": "Shell session has been reset to clean state"}

    @mcp.tool()
    async def upload_file(path: str, content: str, encoding: str = "base64") -> dict[str, Any]:
        """Upload a file to the shell workspace.

        Args:
            path: Path to the file in workspace
            content: File content (base64 or utf8 encoded)
            encoding: Content encoding (default: base64)
        """
        shell = await ensure_shell()

        # We need the shell's cwd for relative paths
        import base64
        import os
        from pathlib import Path

        try:
            # Decode content
            if encoding == "base64":
                file_content = base64.b64decode(content)
            else:
                file_content = content.encode("utf-8")

            # Get absolute path relative to workspace
            cwd = await shell.get_cwd()
            if not path.startswith("/"):
                abs_path = os.path.join(cwd, path)
            else:
                abs_path = path

            # Create parent directory if needed
            Path(abs_path).parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(abs_path, "wb") as f:
                f.write(file_content)

            size = len(file_content)
            return {"status": "uploaded", "path": abs_path, "size": size}

        except Exception as e:
            return {"error": f"Failed to upload file: {str(e)}"}

    @mcp.tool()
    async def download_file(path: str, encoding: str = "base64") -> dict[str, Any]:
        """Download a file from the shell workspace.

        Args:
            path: Path to the file in workspace
            encoding: Content encoding (default: base64)
        """
        shell = await ensure_shell()

        import base64
        import os

        try:
            # Get absolute path relative to workspace
            cwd = await shell.get_cwd()
            if not path.startswith("/"):
                abs_path = os.path.join(cwd, path)
            else:
                abs_path = path

            # Read file
            with open(abs_path, "rb") as f:
                file_content = f.read()

            # Encode content
            if encoding == "base64":
                content_str = base64.b64encode(file_content).decode("ascii")
            else:
                content_str = file_content.decode("utf-8")

            size = len(file_content)
            return {"content": content_str, "size": size, "encoding": encoding}

        except FileNotFoundError:
            return {"error": f"File not found: {path}"}
        except Exception as e:
            return {"error": f"Failed to download file: {str(e)}"}

    # Get the MCP streamable HTTP app
    mcp_app = mcp.streamable_http_app()

    # Create main FastAPI app with combined lifespan
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Lifecycle manager."""
        # Start our session cleanup task
        await session_manager.start_cleanup_task()

        # Start the FastMCP session manager (required for MCP to work)
        async with mcp.session_manager.run():
            # Initialize global shell
            await ensure_shell()

            logger.info(f"Server ready on {config.server.host}:{config.server.port}")

            yield

            # Shutdown
            logger.info("Shutting down server")
            if global_shell:
                await global_shell.terminate()

        await session_manager.shutdown()

    app = FastAPI(title="MCP Persistent Shell", lifespan=lifespan)

    # Add health check endpoint BEFORE mounting MCP app
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": config.server.version,
            "shell_alive": global_shell.is_alive() if global_shell else False,
            "security_enabled": config.security.enabled,
        }

    # Mount MCP streamable HTTP app (catches all other routes)
    # This must be AFTER defining our custom endpoints
    app.mount("", mcp_app)

    return app


# Create the app instance
app = create_app()
