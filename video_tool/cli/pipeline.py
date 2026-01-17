"""Pipeline command: orchestrates full video processing workflow.

Key improvement: uses direct VideoProcessor method calls instead of subprocesses.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import typer

from video_tool import VideoProcessor
from video_tool.cli import app, validate_ai_env_vars, validate_bunny_env_vars
from video_tool.ui import (
    ask_confirm,
    ask_path,
    ask_text,
    ask_choice,
    console,
    normalize_path,
    pipeline_complete,
    pipeline_error,
    pipeline_header,
    pipeline_step,
    status_spinner,
    step_complete,
    step_error,
    step_warning,
)


@dataclass
class PipelineConfig:
    """Configuration for pipeline run."""

    input_dir: Path
    output_dir: Path
    concat_title: str
    fast_concat: bool
    timestamps_granularity: str
    timestamp_notes: str
    timestamps_from_clips: bool
    include_context_cards: bool
    upload_bunny: bool
    bunny_library_id: Optional[str]
    bunny_access_key: Optional[str]
    bunny_collection_id: Optional[str]

    @property
    def concat_output_path(self) -> Path:
        return self.output_dir / f"{self.concat_title}.mp4"

    @property
    def transcript_output_path(self) -> Path:
        return self.output_dir / "transcript.vtt"

    @property
    def timestamps_output_path(self) -> Path:
        return self.output_dir / "timestamps.json"

    @property
    def context_cards_output_path(self) -> Path:
        return self.output_dir / "context-cards.md"

    @property
    def description_output_path(self) -> Path:
        return self.output_dir / "description.md"

    @property
    def metadata_path(self) -> Path:
        return self.output_dir / "metadata.json"


def _count_steps(config: PipelineConfig) -> int:
    """Count total number of pipeline steps."""
    count = 3  # concat, timestamps, transcript (always run)
    if config.include_context_cards:
        count += 1
    if config.upload_bunny:
        count += 1
    return count


def _gather_interactive_config() -> PipelineConfig:
    """Gather pipeline configuration interactively."""
    # Input directory
    input_dir_str = ask_path("Path to directory containing video clips", required=True)
    input_dir = Path(input_dir_str)

    if not input_dir.exists() or not input_dir.is_dir():
        step_error(f"Invalid directory: {input_dir}")
        raise typer.Exit(1)

    # Output directory
    default_output = input_dir / "output"
    output_dir_str = ask_path(f"Output directory (default: {default_output})", required=False)
    output_dir = Path(output_dir_str) if output_dir_str else default_output

    # Title
    concat_title = ask_text("Title for concatenated video", required=True, default=input_dir.name)

    # Concat mode
    fast_concat = ask_confirm("Use fast concatenation?", default=False)

    # Output options
    console.print("\n[bold]Select outputs to generate:[/bold]")
    include_context_cards = ask_confirm("Generate context cards?", default=True)
    upload_bunny = ask_confirm("Upload to Bunny.net?", default=False)

    # Timestamp settings
    console.print("\n[bold]Timestamp settings:[/bold]")
    timestamps_from_clips = ask_confirm("Generate timestamps from clip boundaries?", default=True)

    timestamps_granularity = "medium"
    timestamp_notes = ""
    if not timestamps_from_clips:
        timestamps_granularity = ask_choice("Granularity", ["low", "medium", "high"], default="medium")
        timestamp_notes = ask_text("Additional instructions (optional)", required=False) or ""

    # Bunny credentials
    bunny_library_id = os.getenv("BUNNY_LIBRARY_ID")
    bunny_access_key = os.getenv("BUNNY_ACCESS_KEY")
    bunny_collection_id = os.getenv("BUNNY_COLLECTION_ID")

    if upload_bunny:
        bunny_library_id = ask_text("Bunny Library ID", required=True, default=bunny_library_id)
        bunny_access_key = ask_text("Bunny Access Key", required=True, default=bunny_access_key)
        bunny_collection_id = ask_text("Bunny Collection ID (optional)", required=False, default=bunny_collection_id)

    return PipelineConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        concat_title=concat_title,
        fast_concat=fast_concat,
        timestamps_granularity=timestamps_granularity,
        timestamp_notes=timestamp_notes,
        timestamps_from_clips=timestamps_from_clips,
        include_context_cards=include_context_cards,
        upload_bunny=upload_bunny,
        bunny_library_id=bunny_library_id,
        bunny_access_key=bunny_access_key,
        bunny_collection_id=bunny_collection_id,
    )


def _build_noninteractive_config(
    input_dir: Path,
    output_dir: Optional[Path],
    title: Optional[str],
    fast_concat: bool,
    timestamps_from_clips: bool,
    granularity: str,
    upload_bunny: bool,
) -> PipelineConfig:
    """Build config for non-interactive mode with defaults."""
    resolved_output = output_dir or (input_dir / "output")
    resolved_title = title or input_dir.name

    return PipelineConfig(
        input_dir=input_dir,
        output_dir=resolved_output,
        concat_title=resolved_title,
        fast_concat=fast_concat,
        timestamps_granularity=granularity,
        timestamp_notes="",
        timestamps_from_clips=timestamps_from_clips,
        include_context_cards=True,
        upload_bunny=upload_bunny,
        bunny_library_id=os.getenv("BUNNY_LIBRARY_ID"),
        bunny_access_key=os.getenv("BUNNY_ACCESS_KEY"),
        bunny_collection_id=os.getenv("BUNNY_COLLECTION_ID"),
    )


@app.command("pipeline")
def pipeline(
    input_dir: Optional[Path] = typer.Option(None, "--input-dir", "-i", help="Input directory containing video clips"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Output directory"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Title for concatenated video"),
    fast_concat: bool = typer.Option(False, "--fast-concat", "-f", help="Use fast concatenation"),
    timestamps_from_clips: bool = typer.Option(True, "--timestamps-from-clips", help="Generate timestamps from clips"),
    granularity: str = typer.Option("medium", "--granularity", "-g", help="Timestamp granularity"),
    upload_bunny: bool = typer.Option(False, "--upload-bunny", help="Upload to Bunny.net after processing"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Non-interactive mode (use defaults)"),
) -> None:
    """Run the full video processing pipeline.

    Orchestrates: concat -> timestamps -> transcript -> content generation -> optional Bunny upload.

    In non-interactive mode (--yes), all content outputs are enabled by default
    and Bunny upload is skipped unless explicitly enabled with --upload-bunny.
    """
    # Validate AI credentials
    if not validate_ai_env_vars():
        raise typer.Exit(1)

    # Gather configuration
    if yes:
        # Non-interactive mode
        if input_dir is None:
            step_error("--input-dir is required in non-interactive mode")
            raise typer.Exit(1)

        input_path = Path(normalize_path(str(input_dir)))
        if not input_path.exists() or not input_path.is_dir():
            step_error(f"Invalid input directory: {input_path}")
            raise typer.Exit(1)

        output_path = Path(normalize_path(str(output_dir))) if output_dir else None
        config = _build_noninteractive_config(
            input_path, output_path, title, fast_concat, timestamps_from_clips, granularity, upload_bunny
        )
    else:
        # Interactive mode
        config = _gather_interactive_config()

    # Validate Bunny credentials if needed
    if config.upload_bunny:
        if not validate_bunny_env_vars(config.bunny_library_id, config.bunny_access_key):
            raise typer.Exit(1)

    # Create output directory
    config.output_dir.mkdir(parents=True, exist_ok=True)

    # Display configuration
    total_steps = _count_steps(config)
    pipeline_header(
        "Pipeline Configuration",
        {
            "Input": str(config.input_dir),
            "Output": str(config.output_dir),
            "Title": config.concat_title,
            "Steps": str(total_steps),
            "Fast concat": "Yes" if config.fast_concat else "No",
            "Bunny upload": "Yes" if config.upload_bunny else "No",
        },
    )

    # Track artifacts
    artifacts: List[str] = []
    current_step = 0

    try:
        # Create processor
        processor = VideoProcessor(
            str(config.input_dir),
            video_title=config.concat_title,
            output_dir=str(config.output_dir),
        )

        # Step 1: Concatenate
        current_step += 1
        pipeline_step(current_step, total_steps, "Concatenating videos")
        with status_spinner("Processing"):
            concat_result = processor.concatenate_videos(
                output_filename=config.concat_title,
                skip_reprocessing=config.fast_concat,
                output_path=str(config.concat_output_path),
            )

        if not concat_result:
            pipeline_error("Concatenation failed", "Concatenating videos")
            raise typer.Exit(1)

        step_complete("Videos concatenated", concat_result)
        artifacts.append(Path(concat_result).name)

        # Step 2: Timestamps
        current_step += 1
        pipeline_step(current_step, total_steps, "Generating timestamps")
        with status_spinner("Analyzing"):
            timestamps_result = processor.generate_timestamps(
                output_path=str(config.timestamps_output_path),
                transcript_path=str(config.transcript_output_path) if not config.timestamps_from_clips else None,
                stamps_from_transcript=not config.timestamps_from_clips,
                granularity=config.timestamps_granularity,
                timestamp_notes=config.timestamp_notes,
            )

        step_complete("Timestamps generated", config.timestamps_output_path)
        artifacts.append(config.timestamps_output_path.name)

        # Step 3: Transcript
        current_step += 1
        pipeline_step(current_step, total_steps, "Transcribing audio")
        with status_spinner("Transcribing"):
            transcript_result = processor.generate_transcript(
                str(config.concat_output_path),
                output_path=str(config.transcript_output_path),
            )

        step_complete("Transcript generated", transcript_result)
        artifacts.append(config.transcript_output_path.name)

        # Step 4: Context cards (optional)
        if config.include_context_cards:
            current_step += 1
            pipeline_step(current_step, total_steps, "Generating context cards")
            with status_spinner("Processing"):
                cards_result = processor.generate_context_cards(
                    str(config.transcript_output_path),
                    output_path=str(config.context_cards_output_path),
                )

            if cards_result:
                step_complete("Context cards generated", cards_result)
                artifacts.append(config.context_cards_output_path.name)
            else:
                step_warning("Context cards generation failed")

        # Step 5: Bunny upload (optional)
        if config.upload_bunny:
            current_step += 1
            pipeline_step(current_step, total_steps, "Uploading to Bunny.net")
            with status_spinner("Uploading"):
                upload_result = processor.upload_bunny_video(
                    video_path=str(config.concat_output_path),
                    library_id=config.bunny_library_id,
                    access_key=config.bunny_access_key,
                    collection_id=config.bunny_collection_id,
                )

            if upload_result:
                video_id = upload_result.get("video_id", "")
                step_complete(f"Uploaded to Bunny.net (ID: {video_id})")
            else:
                step_warning("Bunny upload failed")

        # Success!
        console.print()
        pipeline_complete(str(config.output_dir), artifacts)

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Pipeline interrupted by user.[/bold yellow]")
        raise typer.Exit(130)
    except Exception as e:
        pipeline_error(str(e), f"Step {current_step}")
        raise typer.Exit(1)
