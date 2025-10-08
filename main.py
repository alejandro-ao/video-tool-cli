import argparse
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

from dotenv import load_dotenv
from loguru import logger
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from video_tool import VideoProcessor

console = Console()
T = TypeVar("T")
CONSOLE_SINK_ID: Optional[int] = None

ASCII_BANNER = r"""


    @@@@@@@@@@@@@@@         @@        __     __  __        __                            ________                    __ 
  @@@@           @@@@    @@@@@      |  \   |  \|  \      |  \                          |        \                  |  \
  @@ @@@@@        @@@ @@@@@ @@      | $$   | $$ \$$  ____| $$  ______    ______         \$$$$$$$$______    ______  | $$
  @@ @@@          @@@@@@    @@      | $$   | $$|  \ /      $$ /      \  /      \          | $$  /      \  /      \ | $$
  @@              @@@@@@    @@       \$$\ /  $$| $$|  $$$$$$$|  $$$$$$\|  $$$$$$\         | $$ |  $$$$$$\|  $$$$$$\| $$
  @@              @@@@@@    @@        \$$\  $$ | $$| $$  | $$| $$    $$| $$  | $$         | $$ | $$  | $$| $$  | $$| $$
  @@           @@ @@@@@@    @@         \$$ $$  | $$| $$__| $$| $$$$$$$$| $$__/ $$         | $$ | $$__/ $$| $$__/ $$| $$
  @@        @@@@@ @@@ @@@@@ @@          \$$$   | $$ \$$    $$ \$$     \ \$$    $$         | $$  \$$    $$ \$$    $$| $$
  @@@@           @@@@    @@@@@           \$     \$$  \$$$$$$$  \$$$$$$$  \$$$$$$           \$$   \$$$$$$   \$$$$$$  \$$
    @@@@@@@@@@@@@@@         @@                                                                                         


"""


def get_config_dir() -> Path:
    """Determine the platform-appropriate configuration directory."""
    if sys.platform == "win32":
        base = Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "video-tool"


CONFIG_DIR = get_config_dir()
PROFILES_FILE = CONFIG_DIR / "profiles.json"

DEFAULT_PARAMS: Dict[str, Any] = {
    "input_dir": None,
    "repo_url": None,
    "video_title": None,
    "skip_silence_removal": False,
    "skip_concat": False,
    "skip_reprocessing": False,
    "skip_timestamps": False,
    "skip_transcript": False,
    "skip_context_cards": False,
    "skip_description": False,
    "skip_seo": False,
    "skip_linkedin": False,
    "skip_twitter": False,
    "skip_bunny_video_upload": True,
    "skip_bunny_chapter_upload": True,
    "skip_bunny_transcript_upload": True,
    "bunny_library_id": None,
    "bunny_collection_id": None,
    "bunny_caption_language": "en",
    "bunny_video_id": None,
    "verbose_logging": False,
}


class StepFlagSpec:
    """Metadata describing CLI toggles for specific processing steps."""

    def __init__(self, cli_name: str, skip_key: str, help_text: str):
        self.cli_name = cli_name
        self.skip_key = skip_key
        self.help_text = help_text

    @property
    def attr(self) -> str:
        return self.cli_name.replace("-", "_")


STEP_FLAG_SPECS: List[StepFlagSpec] = [
    StepFlagSpec("silence-removal", "skip_silence_removal", "Run silence removal."),
    StepFlagSpec("concat", "skip_concat", "Run video concatenation."),
    StepFlagSpec("timestamps", "skip_timestamps", "Generate timestamps."),
    StepFlagSpec("transcript", "skip_transcript", "Generate transcript."),
    StepFlagSpec("context-cards", "skip_context_cards", "Generate context cards."),
    StepFlagSpec("description", "skip_description", "Draft video description."),
    StepFlagSpec("seo", "skip_seo", "Generate SEO keyword suggestions."),
    StepFlagSpec("linkedin", "skip_linkedin", "Draft LinkedIn copy."),
    StepFlagSpec("twitter", "skip_twitter", "Draft Twitter/X copy."),
    StepFlagSpec("bunny-video", "skip_bunny_video_upload", "Upload video to Bunny.net."),
    StepFlagSpec(
        "bunny-chapters",
        "skip_bunny_chapter_upload",
        "Upload chapter markers to Bunny.net.",
    ),
    StepFlagSpec(
        "bunny-transcript",
        "skip_bunny_transcript_upload",
        "Upload transcript captions to Bunny.net.",
    ),
]


