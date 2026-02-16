# MCP Persistent Shell Server

A Model Context Protocol (MCP) server providing **persistent shell access** via **Streamable HTTP** transport. Designed for LLM agents to perform agentic workflows with stateful shell sessions.

## Features

- **Persistent Shell Session**: Maintains a single interactive shell process across requests
  - State preservation (cwd, env vars, virtualenv activation)
  - Commands build on previous state
  - **Current limitation**: Single global shell shared across all MCP clients

- **MCP Streamable HTTP Transport**: Compatible with OpenWebUI External Tools
  - JSON-RPC over HTTP/SSE
  - MCP session management via `Mcp-Session-Id` header
  - DNS rebinding protection disabled for Docker/network access

- **Security**: Configurable validation (opt-in, disabled by default)
  - Command allowlist/blocklist
  - Execution timeouts and output limits
  - Non-root execution in Docker

- **File Transfer**: Upload/download files to/from workspace
  - Base64 and UTF-8 encoding support

- **Workspace Persistence**: Files persist indefinitely
  - Not automatically cleaned (user/agent manages cleanup)
  - Persists across container restarts via volume mount

## Quick Start

### Docker (Recommended)

```bash
cd /opt/gen-ai/ai-assistant-shell/mcp-persistent-shell

# Build and run
docker-compose up -d

# Check health
curl http://localhost:3000/health

# View logs
docker-compose logs -f
```

### Bare Metal

```bash
# Install dependencies
pip install -r requirements.txt

# Run server (binds to 127.0.0.1:3000 by default)
python -m mcp_persistent_shell

# Or with custom config
MCP_SHELL_CONFIG_FILE=config/security.yaml python -m mcp_persistent_shell
```

## MCP Tools

### 1. `execute_command`
Execute a command in the persistent shell session.

```json
{
  "name": "execute_command",
  "arguments": {
    "command": "ls -la",
    "timeout": 30
  }
}
```

**Response:**
```json
{
  "status": "success",
  "exit_code": 0,
  "stdout": "total 8\ndrwxrwxrwx ...",
  "stderr": "",
  "command": "ls -la",
  "execution_time": 0.05
}
```

### 2. `get_working_directory`
Get the current working directory.

```json
{
  "name": "get_working_directory",
  "arguments": {}
}
```

**Response:**
```json
{
  "cwd": "/workspace"
}
```

### 3. `reset_session`
Reset the shell to a clean state (kills and restarts the shell process).

```json
{
  "name": "reset_session",
  "arguments": {}
}
```

### 4. `upload_file`
Upload a file to the workspace.

```json
{
  "name": "upload_file",
  "arguments": {
    "path": "script.py",
    "content": "cHJpbnQoJ0hlbGxvJyk=",
    "encoding": "base64"
  }
}
```

### 5. `download_file`
Download a file from the workspace.

```json
{
  "name": "download_file",
  "arguments": {
    "path": "output.txt",
    "encoding": "base64"
  }
}
```

## OpenWebUI Integration

Configure in OpenWebUI **Admin Panel → Settings → External Tools**:

```json
{
  "name": "Persistent Shell",
  "url": "http://<your-server-ip>:3000/mcp",
  "type": "mcp",
  "auth_type": "none"
}
```

**Important**:
- Set `auth_type` to `"none"` (not "bearer" or empty)
- If OpenWebUI is on a different machine, use the server's IP address
- Port 3000 must be accessible from OpenWebUI

## Configuration

### Environment Variables

Use `__` (double underscore) for nested configuration:

```bash
# Server (nested under 'server')
MCP_SHELL_SERVER__HOST=127.0.0.1
MCP_SHELL_SERVER__PORT=3000

# Logging (nested under 'logging')
MCP_SHELL_LOGGING__LEVEL=info
MCP_SHELL_LOGGING__FORMAT=json

# Session (nested under 'session')
MCP_SHELL_SESSION__TIMEOUT=3600
MCP_SHELL_SESSION__MAX_SESSIONS=100
MCP_SHELL_SESSION__CLEANUP_INTERVAL=300

# Shell (nested under 'shell')
MCP_SHELL_SHELL__DEFAULT_SHELL=/bin/bash

# Security (optional: path to YAML config file)
MCP_SHELL_CONFIG_FILE=config/security.yaml
```

See `.env.example` for complete list.

### Security Configuration (YAML)

Enable security by mounting a config file:

**`config/security.yaml`:**
```yaml
security:
  enabled: true
  allowed_executables: [ls, pwd, git, python3, node, npm, curl, wget]
  blocked_patterns:
    - 'rm\s+.*-rf.*'
    - 'sudo\s+.*'
    - 'chmod\s+(777|666)'
  max_execution_time: 30
  max_output_size: 1048576  # 1MB
  working_directory: /workspace
```

**Enable in docker-compose.yml:**
```yaml
environment:
  MCP_SHELL_CONFIG_FILE: "/etc/mcp-persistent-shell/security.yaml"
volumes:
  - ./config/security.yaml:/etc/mcp-persistent-shell/security.yaml:ro
```

## Security Considerations

⚠️ **Default**: Security is **DISABLED** by default for easy development.

**Production Deployment Checklist**:
1. ✅ Mount `config/security.yaml` with `enabled: true`
2. ✅ Use command `allowed_executables` allowlist
3. ✅ Bind to `127.0.0.1` or use firewall rules
4. ✅ Run in Docker as non-root user (UID 1000)
5. ✅ Set appropriate `max_execution_time` and `max_output_size`
6. ✅ Monitor audit logs (`audit_log: true`)

**Network Security**:
- DNS rebinding protection is **disabled** to allow Docker/network access
- Only expose to trusted networks
- Consider adding authentication layer (reverse proxy with auth)

## Workspace Persistence

- Files in `/workspace` are **permanent** - not auto-deleted
- Session cleanup only terminates shell process, not files
- Docker volume mount: `./workspace:/workspace`
- Agent/user responsible for cleanup via commands

## API Endpoints

- **POST /mcp** - MCP JSON-RPC requests (initialize, tool calls)
- **GET /mcp** - SSE stream for server notifications
- **GET /health** - Health check
  ```json
  {
    "status": "healthy",
    "version": "0.1.0",
    "shell_alive": true,
    "security_enabled": false
  }
  ```

## Architecture

```
FastAPI Server (Streamable HTTP)
├── FastMCP (handles MCP protocol)
│   └── Streamable HTTP session manager
├── Global Shell Process (shared across all clients)
│   └── pexpect PTY wrapper (bash)
├── Security Validator (optional)
└── MCP Tool Handlers
    ├── execute_command
    ├── get_working_directory
    ├── reset_session
    ├── upload_file
    └── download_file
```

**Current Architecture Note**:
- Single global shell session shared across all MCP clients
- MCP manages its own session IDs for protocol handling
- Future enhancement: Map MCP sessions → individual shell processes

## Development

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests (when implemented)
pytest

# Format code
black src tests
ruff check src tests

# Type checking
mypy src
```

## Troubleshooting

### OpenWebUI shows empty command output
- Check server logs: `docker logs mcp-persistent-shell -f`
- Verify auth_type is set to `"none"` in OpenWebUI
- Ensure Accept headers include both `application/json` and `text/event-stream`

### Connection refused / timeout
- Check server is running: `docker ps | grep mcp-persistent-shell`
- Verify port is accessible: `curl http://localhost:3000/health`
- If OpenWebUI is on different machine, ensure port 3000 is open

### Command execution fails silently
- Check if security is blocking: look for "Security validation failed" in logs
- Try with security disabled first, then enable gradually
- Verify shell is alive: check `/health` endpoint `shell_alive` field

## Known Limitations

1. **Single Global Shell**: All MCP clients share one shell session
   - State changes affect all users
   - Consider this when deploying for multi-user scenarios

2. **No Session Isolation**: Future enhancement to support per-client shells

3. **Bash Only**: Currently only supports bash (configurable via `SHELL__DEFAULT_SHELL`)

## Future Enhancements

- [ ] Per-MCP-session shell isolation
- [ ] Multiple shell types (zsh, python REPL, etc.)
- [ ] Resource limits (memory, CPU via cgroups)
- [ ] Authentication/authorization
- [ ] Redis-backed session storage for horizontal scaling

## License

[GNU Affero General Public License v3.0 (AGPL-3.0) ](LICENSE.md)

## References

- [MCP Specification (2025-03-26)](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)
- [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk)
- [FastMCP Documentation](https://gofastmcp.com/)
- [OpenWebUI MCP Integration](https://docs.openwebui.com/tutorials/integrations/mcp-notion/)
- [mcp-shell Reference (Go)](https://github.com/sonirico/mcp-shell)
