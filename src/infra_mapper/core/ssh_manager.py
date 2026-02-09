"""SSH connection manager for remote server operations."""

import paramiko
from pathlib import Path
from typing import Tuple, Optional
from contextlib import contextmanager

from ..utils.exceptions import SSHConnectionError


class SSHConnectionManager:
    """Manages SSH connections to remote servers."""

    def __init__(
        self,
        hostname: str,
        username: str,
        key_path: Optional[Path] = None,
        port: int = 22,
        password: Optional[str] = None,
    ):
        """
        Initialize SSH connection manager.

        Args:
            hostname: Server hostname or IP address
            username: SSH username
            key_path: Path to SSH private key (for key-based auth)
            port: SSH port (default: 22)
            password: SSH password (for password-based auth)
        """
        self.hostname = hostname
        self.username = username
        self.key_path = Path(key_path).expanduser() if key_path else None
        self.port = port
        self.password = password
        self._client: Optional[paramiko.SSHClient] = None

    @contextmanager
    def connect(self):
        """
        Context manager for SSH connections.

        Usage:
            ssh = SSHConnectionManager(hostname, username, key_path=key_path)
            with ssh.connect():
                exit_code, stdout, stderr = ssh.execute_command("ls")

        Raises:
            SSHConnectionError: If connection fails
        """
        try:
            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if self.password:
                # Password-based authentication
                self._client.connect(
                    hostname=self.hostname,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=10,
                    banner_timeout=10,
                )
            elif self.key_path:
                # Key-based authentication - try multiple key formats
                try:
                    key = paramiko.RSAKey.from_private_key_file(str(self.key_path))
                except paramiko.SSHException:
                    try:
                        key = paramiko.Ed25519Key.from_private_key_file(str(self.key_path))
                    except paramiko.SSHException:
                        key = paramiko.ECDSAKey.from_private_key_file(str(self.key_path))

                self._client.connect(
                    hostname=self.hostname,
                    port=self.port,
                    username=self.username,
                    pkey=key,
                    timeout=10,
                    banner_timeout=10,
                )
            else:
                raise SSHConnectionError(
                    "No authentication method provided. Supply either key_path or password."
                )

            yield self

        except FileNotFoundError:
            raise SSHConnectionError(
                f"SSH key file not found: {self.key_path}"
            )
        except paramiko.AuthenticationException:
            raise SSHConnectionError(
                f"Authentication failed for {self.username}@{self.hostname}"
            )
        except SSHConnectionError:
            raise
        except paramiko.SSHException as e:
            raise SSHConnectionError(
                f"SSH error connecting to {self.hostname}: {e}"
            )
        except Exception as e:
            raise SSHConnectionError(
                f"Failed to connect to {self.hostname}: {e}"
            )
        finally:
            if self._client:
                self._client.close()
                self._client = None

    def execute_command(self, command: str, timeout: int = 30) -> Tuple[int, str, str]:
        """
        Execute command on remote server.

        Args:
            command: Command to execute
            timeout: Command timeout in seconds (default: 30)

        Returns:
            Tuple of (exit_code, stdout, stderr)

        Raises:
            ConnectionError: If not connected to server
            SSHConnectionError: If command execution fails
        """
        if not self._client:
            raise ConnectionError("Not connected to server. Use connect() context manager.")

        try:
            stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()

            stdout_str = stdout.read().decode("utf-8", errors="replace")
            stderr_str = stderr.read().decode("utf-8", errors="replace")

            return exit_code, stdout_str, stderr_str

        except Exception as e:
            raise SSHConnectionError(
                f"Failed to execute command on {self.hostname}: {e}"
            )

    def test_connection(self) -> bool:
        """
        Test if SSH connection works.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self.connect():
                exit_code, _, _ = self.execute_command("echo test")
                return exit_code == 0
        except SSHConnectionError:
            return False

    def __str__(self) -> str:
        """Format SSH manager as string for display."""
        auth = "password" if self.password else "key"
        return f"SSH({self.username}@{self.hostname}:{self.port}, {auth})"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"SSHConnectionManager(hostname='{self.hostname}', "
            f"username='{self.username}', port={self.port})"
        )