def load_profiles() -> Dict[str, Dict[str, Any]]:
    """Load persisted profile configurations."""
    if not PROFILES_FILE.exists():
        return {}

    try:
        with PROFILES_FILE.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(f"Unable to read saved profiles: {exc}")
        return {}

    if not isinstance(raw, dict):
        logger.warning("Profiles file is malformed; ignoring.")
        return {}

    profiles: Dict[str, Dict[str, Any]] = {}
    for name, data in raw.items():
        if not isinstance(data, dict):
            continue
        cleaned = {
            key: value
            for key, value in data.items()
            if key in DEFAULT_PARAMS
            and key not in {"input_dir", "repo_url", "video_title"}
        }
        profiles[str(name)] = cleaned
    return profiles


def save_profiles(profiles: Dict[str, Dict[str, Any]]) -> None:
    """Persist the provided profile collection."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with PROFILES_FILE.open("w", encoding="utf-8") as handle:
        json.dump(profiles, handle, indent=2)


def resolve_profile(name: str) -> Optional[Dict[str, Any]]:
    """Return the configuration for a saved profile name (case insensitive)."""
    profiles = load_profiles()
    for stored_name, data in profiles.items():
        if stored_name.lower() == name.lower():
            return {
                key: value
                for key, value in data.items()
                if key in DEFAULT_PARAMS
            }
    return None


def apply_default_settings(overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Merge overrides with CLI defaults."""
    merged = DEFAULT_PARAMS.copy()
    merged.update({key: overrides[key] for key in overrides if key in merged})
    return merged


def apply_cli_overrides(params: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    """Apply non-interactive CLI toggles to the run configuration."""
    if getattr(args, "skip_all", False):
        for key in params:
            if key.startswith("skip_") and key != "skip_reprocessing":
                params[key] = True

    for spec in STEP_FLAG_SPECS:
        if getattr(args, spec.attr, False):
            params[spec.skip_key] = False

    return params


def ensure_video_title(params: Dict[str, Any]) -> bool:
    """Ensure a video title is present, prompting the user if necessary."""
    if params.get("video_title"):
        return True

    if sys.stdin and sys.stdin.isatty():
        console.print("[yellow]Video title is required for this run.[/]")
        params["video_title"] = ask_required_text("Video title")
        return True

    console.print(
        "[bold red]Video title required.[/] "
        "Provide it via --manual, --profile, or CLI overrides."
    )
    logger.error("Missing video title for non-interactive run.")
    return False


def ensure_repo_url(params: Dict[str, Any]) -> bool:
    """Make sure a repository URL is available when description generation runs."""
    if params.get("skip_description", False):
        return True

    if params.get("repo_url"):
        return True

    if sys.stdin and sys.stdin.isatty():
        console.print(
            "[yellow]Description generation requires a repository URL.[/]"
        )
        params["repo_url"] = ask_required_text("Repository URL")
        return True

    console.print(
        "[bold red]Repository URL required for description generation.[/]\n"
        "Provide it via --manual, --profile, or the profiles file."
    )
    logger.error("Missing repository URL while description generation is enabled.")
    return False


def prompt_save_profile(params: Dict[str, Any]) -> None:
    """Offer to persist the current configuration for future runs."""
    # Avoid interactive prompts when stdin is not a TTY (e.g., tests/CI)
    if not (sys.stdin and sys.stdin.isatty()):
        return

    profiles = load_profiles()
    if not Confirm.ask(
        "Save this configuration for future runs?",
        default=False,
        console=console,
    ):
        return

    while True:
        profile_name = (
            Prompt.ask("[bold cyan]Profile name[/]", console=console).strip()
        )
        if not profile_name:
            console.print("[yellow]Please choose a non-empty profile name.[/]")
            continue

        existing = next(
            (
                stored_name
                for stored_name in profiles
                if stored_name.lower() == profile_name.lower()
            ),
            None,
        )
        if existing and not Confirm.ask(
            f"Profile '{existing}' exists. Overwrite?",
            default=False,
            console=console,
        ):
            continue

        profiles[existing or profile_name] = {
            key: params.get(key)
            for key in DEFAULT_PARAMS
            if key not in {"input_dir", "repo_url", "video_title"}
        }
        save_profiles(profiles)
        console.print(f"[green]Saved profile[/] -> {existing or profile_name}")
        break


def parse_cli_args() -> argparse.Namespace:
    """Parse CLI arguments for run configuration."""
    parser = argparse.ArgumentParser(description="Video tool orchestrator.")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        help="Subcommand to execute (only 'run' is currently supported).",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Run in interactive mode to configure all options.",
    )
    parser.add_argument(
        "--profile",
        type=str,
        help="Load configuration from a saved profile.",
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        help="Override input directory when running non-interactively.",
    )
    parser.add_argument(
        "--skip-all",
        action="store_true",
        help="Skip every optional processing step unless explicitly re-enabled.",
    )
    for spec in STEP_FLAG_SPECS:
        parser.add_argument(
            f"--{spec.cli_name}",
            action="store_true",
            help=spec.help_text + " Overrides --skip-all for this step.",
        )
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    """Configure loguru sinks so console output matches verbosity preference."""
    global CONSOLE_SINK_ID

    console_level = "DEBUG" if verbose else "WARNING"

    if CONSOLE_SINK_ID is None:
        logger.remove()
    else:
        logger.remove(CONSOLE_SINK_ID)

    CONSOLE_SINK_ID = logger.add(
        sys.stderr,
        level=console_level,
        colorize=True,
        enqueue=True,
    )


