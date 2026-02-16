"""Main entry point for MCP Persistent Shell server."""

import sys


def main() -> int:
    """Run the MCP Persistent Shell server."""
    import uvicorn

    from mcp_persistent_shell.config import Config

    # Load config to get host/port
    config = Config.load()

    # Run server
    uvicorn.run(
        "mcp_persistent_shell.server:app",
        host=config.server.host,
        port=config.server.port,
        log_level=config.logging.level.lower(),
        access_log=config.logging.level.lower() == "debug",
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
