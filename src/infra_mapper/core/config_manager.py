"""Configuration manager for persisting server settings."""

import platform
from pathlib import Path
from typing import List, Optional
import yaml

from ..models.server import ServerCredentials
from ..utils.exceptions import ConfigurationError


class ConfigManager:
    """Manages configuration persistence for server credentials."""

    def __init__(self, config_dir: Optional[Path] = None, config_file: Optional[Path] = None):
        """
        Initialize configuration manager.

        Args:
            config_dir: Directory for configuration files (default: ~/.infra-mapper)
            config_file: Explicit path to config file. Overrides config_dir if provided.
        """
        if config_file is not None:
            self.config_file = Path(config_file).expanduser()
            self.config_dir = self.config_file.parent
        else:
            if config_dir is None:
                config_dir = Path.home() / ".infra-mapper"
            self.config_dir = Path(config_dir)
            self.config_file = self.config_dir / "servers.yaml"

        # Create config directory if it doesn't exist
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def save_servers(self, servers: List[ServerCredentials]) -> None:
        """
        Save server configurations to file.

        Args:
            servers: List of server credentials to save

        Raises:
            ConfigurationError: If save fails
        """
        try:
            data = {
                "servers": [self._serialize_server(s) for s in servers]
            }

            with open(self.config_file, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        except Exception as e:
            raise ConfigurationError(f"Failed to save configuration: {e}")

    def _serialize_server(self, server: ServerCredentials) -> dict:
        """Serialize a single server to dict for YAML output."""
        entry = {
            "hostname": server.hostname,
            "username": server.username,
            "auth_method": server.auth_method,
            "port": server.port,
        }
        if server.auth_method == "key" and server.ssh_key_path:
            entry["ssh_key_path"] = str(server.ssh_key_path)
        # Password is deliberately NOT saved
        return entry

    def load_servers(self) -> Optional[List[ServerCredentials]]:
        """
        Load server configurations from file.

        Returns:
            List of ServerCredentials if config exists, None otherwise

        Raises:
            ConfigurationError: If config exists but cannot be loaded/parsed
        """
        if not self.config_exists():
            return None

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "servers" not in data:
                return None

            servers = []
            for server in data["servers"]:
                auth_method = server.get("auth_method", "key")
                if auth_method == "password":  # backward compat
                    auth_method = "pass"
                kwargs = {
                    "hostname": server["hostname"],
                    "username": server["username"],
                    "auth_method": auth_method,
                    "port": server.get("port", 22),
                }
                if auth_method == "key":
                    ssh_key_path = server.get("ssh_key_path")
                    if ssh_key_path:
                        kwargs["ssh_key_path"] = Path(ssh_key_path)
                servers.append(ServerCredentials(**kwargs))

            return servers

        except yaml.YAMLError as e:
            raise ConfigurationError(f"Failed to parse configuration file: {e}")
        except (KeyError, TypeError, ValueError) as e:
            raise ConfigurationError(f"Invalid configuration format: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")

    def generate_template(self) -> Path:
        """Generate a template servers.yaml with example entries."""
        if platform.system() == "Windows":
            example_key_path = "C:\\Users\\YourUser\\.ssh\\id_rsa"
        else:
            example_key_path = "/home/youruser/.ssh/id_rsa"

        template = {
            "servers": [
                {
                    "hostname": "server1.example.com",
                    "username": "root",
                    "auth_method": "key",
                    "ssh_key_path": example_key_path,
                    "port": 22,
                },
                {
                    "hostname": "server2.example.com",
                    "username": "admin",
                    "auth_method": "pass",
                    "port": 22,
                },
                {
                    "hostname": "server3.example.com",
                    "username": "deploy",
                    "auth_method": "agent",
                    "port": 22,
                },
            ]
        }

        with open(self.config_file, "w", encoding="utf-8") as f:
            yaml.dump(template, f, default_flow_style=False, sort_keys=False)
            f.write(
                "\n# Authentication methods:\n"
                "#   auth_method: key   - SSH private key (provide ssh_key_path)\n"
                "#   auth_method: pass  - Prompts for password at runtime (never stored)\n"
                "#   auth_method: agent - System SSH agent (1Password, ssh-agent, Pageant)\n"
            )

        return self.config_file

    def config_exists(self) -> bool:
        """
        Check if configuration file exists.

        Returns:
            True if config file exists, False otherwise
        """
        return self.config_file.exists() and self.config_file.is_file()

    def delete_config(self) -> None:
        """Delete configuration file if it exists."""
        if self.config_exists():
            self.config_file.unlink()

    def __str__(self) -> str:
        """Format config manager as string for display."""
        return f"ConfigManager({self.config_file})"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return f"ConfigManager(config_dir='{self.config_dir}')"
