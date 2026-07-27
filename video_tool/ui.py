"""Rich UI helpers for video-tool CLI.

Provides consistent formatting for CLI output:
- Spinners for long-running operations
- Step headers and completion messages
- Pipeline progress panels
- Interactive prompts
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import questionary
from questionary import Style as QStyle
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.status import Status

# Singleton console instance
console = Console()

# Style for questionary prompts (matches Rich cyan theme)
CHOICE_STYLE = QStyle(
    [
        ("qmark", "fg:cyan bold"),
        ("question", "fg:cyan bold"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "fg:cyan bold"),
        ("selected", "fg:green"),
    ]
)


@contextmanager
def status_spinner(message: str) -> Iterator[Status]:
    """Context manager for a spinner during long operations.

    Usage:
        with status_spinner("Processing"):
            do_something_slow()
    """
    with console.status(f"[cyan]{message}[/cyan]") as status:
        yield status


def step_start(name: str, details: dict[str, str] | None = None) -> None:
    """Print a step header with optional details.

    Args:
        name: Name of the step (e.g., "Concatenating videos")
        details: Optional dict of key-value details to display
    """
    console.print(f"\n[bold cyan]{name}[/bold cyan]")
    if details:
        for key, value in details.items():
            console.print(f"  [dim]{key}:[/dim] {value}")


def step_complete(message: str, output_path: str | Path | None = None) -> None:
    """Print step completion with optional output path.

    Args:
        message: Completion message
        output_path: Optional path to the generated output
    """
    console.print(f"[green]{message}[/green]")
    if output_path:
        console.print(f"  [dim]Output:[/dim] {output_path}")


def step_error(message: str, details: str | None = None) -> None:
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


# --- Prompt helpers ---


def normalize_path(raw: str) -> str:
    """Normalize shell-style path input without changing relative-path semantics.

    This strips common shell quoting/escaping and expands ``~``. It intentionally
    does not call ``resolve()`` so callers can preserve standard current-working-
    directory semantics for relative paths.
    """
    trimmed = raw.strip()
    # Remove surrounding quotes if present
    if trimmed.startswith('"') and trimmed.endswith('"'):
        trimmed = trimmed[1:-1]
    elif trimmed.startswith("'") and trimmed.endswith("'"):
        trimmed = trimmed[1:-1]
    # Handle escaped spaces (shell passes these literally)
    trimmed = trimmed.replace("\\ ", " ")
    # Expand user home directory but preserve relative paths
    return str(Path(trimmed).expanduser())


def ask_path(prompt_text: str, required: bool = True) -> str | None:
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


def ask_text(prompt_text: str, required: bool = True, default: str | None = None) -> str | None:
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


def ask_choice(prompt_text: str, choices: list[str], default: str | None = None) -> str:
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
