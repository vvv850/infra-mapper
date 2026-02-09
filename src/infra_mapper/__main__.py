"""Main entry point for the Infrastructure Mapper CLI application."""

import sys
from pathlib import Path
from typing import List

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

    def __init__(self):
        """Initialize the Infrastructure Mapper application."""
        self.config_manager = ConfigManager()
        self.generator = MermaidGenerator()

    def run(self) -> None:
        """Main execution flow."""
        try:
            # Display banner
            console.print(
                Panel.fit(
                    "[bold cyan]🐳 Docker Infrastructure Mapper[/bold cyan]\n"
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

            console.print(f"\n[green]✓ Diagram saved to {saved_path}[/green]")
            console.print("\n[bold]Diagram Preview:[/bold]")
            console.print(diagram)

            console.print(
                f"\n[dim]Open {saved_path} in a Markdown viewer to see the rendered diagram[/dim]"
            )

        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ Operation cancelled by user[/yellow]")
            sys.exit(0)
        except InfraMapperError as e:
            console.print(f"\n[red]✗ Error: {e}[/red]")
            sys.exit(1)
        except Exception as e:
            console.print(f"\n[red]✗ Unexpected error: {e}[/red]")
            sys.exit(1)

    def _get_server_configurations(self) -> List[ServerCredentials]:
        """Get server configurations from user or config file."""
        # Check for saved configuration
        if self.config_manager.config_exists():
            use_saved = Confirm.ask(
                "[cyan]Found saved configuration. Use it?[/cyan]", default=True
            )

            if use_saved:
                try:
                    servers = self.config_manager.load_servers()
                    if servers:
                        console.print("[green]✓ Loaded saved configuration[/green]\n")
                        return servers
                except Exception as e:
                    console.print(f"[yellow]⚠ Failed to load saved config: {e}[/yellow]")
                    console.print("[yellow]Starting fresh configuration...[/yellow]\n")

        # Prompt for new configuration
        servers = self._prompt_servers()

        # Offer to save configuration
        if servers:
            save_config = Confirm.ask(
                "\n[cyan]Save server configuration for future use?[/cyan]", default=True
            )

            if save_config:
                try:
                    self.config_manager.save_servers(servers)
                    console.print("[green]✓ Configuration saved[/green]\n")
                except Exception as e:
                    console.print(f"[yellow]⚠ Failed to save config: {e}[/yellow]\n")

        return servers

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

            # Prompt for SSH key with validation loop
            key_path = None
            default_key = str(Path.home() / ".ssh" / "id_rsa")

            while key_path is None:
                key_path_str = Prompt.ask(
                    "[cyan]SSH private key path[/cyan]", default=default_key
                )
                temp_key_path = Path(key_path_str).expanduser()

                # Validate key exists
                if not temp_key_path.exists():
                    console.print(f"[red]✗ SSH key not found: {temp_key_path}[/red]")
                    retry = Confirm.ask("Try a different key?", default=True)
                    if not retry:
                        # User doesn't want to retry, skip this server
                        console.print("[yellow]Skipping this server[/yellow]\n")
                        break
                    # Loop continues to re-ask for key path
                else:
                    key_path = temp_key_path

            # If key_path is still None, user chose to skip this server
            if key_path is None:
                continue

            # Create server credentials
            try:
                server = ServerCredentials(
                    hostname=hostname, username=username, ssh_key_path=key_path, port=port
                )
                servers.append(server)
                console.print(f"[green]✓ Added {hostname}[/green]\n")
            except Exception as e:
                console.print(f"[red]✗ Failed to add server: {e}[/red]\n")

        return servers

    def _display_servers_table(self, servers: List[ServerCredentials]) -> None:
        """Display configured servers in a formatted table."""
        table = Table(title="Configured Servers", show_header=True, header_style="bold cyan")

        table.add_column("Hostname", style="cyan", no_wrap=True)
        table.add_column("Username", style="green")
        table.add_column("Port", style="yellow", justify="right")
        table.add_column("SSH Key", style="magenta")

        for server in servers:
            # Truncate key path for display
            key_display = str(server.ssh_key_path)
            if len(key_display) > 40:
                key_display = "..." + key_display[-37:]

            table.add_row(server.hostname, server.username, str(server.port), key_display)

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
            # Create SSH connection
            ssh = SSHConnectionManager(
                hostname=server_creds.hostname,
                username=server_creds.username,
                key_path=server_creds.ssh_key_path,
                port=server_creds.port,
            )

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
            console.print(f"  [red]✗ {server_creds.hostname}: SSH connection failed[/red]")

        except DockerNotFoundError as e:
            info.connection_status = "no_docker"
            info.error_message = str(e)
            console.print(f"  [yellow]⚠ {server_creds.hostname}: Docker not found[/yellow]")

        except Exception as e:
            info.connection_status = "failed"
            info.error_message = str(e)
            console.print(f"  [red]✗ {server_creds.hostname}: {e}[/red]")

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
    app = InfraMapper()
    app.run()


if __name__ == "__main__":
    main()
