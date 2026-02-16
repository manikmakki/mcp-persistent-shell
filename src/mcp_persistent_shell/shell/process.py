"""Shell process wrapper using pexpect for persistent shells."""

import asyncio
import logging
import time
from typing import Any

import pexpect

from mcp_persistent_shell.config import ShellConfig
from mcp_persistent_shell.models import CommandResult


class ShellProcess:
    """Wrapper for a persistent PTY shell process using pexpect."""

    def __init__(
        self,
        shell_config: ShellConfig,
        working_dir: str = "/workspace",
        logger: logging.Logger | None = None,
    ):
        self.shell_config = shell_config
        self.working_dir = working_dir
        self.logger = logger or logging.getLogger(__name__)
        self.process: pexpect.spawn | None = None
        self.last_activity = time.time()
        self.prompt = f"{shell_config.prompt_marker}> "

    async def start(self) -> None:
        """Spawn the shell process in a thread pool."""
        self.logger.info(
            f"Starting shell process: {self.shell_config.default_shell} in {self.working_dir}"
        )

        def _spawn_shell() -> pexpect.spawn:
            """Spawn shell in thread (pexpect is not async-safe)."""
            proc = pexpect.spawn(
                self.shell_config.default_shell,
                cwd=self.working_dir,
                timeout=30,
                encoding="utf-8",
                echo=False,
            )

            # Set custom prompt for reliable detection
            proc.sendline(f'export PS1="{self.prompt}"')
            proc.expect(self.prompt, timeout=5)

            # Clear any initial output
            proc.before = ""

            return proc

        self.process = await asyncio.to_thread(_spawn_shell)
        self.last_activity = time.time()
        self.logger.info("Shell process started successfully")

    async def execute(
        self,
        command: str,
        timeout: int = 30,
    ) -> CommandResult:
        """Execute a command and return structured result."""
        if not self.process or not self.process.isalive():
            raise RuntimeError("Shell process is not running")

        start_time = time.time()
        self.logger.debug(f"Executing command: {command}")

        def _execute_command() -> tuple[str, str, int]:
            """Execute command in thread (pexpect is not async-safe)."""
            if not self.process:
                raise RuntimeError("Shell process not initialized")

            # Send command
            self.process.sendline(command)

            try:
                # Wait for prompt to return
                self.process.expect(self.prompt, timeout=timeout)

                # Capture output (everything before the prompt)
                output = self.process.before or ""

                # Get exit code by running echo $?
                self.process.sendline("echo $?")
                self.process.expect(self.prompt, timeout=5)
                exit_code_str = (self.process.before or "").strip()

                try:
                    exit_code = int(exit_code_str)
                except ValueError:
                    exit_code = 0  # Assume success if we can't parse

                return output, "", exit_code

            except pexpect.TIMEOUT:
                self.logger.warning(f"Command timed out after {timeout}s: {command}")
                # Try to get any partial output
                output = self.process.before or ""
                return output, f"Command timed out after {timeout}s", -1

            except pexpect.EOF:
                self.logger.error("Shell process terminated unexpectedly")
                return "", "Shell process terminated", -1

        try:
            stdout, stderr, exit_code = await asyncio.to_thread(_execute_command)
            execution_time = time.time() - start_time
            self.last_activity = time.time()

            status = "success" if exit_code == 0 else "error"

            return CommandResult(
                status=status,
                exit_code=exit_code,
                stdout=stdout.strip(),
                stderr=stderr,
                command=command,
                execution_time=execution_time,
            )

        except Exception as e:
            self.logger.error(f"Error executing command: {e}")
            execution_time = time.time() - start_time
            return CommandResult(
                status="error",
                exit_code=-1,
                stdout="",
                stderr=str(e),
                command=command,
                execution_time=execution_time,
            )

    async def get_cwd(self) -> str:
        """Get the current working directory."""
        result = await self.execute("pwd", timeout=5)
        if result.status == "success":
            return result.stdout.strip()
        return self.working_dir

    async def reset(self) -> None:
        """Reset the shell by terminating and restarting."""
        self.logger.info("Resetting shell process")
        await self.terminate()
        await self.start()

    async def terminate(self) -> None:
        """Terminate the shell process gracefully."""
        if self.process and self.process.isalive():
            self.logger.info("Terminating shell process")

            def _terminate() -> None:
                if self.process:
                    try:
                        self.process.sendline("exit")
                        self.process.expect(pexpect.EOF, timeout=5)
                    except:
                        pass
                    finally:
                        if self.process.isalive():
                            self.process.terminate(force=True)

            await asyncio.to_thread(_terminate)
            self.process = None

    def is_alive(self) -> bool:
        """Check if the shell process is still alive."""
        return self.process is not None and self.process.isalive()

    def idle_time(self) -> float:
        """Get the idle time in seconds."""
        return time.time() - self.last_activity