def display_welcome() -> None:
    """Render an ASCII banner and short tagline."""
    banner = Text(ASCII_BANNER.rstrip("\n"), style="bold cyan")
    console.print(
        Panel(
            banner,
            title="videotool",
            subtitle="capture • craft • share",
            border_style="cyan",
            box=box.ASCII,
        )
    )
    console.print(
        "[bold magenta]Process clips, stitch the story, and publish in minutes.[/]",
        justify="center",
    )
    console.print()


def normalize_path(raw: str) -> str:
    """Normalize shell-style input paths (quotes / escaped spaces)."""
    trimmed = raw.strip()
    if trimmed.startswith('"') and trimmed.endswith('"'):
        trimmed = trimmed[1:-1]
    elif trimmed.startswith("'") and trimmed.endswith("'"):
        trimmed = trimmed[1:-1]
    return trimmed.replace("\\ ", " ")


def ask_required_path(prompt_text: str) -> str:
    """Prompt until a non-empty path-like value is provided."""
    while True:
        response = Prompt.ask(
            f"[bold cyan]{prompt_text}[/]",
            console=console,
        )
        normalized = normalize_path(response)
        if normalized:
            return normalized
        console.print("[yellow]Please provide a value.[/]")


def ask_optional_text(prompt_text: str) -> Optional[str]:
    """Prompt for optional text input."""
    response = Prompt.ask(
        f"[bold cyan]{prompt_text}[/] ([dim]optional[/])",
        default="",
        show_default=False,
        console=console,
    ).strip()
    return response or None


def ask_required_text(prompt_text: str) -> str:
    """Prompt until a non-empty text value is provided."""
    while True:
        response = (
            Prompt.ask(f"[bold cyan]{prompt_text}[/]", console=console)
            .strip()
        )
        if response:
            return response
        console.print("[yellow]Please provide a value.[/]")


def summarize_configuration(data: Dict[str, Any]) -> None:
    """Show the user a quick overview of their selections."""
    summary = Table(box=box.ASCII, show_header=False, pad_edge=False)
    summary.add_row("Input directory", str(Path(data["input_dir"]).expanduser()))
    summary.add_row("Repository URL", data["repo_url"] or "—")
    summary.add_row("Video title", data["video_title"] or "—")
    summary.add_row("Silence removal", "run" if not data["skip_silence_removal"] else "skip")
    summary.add_row("Concatenation", "run" if not data["skip_concat"] else "skip")
    if not data["skip_concat"]:
        summary.add_row(
            "Fast concatenation",
            "enabled" if data["skip_reprocessing"] else "standard",
        )
    summary.add_row("Timestamps", "run" if not data["skip_timestamps"] else "skip")
    summary.add_row("Transcript", "run" if not data["skip_transcript"] else "skip")
    summary.add_row(
        "Context cards",
        "run" if not data["skip_context_cards"] else "skip",
    )
    description_label = "run" if not data["skip_description"] else "skip"
    if description_label == "run" and not data["repo_url"]:
        description_label = "run (requires repo URL)"
    summary.add_row("Description", description_label)
    summary.add_row("SEO keywords", "run" if not data["skip_seo"] else "skip")
    summary.add_row("LinkedIn copy", "run" if not data["skip_linkedin"] else "skip")
    summary.add_row("Twitter copy", "run" if not data["skip_twitter"] else "skip")
    bunny_actions_selected = any(
        not data.get(flag, True)
        for flag in (
            "skip_bunny_video_upload",
            "skip_bunny_chapter_upload",
            "skip_bunny_transcript_upload",
        )
    )
    summary.add_row(
        "Bunny video",
        "run" if not data.get("skip_bunny_video_upload") else "skip",
    )
    summary.add_row(
        "Bunny chapters",
        "run" if not data.get("skip_bunny_chapter_upload") else "skip",
    )
    summary.add_row(
        "Bunny transcript",
        "run" if not data.get("skip_bunny_transcript_upload") else "skip",
    )
    if bunny_actions_selected:
        library_hint = (
            data.get("bunny_library_id")
            or os.getenv("BUNNY_LIBRARY_ID")
            or "—"
        )
        summary.add_row("Bunny library", library_hint)
        video_id_hint = (
            data.get("bunny_video_id")
            or os.getenv("BUNNY_VIDEO_ID")
            or "—"
        )
        if not data.get("skip_bunny_video_upload") or video_id_hint != "—":
            summary.add_row("Bunny video ID", video_id_hint)
        if not data.get("skip_bunny_transcript_upload", True):
            caption_lang = (
                data.get("bunny_caption_language")
                or os.getenv("BUNNY_CAPTION_LANGUAGE")
                or "en"
            )
            summary.add_row("Bunny captions", caption_lang)
    summary.add_row("Verbose logs", "on" if data.get("verbose_logging") else "off")

    console.print(
        Panel(
            summary,
            title="Run Overview",
            border_style="magenta",
            box=box.ASCII,
        )
    )


