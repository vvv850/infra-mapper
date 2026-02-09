"""Configuration manager for persisting server settings."""

from pathlib import Path
from typing import List, Optional
import yaml

from ..models.server import ServerCredentials
from ..utils.exceptions import ConfigurationError


class ConfigManager:
    """Manages configuration persistence for server credentials."""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize configuration manager.

        Args:
            config_dir: Directory for configuration files (default: ~/.infra-mapper)
        """
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
                "servers": [
                    {
                        "hostname": s.hostname,
                        "username": s.username,
                        "ssh_key_path": str(s.ssh_key_path),
                        "port": s.port,
                    }
                    for s in servers
                ]
            }

            with open(self.config_file, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        except Exception as e:
            raise ConfigurationError(f"Failed to save configuration: {e}")

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

            servers = [
                ServerCredentials(
                    hostname=server["hostname"],
                    username=server["username"],
                    ssh_key_path=Path(server["ssh_key_path"]),
                    port=server.get("port", 22),
                )
                for server in data["servers"]
            ]

            return servers

        except yaml.YAMLError as e:
            raise ConfigurationError(f"Failed to parse configuration file: {e}")
        except (KeyError, TypeError) as e:
            raise ConfigurationError(f"Invalid configuration format: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")

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
