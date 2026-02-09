"""HTML generator for infrastructure visualization."""

from datetime import datetime
from html import escape
from pathlib import Path
from typing import List

from ..models.server import ServerInfo
from ..models.docker_stack import DockerStack
from ..models.container import Container


class HtmlGenerator:
    """Generates HTML tables with inline CSS from infrastructure data.

    Produces an HTML content fragment (no <html>/<head>/<body> wrapper)
    suitable for pasting into any WYSIWYG documentation editor or
    pushing via REST API.
    """

    # Inline styles -- many platforms strip <style> blocks, so everything must be inline
    STYLES = {
        "table": (
            "border-collapse: collapse; width: 100%; margin-bottom: 20px; "
            "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; "
            "font-size: 14px; color: #333; background-color: #fff;"
        ),
        "th": (
            "background-color: #e8e8e8; border: 1px solid #ccc; padding: 10px 14px; "
            "text-align: left; font-weight: 600; color: #222;"
        ),
        "td": "border: 1px solid #ddd; padding: 8px 14px; color: #333; background-color: #fff;",
        "td_alt": "border: 1px solid #ddd; padding: 8px 14px; color: #333; background-color: #f5f5f5;",
        "h1": "color: #2196f3; margin-bottom: 4px;",
        "h2_ok": "color: #42a5f5; margin-top: 28px;",
        "h2_fail": "color: #ef5350; margin-top: 28px;",
        "h3_stack": "color: #ffa726; margin-top: 18px; margin-bottom: 6px;",
        "h3_standalone": "color: #ab47bc; margin-top: 18px; margin-bottom: 6px;",
        "port_link": "color: #e91e63; text-decoration: none; font-weight: 500;",
        "timestamp": "color: #999; font-size: 13px;",
    }

    def generate(self, servers: List[ServerInfo]) -> str:
        """Generate HTML content fragment from server information.

        Args:
            servers: List of server information objects

        Returns:
            HTML content fragment as string
        """
        parts: List[str] = []

        parts.append(f'<h1 style="{self.STYLES["h1"]}">Docker Infrastructure Map</h1>')
        parts.append(
            f'<p style="{self.STYLES["timestamp"]}"><em>Generated on {self._get_timestamp()}</em></p>'
        )

        for server in servers:
            hostname = escape(server.credentials.hostname)

            if server.connection_status != "success":
                parts.append(
                    f'<h2 style="{self.STYLES["h2_fail"]}">&#x1F5A5;&#xFE0F; {hostname} (failed)</h2>'
                )
                if server.error_message:
                    parts.append(f"<p><em>{escape(server.error_message)}</em></p>")
                continue

            parts.append(
                f'<h2 style="{self.STYLES["h2_ok"]}">&#x1F5A5;&#xFE0F; {hostname}</h2>'
            )

            # Stacks
            for stack in server.docker_stacks:
                parts.extend(self._generate_stack_table(hostname, stack))

            # Standalone containers
            if server.standalone_containers:
                parts.extend(
                    self._generate_standalone_table(hostname, server.standalone_containers)
                )

        return "\n".join(parts)

    def _generate_stack_table(self, hostname: str, stack: DockerStack) -> List[str]:
        """Generate an HTML table for a Docker Compose stack."""
        parts: List[str] = []
        safe_name = escape(stack.project_name)

        parts.append(
            f'<h3 style="{self.STYLES["h3_stack"]}">&#x1F4E6; Stack: {safe_name}</h3>'
        )
        parts.append(self._build_table(hostname, stack.containers))

        return parts

    def _generate_standalone_table(
        self, hostname: str, containers: List[Container]
    ) -> List[str]:
        """Generate an HTML table for standalone containers."""
        parts: List[str] = []

        parts.append(
            f'<h3 style="{self.STYLES["h3_standalone"]}">&#x1F433; Standalone Containers</h3>'
        )
        parts.append(self._build_table(hostname, containers))

        return parts

    def _build_table(self, hostname: str, containers: List[Container]) -> str:
        """Build an HTML table for a list of containers."""
        rows: List[str] = []

        rows.append(f'<table style="{self.STYLES["table"]}">')
        rows.append("  <thead>")
        rows.append("    <tr>")
        rows.append(f'      <th style="{self.STYLES["th"]}">Container</th>')
        rows.append(f'      <th style="{self.STYLES["th"]}">Image</th>')
        rows.append(f'      <th style="{self.STYLES["th"]}">Ports</th>')
        rows.append("    </tr>")
        rows.append("  </thead>")
        rows.append("  <tbody>")

        for idx, container in enumerate(containers):
            td_style = self.STYLES["td_alt"] if idx % 2 else self.STYLES["td"]
            safe_name = escape(container.name)
            safe_image = escape(container.image)

            port_parts = self._format_ports(hostname, container)
            ports_html = port_parts if port_parts else "&mdash;"

            rows.append("    <tr>")
            rows.append(f'      <td style="{td_style}">{safe_name}</td>')
            rows.append(f'      <td style="{td_style}">{safe_image}</td>')
            rows.append(f'      <td style="{td_style}">{ports_html}</td>')
            rows.append("    </tr>")

        rows.append("  </tbody>")
        rows.append("</table>")

        return "\n".join(rows)

    def _format_ports(self, hostname: str, container: Container) -> str:
        """Format port mappings as clickable links, deduplicating IPv4/IPv6."""
        seen: dict[str, str] = {}

        for port in container.ports:
            port_key = f"{port.host_port}_{port.container_port}_{port.protocol}"
            if port_key in seen:
                continue

            protocol = "https" if port.host_port == 443 else "http"
            url = f"{protocol}://{escape(hostname)}:{port.host_port}"
            display = f"{port.host_port} &rarr; {port.container_port}/{escape(port.protocol)}"

            seen[port_key] = (
                f'<a href="{url}" style="{self.STYLES["port_link"]}">{display}</a>'
            )

        return "<br>".join(seen.values())

    def save_to_file(
        self, content: str, filename: str = "infrastructure.html", output_dir: Path = None
    ) -> Path:
        """Save HTML content to file.

        Args:
            content: HTML content fragment
            filename: Output filename (default: infrastructure.html)
            output_dir: Output directory (default: current directory)

        Returns:
            Path to saved file
        """
        if output_dir is None:
            output_path = Path(filename)
        else:
            output_path = Path(output_dir) / filename

        output_path.write_text(content, encoding="utf-8")
        return output_path

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp in readable format."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def __str__(self) -> str:
        return "HtmlGenerator"

    def __repr__(self) -> str:
        return "HtmlGenerator()"