def get_user_input() -> Dict[str, Any]:
    """Collect configuration details interactively using explicit skip prompts."""
    console.print("[bold]Let's configure this session.[/]\n")
    input_dir = ask_required_path("Input directory")
    repo_url = ask_optional_text("Repository URL")
    video_title = ask_optional_text("Video title")

    console.print("\n[bold]Processing modules[/]")
    skip_silence_removal = Confirm.ask(
        "Skip silence removal on clips?",
        default=False,
        console=console,
    )
    skip_concat = Confirm.ask(
        "Skip concatenation into a final cut?",
        default=False,
        console=console,
    )

    skip_reprocessing = False
    if not skip_concat:
        skip_reprocessing = Confirm.ask(
            "Use fast concatenation (skip reprocessing step)?",
            default=False,
            console=console,
        )

    skip_timestamps = Confirm.ask(
        "Skip generating timestamps for individual clips?",
        default=False,
        console=console,
    )
    skip_transcript = Confirm.ask(
        "Skip generating a transcript?",
        default=False,
        console=console,
    )
    skip_context_cards = Confirm.ask(
        "Skip identifying context cards and resource mentions?",
        default=False,
        console=console,
    )
    skip_description = Confirm.ask(
        "Skip drafting a video description?",
        default=False,
        console=console,
    )

    if not skip_description and not repo_url:
        console.print(
            "[yellow]A repository URL is required to generate a description.[/]"
        )
        repo_url = ask_required_text("Repository URL")

    # Always prompt for SEO keywords skip, regardless of description selection
    skip_seo = Confirm.ask(
        "Skip including SEO keyword suggestions?",
        default=False,
        console=console,
    )

    skip_linkedin = Confirm.ask(
        "Skip drafting a LinkedIn post?",
        default=False,
        console=console,
    )
    skip_twitter = Confirm.ask(
        "Skip drafting a Twitter/X post?",
        default=False,
        console=console,
    )

    skip_bunny_video_upload = Confirm.ask(
        "Skip uploading the final video to Bunny.net?",
        default=True,
        console=console,
    )

    skip_bunny_chapter_upload = Confirm.ask(
        "Skip uploading chapters to Bunny.net?",
        default=True,
        console=console,
    )

    skip_bunny_transcript_upload = Confirm.ask(
        "Skip uploading transcript captions to Bunny.net?",
        default=True,
        console=console,
    )

    bunny_library_id: Optional[str] = None
    bunny_collection_id: Optional[str] = None
    bunny_caption_language = "en"
    bunny_video_id: Optional[str] = None

    bunny_actions_enabled = not (
        skip_bunny_video_upload
        and skip_bunny_chapter_upload
        and skip_bunny_transcript_upload
    )

    if bunny_actions_enabled:
        bunny_library_id = ask_optional_text(
            "Bunny library ID (leave blank to use BUNNY_LIBRARY_ID env)"
        )
        if not skip_bunny_video_upload:
            bunny_collection_id = ask_optional_text("Bunny collection ID (optional)")
        if skip_bunny_video_upload and (
            not skip_bunny_chapter_upload or not skip_bunny_transcript_upload
        ):
            bunny_video_id = ask_optional_text(
                "Existing Bunny video ID (leave blank to use BUNNY_VIDEO_ID env)"
            )
        if not skip_bunny_transcript_upload:
            bunny_caption_language = (
                Prompt.ask(
                    "[bold cyan]Caption language code for transcript[/] ([dim]default: en[/])",
                    default="en",
                    console=console,
                ).strip()
                or "en"
            )

    console.print("\n[bold]Diagnostics[/]")
    verbose_logging = Confirm.ask(
        "Show detailed log output in the terminal?",
        default=False,
        console=console,
    )

    selections: Dict[str, Any] = {
        "input_dir": input_dir,
        "repo_url": repo_url,
        "video_title": video_title,
        "skip_silence_removal": skip_silence_removal,
        "skip_concat": skip_concat,
        "skip_reprocessing": skip_reprocessing,
        "skip_timestamps": skip_timestamps,
        "skip_transcript": skip_transcript,
        "skip_context_cards": skip_context_cards,
        "skip_description": skip_description,
        "skip_seo": skip_seo,
        "skip_linkedin": skip_linkedin,
        "skip_twitter": skip_twitter,
        "skip_bunny_video_upload": skip_bunny_video_upload,
        "skip_bunny_chapter_upload": skip_bunny_chapter_upload,
        "skip_bunny_transcript_upload": skip_bunny_transcript_upload,
        "bunny_library_id": bunny_library_id,
        "bunny_collection_id": bunny_collection_id,
        "bunny_caption_language": bunny_caption_language,
        "bunny_video_id": bunny_video_id,
        "verbose_logging": verbose_logging,
    }

    console.print()
    summarize_configuration(selections)
    console.print()

    return selections


