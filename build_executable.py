"""Build standalone executable using PyInstaller."""

import subprocess
import sys
import platform


def build():
    """Build infra-mapper as a standalone single-file executable."""
    name = "infra-mapper"
    entry_point = "src/infra_mapper/__main__.py"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", name,
        "--clean",
        "--noconfirm",
        # Hidden imports that PyInstaller may miss during static analysis
        "--hidden-import", "paramiko",
        "--hidden-import", "pydantic",
        "--hidden-import", "pydantic.deprecated.decorator",
        "--hidden-import", "yaml",
        "--hidden-import", "rich",
        "--hidden-import", "rich.console",
        "--hidden-import", "rich.prompt",
        "--hidden-import", "rich.table",
        "--hidden-import", "rich.panel",
        "--hidden-import", "rich.progress",
        entry_point,
    ]

    print(f"Building {name} for {platform.system()}...")
    subprocess.run(cmd, check=True)

    if platform.system() == "Windows":
        binary_path = f"dist\\{name}.exe"
    else:
        binary_path = f"dist/{name}"

    print(f"\nBuild complete! Binary at: {binary_path}")


if __name__ == "__main__":
    build()
