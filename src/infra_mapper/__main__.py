"""Main entry point for the Infrastructure Mapper CLI application."""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.progress import track, Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel

from .core.config_manager import ConfigManager
from .core.ssh_manager import SSHConnectionManager
from .core.docker_discovery import DockerDiscoveryService
from .generators.mermaid_generator import MermaidGenerator
from .models.server import ServerCredentials, ServerInfo
from .utils.exceptions import InfraMapperError, SSHConnectionError, DockerNotFoundError

# Configure UTF-8 encoding for Windows console to handle emojis
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

console = Console()


class InfraMapper:
    """Main application orchestrator for Infrastructure Mapper."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the Infrastructure Mapper application."""
        if config_path:
            self.config_manager = ConfigManager(config_file=Path(config_path))
        else:
            self.config_manager = ConfigManager()
        self.generator = MermaidGenerator()
        self._passwords: Dict[str, str] = {}

    def run(self) -> None:
        """Main execution flow."""
        try:
            # Display banner
            console.print(
                Panel.fit(
                    "[bold cyan]Docker Infrastructure Mapper[/bold cyan]\n"
                    "Discover and visualize Docker containers across servers",
                    border_style="cyan",
                )
            )
            console.print()

            # Get server configurations
            servers = self._get_server_configurations()

            if not servers:
                console.print("[red]No servers configured. Exiting.[/red]")
                return

            # Display configured servers
            self._display_servers_table(servers)

            # Discover containers on all servers
            console.print("\n[bold]Discovering Docker containers...[/bold]\n")
            server_info_list = self._discover_all_servers(servers)

            # Display summary
            self._display_summary(server_info_list)

            # Generate Mermaid diagram
            console.print("\n[bold]Generating Mermaid diagram...[/bold]")
            diagram = self.generator.generate(server_info_list)

            # Save to file
            output_file = Path("infrastructure.md")
            saved_path = self.generator.save_to_file(diagram, str(output_file))

            console.print(f"\n[green]Diagram saved to {saved_path}[/green]")
            console.print("\n[bold]Diagram Preview:[/bold]")
            console.print(diagram)

            console.print(
                f"\n[dim]Open {saved_path} in a Markdown viewer to see the rendered diagram[/dim]"
            )

        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user[/yellow]")
            sys.exit(0)
        except InfraMapperError as e:
            console.print(f"\n[red]Error: {e}[/red]")
            sys.exit(1)
        except Exception as e:
            console.print(f"\n[red]Unexpected error: {e}[/red]")
            sys.exit(1)

    def _get_server_configurations(self) -> List[ServerCredentials]:
        """Get server configurations from user or config file."""
        if self.config_manager.config_exists():
            # Config exists -- show count and ask to reuse
            try:
                servers = self.config_manager.load_servers()
                if servers:
                    console.print(
                        f"[cyan]Found saved configuration with "
                        f"{len(servers)} server(s) at {self.config_manager.config_file}[/cyan]"
                    )
                    use_saved = Confirm.ask(
                        "[cyan]Use saved configuration?[/cyan]", default=True
                    )

                    if use_saved:
                        console.print("[green]Loaded saved configuration[/green]\n")
                        self._passwords.update(self._collect_passwords(servers))
                        return servers
            except Exception as e:
                console.print(f"[yellow]Failed to load saved config: {e}[/yellow]")
                console.print("[yellow]Starting fresh configuration...[/yellow]\n")
        else:
            # First run -- no config exists
            console.print("[cyan]No server configuration found.[/cyan]")
            choice = Prompt.ask(
                "[cyan]Would you like to [bold](c)[/bold]reate one interactively "
                "or generate a [bold](t)[/bold]emplate?[/cyan]",
                choices=["c", "t"],
                default="c",
            )
            if choice == "t":
                template_path = self.config_manager.generate_template()
                console.print(
                    f"\n[green]Template created at {template_path}[/green]\n"
                    "[dim]Edit the file with your server details, then run infra-mapper again.[/dim]"
                )
                return []

        # Interactive prompting
        servers = self._prompt_servers()

        # Offer to save configuration
        if servers:
            save_config = Confirm.ask(
                "\n[cyan]Save server configuration for future use?[/cyan]", default=True
            )

            if save_config:
                try:
                    self.config_manager.save_servers(servers)
                    console.print(
                        f"[green]Configuration saved to {self.config_manager.config_file}[/green]\n"
                    )
                except Exception as e:
                    console.print(f"[yellow]Failed to save config: {e}[/yellow]\n")

        return servers

    def _collect_passwords(self, servers: List[ServerCredentials]) -> Dict[str, str]:
        """Prompt for passwords for servers using password authentication."""
        passwords: Dict[str, str] = {}
        password_servers = [s for s in servers if s.auth_method == "password"]
        if not password_servers:
            return passwords

        console.print(
            f"[cyan]{len(password_servers)} server(s) use password authentication.[/cyan]"
        )
        for server in password_servers:
            password = Prompt.ask(
                f"[cyan]Password for {server.username}@{server.hostname}[/cyan]",
                password=True,
            )
            passwords[f"{server.hostname}:{server.port}"] = password

        console.print()
        return passwords

    def _prompt_servers(self) -> List[ServerCredentials]:
        """Prompt user for server information."""
        servers = []

        console.print("[bold cyan]Server Configuration[/bold cyan]")
        console.print(
            "[dim]Enter details for each server (leave hostname empty to finish)[/dim]\n"
        )

        while True:
            # Prompt for hostname
            if servers:
                hostname = Prompt.ask(
                    f"[cyan]Server {len(servers) + 1} hostname/IP[/cyan]",
                    default="",
                )
            else:
                hostname = Prompt.ask(f"[cyan]Server {len(servers) + 1} hostname/IP[/cyan]")

            if not hostname or not hostname.strip():
                break

            hostname = hostname.strip()

            # Prompt for username
            username = Prompt.ask("[cyan]SSH username[/cyan]", default="root")

            # Prompt for port
            port_str = Prompt.ask("[cyan]SSH port[/cyan]", default="22")
            try:
                port = int(port_str)
            except ValueError:
                console.print("[red]Invalid port number. Using default 22.[/red]")
                port = 22

            # Prompt for authentication method
            auth_method = Prompt.ask(
                "[cyan]Authentication method[/cyan]",
                choices=["key", "password"],
                default="key",
            )

            if auth_method == "key":
                # SSH key path with validation loop
                key_path = self._prompt_ssh_key_path()
                if key_path is None:
                    console.print("[yellow]Skipping this server[/yellow]\n")
                    continue

                try:
                    server = ServerCredentials(
                        hostname=hostname,
                        username=username,
                        auth_method="key",
                        ssh_key_path=key_path,
                        port=port,
                    )
                    servers.append(server)
                    console.print(f"[green]Added {hostname} (key auth)[/green]\n")
                except Exception as e:
                    console.print(f"[red]Failed to add server: {e}[/red]\n")
            else:
                # Password auth -- prompt password now (won't be saved)
                password = Prompt.ask(
                    f"[cyan]Password for {username}@{hostname}[/cyan]",
                    password=True,
                )
                self._passwords[f"{hostname}:{port}"] = password

                try:
                    server = ServerCredentials(
                        hostname=hostname,
                        username=username,
                        auth_method="password",
                        port=port,
                    )
                    servers.append(server)
                    console.print(f"[green]Added {hostname} (password auth)[/green]\n")
                except Exception as e:
                    console.print(f"[red]Failed to add server: {e}[/red]\n")

        return servers

    def _prompt_ssh_key_path(self) -> Optional[Path]:
        """Prompt for SSH key path with validation loop."""
        default_key = str(Path.home() / ".ssh" / "id_rsa")
        key_path = None

        while key_path is None:
            key_path_str = Prompt.ask(
                "[cyan]SSH private key path[/cyan]", default=default_key
            )
            temp_key_path = Path(key_path_str).expanduser()

            if not temp_key_path.exists():
                console.print(f"[red]SSH key not found: {temp_key_path}[/red]")
                retry = Confirm.ask("Try a different key?", default=True)
                if not retry:
                    return None
            else:
                key_path = temp_key_path

        return key_path

    def _display_servers_table(self, servers: List[ServerCredentials]) -> None:
        """Display configured servers in a formatted table."""
        table = Table(title="Configured Servers", show_header=True, header_style="bold cyan")

        table.add_column("Hostname", style="cyan", no_wrap=True)
        table.add_column("Username", style="green")
        table.add_column("Port", style="yellow", justify="right")
        table.add_column("Auth", style="magenta")
        table.add_column("SSH Key", style="dim")

        for server in servers:
            auth_display = "Key" if server.auth_method == "key" else "Password"

            if server.auth_method == "key" and server.ssh_key_path:
                key_display = str(server.ssh_key_path)
                if len(key_display) > 40:
                    key_display = "..." + key_display[-37:]
            else:
                key_display = "-"

            table.add_row(
                server.hostname, server.username, str(server.port),
                auth_display, key_display
            )

        console.print(table)

    def _discover_all_servers(self, servers: List[ServerCredentials]) -> List[ServerInfo]:
        """Discover containers on all servers with progress tracking."""
        server_info_list = []

        for server in track(
            servers, description="[cyan]Scanning servers...[/cyan]", console=console
        ):
            info = self._discover_server(server)
            server_info_list.append(info)

        return server_info_list

    def _discover_server(self, server_creds: ServerCredentials) -> ServerInfo:
        """Discover containers on a single server."""
        info = ServerInfo(credentials=server_creds)

        try:
            # Build SSH connection kwargs based on auth method
            ssh_kwargs = {
                "hostname": server_creds.hostname,
                "username": server_creds.username,
                "port": server_creds.port,
            }

            if server_creds.auth_method == "password":
                server_key = f"{server_creds.hostname}:{server_creds.port}"
                password = self._passwords.get(server_key)
                if not password:
                    info.connection_status = "ssh_failed"
                    info.error_message = "No password provided"
                    console.print(f"  [red]{server_creds.hostname}: No password available[/red]")
                    return info
                ssh_kwargs["password"] = password
            else:
                ssh_kwargs["key_path"] = server_creds.ssh_key_path

            ssh = SSHConnectionManager(**ssh_kwargs)

            # Connect and discover
            with ssh.connect():
                discovery = DockerDiscoveryService(ssh)
                stacks, standalone = discovery.discover_containers()

                info.docker_stacks = stacks
                info.standalone_containers = standalone
                info.connection_status = "success"

        except SSHConnectionError as e:
            info.connection_status = "ssh_failed"
            info.error_message = str(e)
            console.print(f"  [red]{server_creds.hostname}: SSH connection failed[/red]")

        except DockerNotFoundError as e:
            info.connection_status = "no_docker"
            info.error_message = str(e)
            console.print(f"  [yellow]{server_creds.hostname}: Docker not found[/yellow]")

        except Exception as e:
            info.connection_status = "failed"
            info.error_message = str(e)
            console.print(f"  [red]{server_creds.hostname}: {e}[/red]")

        return info

    def _display_summary(self, servers: List[ServerInfo]) -> None:
        """Display discovery summary."""
        console.print("\n[bold green]Discovery Summary[/bold green]\n")

        total_servers = len(servers)
        successful_servers = sum(1 for s in servers if s.is_connected)
        total_containers = sum(s.total_containers for s in servers)
        total_stacks = sum(len(s.docker_stacks) for s in servers)

        # Overall stats
        console.print(f"[bold]Servers:[/bold] {successful_servers}/{total_servers} connected")
        console.print(f"[bold]Total Containers:[/bold] {total_containers}")
        console.print(f"[bold]Docker Stacks:[/bold] {total_stacks}\n")

        # Per-server details
        for server in servers:
            if server.is_connected:
                status_icon = "[green]●[/green]"
                status_text = f"{len(server.docker_stacks)} stacks, {len(server.standalone_containers)} standalone, {server.total_containers} total"
            else:
                status_icon = "[red]●[/red]"
                status_text = f"[dim]{server.connection_status}[/dim]"

            console.print(f"{status_icon} [bold]{server.credentials.hostname}[/bold]: {status_text}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="infra-mapper",
        description="Discover and visualize Docker containers across servers",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to custom servers.yaml config file",
    )
    args = parser.parse_args()

    app = InfraMapper(config_path=args.config)
    app.run()


if __name__ == "__main__":
    main()