def validate_environment() -> bool:
    """Ensure required API keys are present."""
    missing = [var for var in ("OPENAI_API_KEY", "GROQ_API_KEY") if not os.getenv(var)]
    if missing:
        missing_list = ", ".join(missing)
        console.print(
            f"[bold red]Missing required environment variables:[/] {missing_list}"
        )
        logger.error(f"Missing required environment variables: {missing_list}")
        return False
    return True


@contextmanager
def stage(message: str):
    """Show a terminal spinner while a stage is running."""
    with console.status(f"[bold blue]{message}[/]", spinner="line"):
        yield


def run_step(message: str, action: Callable[[], T]) -> T:
    """Execute an action while displaying a spinner."""
    logger.info(message)
    with stage(message):
        return action()


def main() -> None:
    load_dotenv()
    args = parse_cli_args()

    if args.command.lower() != "run":
        console.print(f"[bold red]Unsupported command:[/] {args.command}")
        console.print("[cyan]Available command:[/] run")
        return

    if args.manual and args.profile:
        console.print("[bold red]Cannot combine --manual with --profile.[/]")
        return

    configure_logging(verbose=False)
    display_welcome()

    if not validate_environment():
        return

    manual_mode = args.manual
    profile_used: Optional[str] = None

    if manual_mode:
        ignored_flags: List[str] = []
        if getattr(args, "skip_all", False):
            ignored_flags.append("--skip-all")
        ignored_flags.extend(
            f"--{spec.cli_name}"
            for spec in STEP_FLAG_SPECS
            if getattr(args, spec.attr, False)
        )
        if ignored_flags:
            console.print(
                "[yellow]Manual mode ignores non-interactive flags:[/] "
                + ", ".join(ignored_flags)
            )

    try:
        if manual_mode:
            params = get_user_input()
            params = apply_default_settings(params)
            params["input_dir"] = normalize_path(str(params["input_dir"]))
            if not ensure_video_title(params):
                return
            if not ensure_repo_url(params):
                return
        else:
            profile_data: Optional[Dict[str, Any]] = None
            if args.profile:
                profile_used = args.profile
                profile_data = resolve_profile(args.profile)
                if profile_data is None:
                    available_profiles = list(load_profiles().keys())
                    console.print(
                        f"[bold red]Profile not found:[/] {args.profile}"
                    )
                    if available_profiles:
                        console.print(
                            "[cyan]Available profiles:[/] "
                            + ", ".join(sorted(available_profiles))
                        )
                    logger.error(f"Requested profile not found: {args.profile}")
                    return
            else:
                default_profile = resolve_profile("default")
                if default_profile:
                    profile_used = "default"
                    profile_data = default_profile

            params = apply_default_settings(profile_data or {})
            if args.input_dir:
                params["input_dir"] = normalize_path(args.input_dir)

            params = apply_cli_overrides(params, args)

            if not params.get("input_dir"):
                if sys.stdin and sys.stdin.isatty():
                    console.print("[yellow]Input directory is required for this run.[/]")
                    params["input_dir"] = ask_required_path("Input directory")
                else:
                    console.print(
                        "[bold red]Input directory not provided. "
                        "Set --input-dir or save it in the selected profile.[/]"
                    )
                    logger.error("Input directory missing for non-interactive run.")
                    return
            else:
                params["input_dir"] = normalize_path(str(params["input_dir"]))

            if not ensure_video_title(params):
                return
            if not ensure_repo_url(params):
                return

            if profile_used:
                console.print(f"[cyan]Using profile[/] -> {profile_used}")
            else:
                console.print("[cyan]Using default run configuration.[/]")
            console.print()
            summarize_configuration(params)
            console.print()

        configure_logging(params.get("verbose_logging", False))

        input_dir = Path(params["input_dir"]).expanduser().resolve()

        if not input_dir.exists():
            console.print(
                f"[bold red]Input directory does not exist:[/] {input_dir}"
            )
            logger.error(f"Input directory does not exist: {input_dir}")
            return
        if not input_dir.is_dir():
            console.print(f"[bold red]Path is not a directory:[/] {input_dir}")
            logger.error(f"Path is not a directory: {input_dir}")
            return

        processor = VideoProcessor(
            str(input_dir),
            video_title=params["video_title"],
            show_external_logs=params["verbose_logging"],
        )
        logger.info(f"Input directory path: {input_dir}")
        logger.info(f"Output directory path: {processor.output_dir}")

        artifacts: Dict[str, Any] = {}
        timestamps_info: Optional[Dict[str, Any]] = None

        # Remove silences
        if not params["skip_silence_removal"]:
            processed_dir = run_step(
                "🔇 Removing silences from videos...",
                processor.remove_silences,
            )
            logger.info(f"✅ Silences removed. Processed videos in: {processed_dir}")
            console.print(
                f"[green]Silences removed[/] -> {processed_dir}"
            )
            artifacts["Processed clips"] = processed_dir

        # Concatenation
        output_video: Optional[str] = None
        if not params["skip_concat"]:
            output_video = run_step(
                "🎬 Starting video concatenation...",
                lambda: processor.concatenate_videos(
                    skip_reprocessing=params["skip_reprocessing"]
                ),
            )
            if output_video:
                file_size = Path(output_video).stat().st_size / (1024 * 1024)
                logger.info(
                    f"✅ Videos concatenated: {Path(output_video).name} ({file_size:.1f} MB)"
                )
                console.print(
                    f"[green]Videos concatenated[/] -> "
                    f"{Path(output_video).name} ({file_size:.1f} MB)"
                )
                artifacts["Final video"] = output_video
            else:
                logger.warning(
                    "⚠️ Video concatenation completed but no output file returned"
                )
                console.print(
                    "[yellow]Video concatenation completed but no output file returned[/]"
                )

        console.print("\n[bold]Selecting video for downstream tasks[/]")
        logger.info("🎥 Selecting video file for content generation...")
        video_path = output_video

        if not video_path:
            mp4_files = list(processor.output_dir.glob("*.mp4"))
            if not mp4_files:
                mp4_files = list(input_dir.glob("*.mp4"))
            if mp4_files:
                mp4_files_with_size = [(f, f.stat().st_size) for f in mp4_files]
                mp4_files_with_size.sort(key=lambda item: item[1], reverse=True)
                video_path = str(mp4_files_with_size[0][0])
                largest_size = mp4_files_with_size[0][1] / (1024 * 1024)
                logger.info(
                    f"📁 Selected largest MP4: {Path(video_path).name} ({largest_size:.1f} MB)"
                )
                console.print(
                    f"[green]Using video[/] -> "
                    f"{Path(video_path).name} ({largest_size:.1f} MB)"
                )
                artifacts.setdefault("Candidate video", Path(video_path))
            else:
                logger.warning("❌ No video files found for content generation")
                console.print("[yellow]No video files found for content generation[/]")
                video_path = None
        else:
            logger.info(f"📁 Using concatenated video: {Path(video_path).name}")
            console.print(
                f"[green]Using concatenated video[/] -> {Path(video_path).name}"
            )
            artifacts.setdefault("Candidate video", Path(video_path))

        transcript_path: Optional[str] = None
        if not params["skip_transcript"] and video_path:
            transcript_path = run_step(
                "📝 Generating transcript...",
                lambda: processor.generate_transcript(str(video_path)),
            )
            if transcript_path and Path(transcript_path).exists():
                transcript_size = Path(transcript_path).stat().st_size
                logger.info(f"✅ Transcript generated ({transcript_size} bytes)")
                console.print(
                    f"[green]Transcript generated[/] -> "
                    f"{Path(transcript_path).name} ({transcript_size} bytes)"
                )
                artifacts["Transcript"] = transcript_path
            else:
                logger.error("❌ Transcript generation failed")
                console.print("[red]Transcript generation failed[/]")
        elif not params["skip_transcript"]:
            logger.warning("⚠️ Skipping transcript: no video file available")
            console.print("[yellow]Skipping transcript: no video file available[/]")

        resolved_transcript: Optional[Path] = None
        if transcript_path and Path(transcript_path).exists():
            resolved_transcript = Path(transcript_path)
        else:
            default_transcript = processor.output_dir / "transcript.vtt"
            if default_transcript.exists():
                resolved_transcript = default_transcript
                artifacts.setdefault("Transcript", str(default_transcript))

        if not params["skip_timestamps"]:
            timestamps_info = run_step(
                "⏰ Generating timestamps for individual videos...",
                processor.generate_timestamps,
            )
            logger.info("✅ Timestamps generated for all videos")
            console.print("[green]Timestamps generated for all videos[/]")

        bunny_result: Optional[Dict[str, Any]] = None
        upload_bunny_video = not params["skip_bunny_video_upload"]
        upload_bunny_chapters = not params["skip_bunny_chapter_upload"]
        upload_bunny_transcript = not params["skip_bunny_transcript_upload"]

        if upload_bunny_video or upload_bunny_chapters or upload_bunny_transcript:
            if upload_bunny_video and not video_path:
                logger.warning("⚠️ Skipping Bunny video upload: no video file available")
                console.print(
                    "[yellow]Skipping Bunny video upload: no video file available[/]"
                )
            else:
                if upload_bunny_video and (upload_bunny_chapters or upload_bunny_transcript):
                    bunny_message = "🚀 Syncing Bunny.net video and metadata..."
                elif upload_bunny_video:
                    bunny_message = "🚀 Uploading final video to Bunny.net..."
                else:
                    bunny_message = "🛠 Updating Bunny.net metadata..."

                chapter_entries = None
                if isinstance(timestamps_info, dict):
                    chapter_entries = timestamps_info.get("timestamps")

                bunny_result = run_step(
                    bunny_message,
                    lambda: processor.deploy_to_bunny(
                        str(video_path) if video_path else None,
                        upload_video=upload_bunny_video,
                        upload_chapters=upload_bunny_chapters,
                        upload_transcript=upload_bunny_transcript,
                        library_id=params.get("bunny_library_id"),
                        collection_id=params.get("bunny_collection_id"),
                        video_title=params.get("video_title"),
                        chapters=chapter_entries,
                        transcript_path=str(resolved_transcript) if resolved_transcript else None,
                        caption_language=params.get("bunny_caption_language"),
                        video_id=params.get("bunny_video_id"),
                    ),
                )

                if bunny_result:
                    pending = bunny_result.get("pending", False)
                    action_labels = []
                    if bunny_result.get("video_uploaded"):
                        action_labels.append("video")
                    if bunny_result.get("chapters_uploaded"):
                        action_labels.append("chapters")
                    if bunny_result.get("transcript_uploaded"):
                        action_labels.append("transcript")
                    failed_actions = []
                    if upload_bunny_chapters and not bunny_result.get("chapters_uploaded"):
                        failed_actions.append("chapters")
                    if upload_bunny_transcript and not bunny_result.get("transcript_uploaded"):
                        failed_actions.append("transcript")
                    action_summary = ", ".join(action_labels) or "no actions"
                    artifacts["Bunny video"] = bunny_result["video_id"]

                    if action_labels:
                        logger.info(
                            "✅ Bunny sync complete (%s) library=%s video_id=%s",
                            action_summary,
                            bunny_result["library_id"],
                            bunny_result["video_id"],
                        )
                        console.print(
                            "[green]Bunny sync complete[/] -> "
                            f"{action_summary} • ID {bunny_result['video_id']}"
                        )
                    else:
                        logger.info(
                            "⏳ Bunny sync pending (library=%s video_id=%s)",
                            bunny_result["library_id"],
                            bunny_result["video_id"],
                        )
                        console.print(
                            "[yellow]Bunny sync pending[/] -> "
                            f"Waiting for processing • ID {bunny_result['video_id']}"
                        )

                    if failed_actions:
                        console.print(
                            "[yellow]Bunny skipped:[/] "
                            f"{', '.join(failed_actions)} (asset may still be processing)"
                        )
                    elif pending:
                        console.print(
                            "[yellow]Re-run once Bunny finishes processing to push chapters/captions.[/]"
                        )
                else:
                    logger.error("❌ Bunny sync failed")
                    console.print("[red]Bunny sync failed[/]")

        if not params["skip_context_cards"]:
            if resolved_transcript:
                cards_path = run_step(
                    "🗂 Identifying context cards and resource mentions...",
                    lambda: processor.generate_context_cards(str(resolved_transcript)),
                )
                if cards_path:
                    logger.info(
                        f"✅ Context cards generated: {Path(cards_path).name}"
                    )
                    console.print(
                        f"[green]Context cards generated[/] -> "
                        f"{Path(cards_path).name}"
                    )
                    artifacts["Context cards"] = cards_path
                else:
                    logger.error("❌ Context cards generation failed")
                    console.print("[red]Context cards generation failed[/]")
            else:
                logger.warning("⚠️ Skipping context cards: no transcript available")
                console.print(
                    "[yellow]Skipping context cards: no transcript available[/]"
                )

        if (
            not params["skip_description"]
            and params["repo_url"]
            and video_path
        ):
            transcript_vtt_path = str(processor.output_dir / "transcript.vtt")
            if not Path(transcript_vtt_path).exists():
                logger.warning(f"⚠️ Transcript file not found: {transcript_vtt_path}")
                console.print(
                    f"[yellow]Transcript file not found:[/] {transcript_vtt_path}"
                )

            description_path = run_step(
                "📄 Generating description...",
                lambda: processor.generate_description(
                    str(video_path),
                    params["repo_url"],
                    transcript_vtt_path,
                ),
            )
            if description_path:
                logger.info(
                    f"✅ Description generated: {Path(description_path).name}"
                )
                console.print(
                    f"[green]Description generated[/] -> "
                    f"{Path(description_path).name}"
                )
                artifacts["Description"] = description_path

                if not params["skip_seo"]:
                    keywords_path = run_step(
                        "🔍 Generating SEO keywords...",
                        lambda: processor.generate_seo_keywords(description_path),
                    )
                    if keywords_path:
                        logger.info(
                            f"✅ SEO keywords generated: {Path(keywords_path).name}"
                        )
                        console.print(
                            f"[green]SEO keywords generated[/] -> "
                            f"{Path(keywords_path).name}"
                        )
                        artifacts["SEO keywords"] = keywords_path
                    else:
                        logger.error("❌ SEO keywords generation failed")
                        console.print("[red]SEO keyword generation failed[/]")
            else:
                logger.error("❌ Description generation failed")
                console.print("[red]Description generation failed[/]")
        elif not params["skip_description"] and params["repo_url"]:
            logger.warning("⚠️ Skipping description: no video file available")
            console.print("[yellow]Skipping description: no video file available[/]")
        elif not params["skip_description"]:
            logger.info("ℹ️ Skipping description: no repository URL provided")
            console.print("[yellow]Skipping description: no repository URL provided[/]")

        if (
            not params["skip_linkedin"]
            and video_path
            and resolved_transcript
        ):
            linkedin_path = run_step(
                "📱 Generating LinkedIn post...",
                lambda: processor.generate_linkedin_post(str(resolved_transcript)),
            )
            if linkedin_path:
                logger.info(
                    f"✅ LinkedIn post generated: {Path(linkedin_path).name}"
                )
                console.print(
                    f"[green]LinkedIn post generated[/] -> "
                    f"{Path(linkedin_path).name}"
                )
                artifacts["LinkedIn copy"] = linkedin_path
            else:
                logger.error("❌ LinkedIn post generation failed")
                console.print("[red]LinkedIn post generation failed[/]")
        elif not params["skip_linkedin"] and video_path:
            logger.warning("⚠️ Skipping LinkedIn post: no transcript available")
            console.print(
                "[yellow]Skipping LinkedIn post: no transcript available[/]"
            )
        elif not params["skip_linkedin"]:
            logger.warning("⚠️ Skipping LinkedIn post: no video file available")
            console.print("[yellow]Skipping LinkedIn post: no video file available[/]")

        if (
            not params["skip_twitter"]
            and video_path
            and resolved_transcript
        ):
            twitter_path = run_step(
                "🐦 Generating Twitter post...",
                lambda: processor.generate_twitter_post(str(resolved_transcript)),
            )
            if twitter_path:
                logger.info(
                    f"✅ Twitter post generated: {Path(twitter_path).name}"
                )
                console.print(
                    f"[green]Twitter post generated[/] -> "
                    f"{Path(twitter_path).name}"
                )
                artifacts["Twitter copy"] = twitter_path
            else:
                logger.error("❌ Twitter post generation failed")
                console.print("[red]Twitter post generation failed[/]")
        elif not params["skip_twitter"] and video_path:
            logger.warning("⚠️ Skipping Twitter post: no transcript available")
            console.print("[yellow]Skipping Twitter post: no transcript available[/]")
        elif not params["skip_twitter"]:
            logger.warning("⚠️ Skipping Twitter post: no video file available")
            console.print("[yellow]Skipping Twitter post: no video file available[/]")

        if artifacts:
            artifact_table = Table(box=box.ASCII, show_header=False, pad_edge=False)
            for label, value in artifacts.items():
                artifact_table.add_row(label, str(value))
            console.print()
            console.print(
                Panel(
                    artifact_table,
                    title="Generated Artifacts",
                    border_style="green",
                    box=box.ASCII,
                )
            )

        if manual_mode:
            prompt_save_profile(params)

        console.print("\n[bold green]All done! Happy editing.[/]")
        console.print("[dim]Detailed logs saved to video_processor.log[/]")

    except KeyboardInterrupt:
        console.print("\n[bold yellow]Processing interrupted by user.[/]")
        logger.warning("Processing interrupted by user")
    except Exception as exc:
        console.print(f"[bold red]Error during processing:[/] {exc}")
        logger.error(f"Error during processing: {exc}")
        raise


if __name__ == "__main__":
    main()
