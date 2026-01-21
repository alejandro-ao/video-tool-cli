"""Rich UI helpers for video-tool CLI.

Provides consistent formatting for CLI output:
- Spinners for long-running operations
- Step headers and completion messages
- Pipeline progress panels
- Interactive prompts
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import questionary
from questionary import Style as QStyle
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.status import Status
from rich.table import Table

# Singleton console instance
console = Console()

# Style for questionary prompts (matches Rich cyan theme)
CHOICE_STYLE = QStyle([
    ("qmark", "fg:cyan bold"),
    ("question", "fg:cyan bold"),
    ("pointer", "fg:cyan bold"),
    ("highlighted", "fg:cyan bold"),
    ("selected", "fg:green"),
])


@contextmanager
def status_spinner(message: str) -> Iterator[Status]:
    """Context manager for a spinner during long operations.

    Usage:
        with status_spinner("Processing"):
            do_something_slow()
    """
    with console.status(f"[cyan]{message}[/cyan]") as status:
        yield status


def step_start(name: str, details: Optional[Dict[str, str]] = None) -> None:
    """Print a step header with optional details.

    Args:
        name: Name of the step (e.g., "Concatenating videos")
        details: Optional dict of key-value details to display
    """
    console.print(f"\n[bold cyan]{name}[/bold cyan]")
    if details:
        for key, value in details.items():
            console.print(f"  [dim]{key}:[/dim] {value}")


def step_complete(message: str, output_path: Optional[str | Path] = None) -> None:
    """Print step completion with optional output path.

    Args:
        message: Completion message
        output_path: Optional path to the generated output
    """
    console.print(f"[green]{message}[/green]")
    if output_path:
        console.print(f"  [dim]Output:[/dim] {output_path}")


def step_error(message: str, details: Optional[str] = None) -> None:
    """Print an error message.

    Args:
        message: Error message
        details: Optional additional details
    """
    console.print(f"[bold red]Error:[/bold red] {message}")
    if details:
        console.print(f"  [dim]{details}[/dim]")


def step_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]Warning:[/yellow] {message}")


def step_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[cyan]Info:[/cyan] {message}")


def pipeline_header(title: str, config: Dict[str, Any]) -> None:
    """Print a pipeline configuration panel.

    Args:
        title: Pipeline title
        config: Configuration dictionary to display
    """
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="dim")
    table.add_column("Value")

    for key, value in config.items():
        table.add_row(key, str(value))

    panel = Panel(table, title=f"[bold]{title}[/bold]", border_style="cyan")
    console.print(panel)


def pipeline_step(num: int, total: int, description: str) -> None:
    """Print a pipeline step indicator.

    Args:
        num: Current step number
        total: Total number of steps
        description: Step description
    """
    console.print(f"\n[bold]Step {num}/{total}:[/bold] {description}")


def pipeline_complete(output_dir: str | Path, artifacts: List[str]) -> None:
    """Print a pipeline completion summary panel.

    Args:
        output_dir: Output directory path
        artifacts: List of generated artifact filenames
    """
    content = f"[bold]Output:[/bold] {output_dir}\n\n[bold]Artifacts:[/bold]"
    for artifact in artifacts:
        content += f"\n  [green]{artifact}[/green]"

    panel = Panel(content, title="[bold green]Pipeline Complete[/bold green]", border_style="green")
    console.print(panel)


def pipeline_error(message: str, step: Optional[str] = None) -> None:
    """Print a pipeline error panel.

    Args:
        message: Error message
        step: Optional step name where error occurred
    """
    content = message
    if step:
        content = f"[bold]Step:[/bold] {step}\n\n{content}"

    panel = Panel(content, title="[bold red]Pipeline Failed[/bold red]", border_style="red")
    console.print(panel)


# --- Prompt helpers ---


def normalize_path(raw: str) -> str:
    """Normalize shell-style input paths (quotes / escaped spaces)."""
    trimmed = raw.strip()
    # Remove surrounding quotes if present
    if trimmed.startswith('"') and trimmed.endswith('"'):
        trimmed = trimmed[1:-1]
    elif trimmed.startswith("'") and trimmed.endswith("'"):
        trimmed = trimmed[1:-1]
    # Handle escaped spaces (shell passes these literally)
    trimmed = trimmed.replace("\\ ", " ")
    # Expand user home directory and resolve to absolute path
    return str(Path(trimmed).expanduser().resolve())


def ask_path(prompt_text: str, required: bool = True) -> Optional[str]:
    """Prompt for a filesystem path.

    Args:
        prompt_text: Prompt text to display
        required: If True, loop until a value is provided

    Returns:
        Normalized path string, or None if not required and blank
    """
    while True:
        suffix = "" if required else " [dim](optional)[/dim]"
        response = Prompt.ask(f"[bold cyan]{prompt_text}[/bold cyan]{suffix}", console=console)

        if not response or not response.strip():
            if not required:
                return None
            console.print("[yellow]Please provide a path.[/yellow]")
            continue

        return normalize_path(response)


def ask_text(prompt_text: str, required: bool = True, default: Optional[str] = None) -> Optional[str]:
    """Prompt for text input.

    Args:
        prompt_text: Prompt text to display
        required: If True, loop until a value is provided
        default: Default value to use if blank

    Returns:
        Input string, or None if not required and blank
    """
    while True:
        if default:
            response = Prompt.ask(
                f"[bold cyan]{prompt_text}[/bold cyan]",
                default=default,
                console=console,
            ).strip()
        else:
            suffix = "" if required else " [dim](optional)[/dim]"
            response = Prompt.ask(
                f"[bold cyan]{prompt_text}[/bold cyan]{suffix}",
                console=console,
            ).strip()

        if response:
            return response
        if default:
            return default
        if not required:
            return None
        console.print("[yellow]Please provide a value.[/yellow]")


def ask_confirm(prompt_text: str, default: bool = False) -> bool:
    """Prompt for a yes/no confirmation.

    Args:
        prompt_text: Prompt text to display
        default: Default value if user just presses enter

    Returns:
        True for yes, False for no
    """
    return Confirm.ask(f"[bold cyan]{prompt_text}[/bold cyan]", default=default, console=console)


def ask_choice(prompt_text: str, choices: List[str], default: Optional[str] = None) -> str:
    """Prompt for a choice using arrow-key navigation.

    Args:
        prompt_text: Prompt text to display
        choices: List of valid choices
        default: Default choice if blank

    Returns:
        Selected choice (lowercased)
    """
    result = questionary.select(
        prompt_text,
        choices=choices,
        default=default,
        style=CHOICE_STYLE,
        use_arrow_keys=True,
        use_jk_keys=True,
    ).ask()

    if result is None:
        raise KeyboardInterrupt()

    return result.lower()
