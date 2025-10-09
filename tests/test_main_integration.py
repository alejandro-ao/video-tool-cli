"""Integration tests for the main.py CLI workflow.

These tests exercise all operational branches by toggling the skip flags
returned from ``get_user_input`` and asserting the expected calls on the
``VideoProcessor`` facade.  They validate that each processing step can run
independently, that the complete workflow executes every stage, and that a user
choosing to skip all actions is handled cleanly.
"""

from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from main import STEP_FLAG_SPECS, get_user_input, main


PROCESSOR_METHODS = [
    "remove_silences",
    "generate_timestamps",
    "concatenate_videos",
    "generate_transcript",
    "generate_context_cards",
    "generate_description",
    "generate_seo_keywords",
    "generate_linkedin_post",
    "generate_twitter_post",
    "deploy_to_bunny",
]


def _create_processor_mock(temp_dir: Path) -> MagicMock:
    """Create a VideoProcessor mock with realistic filesystem artifacts."""
    output_dir = temp_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    final_video = output_dir / "final.mp4"
    final_video.write_bytes(b"\x00\x00fake-video")

    transcript_file = output_dir / "transcript.vtt"
    transcript_file.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nSample transcript line.\n"
    )

    # Provide an input clip so the fallback discovery logic has material.
    raw_clip = temp_dir / "source_clip.mp4"
    raw_clip.write_bytes(b"\x00\x00raw-clip")

    processor = MagicMock()
    processor.output_dir = output_dir
    processor.remove_silences.return_value = str(temp_dir / "processed")
    processor.generate_timestamps.return_value = {"timestamps": []}
    processor.concatenate_videos.return_value = str(final_video)
    processor.generate_transcript.return_value = str(transcript_file)
    processor.generate_context_cards.return_value = str(output_dir / "context_cards.md")
    processor.generate_description.return_value = str(output_dir / "description.md")
    processor.generate_seo_keywords.return_value = str(output_dir / "keywords.txt")
    processor.generate_linkedin_post.return_value = str(output_dir / "linkedin_post.md")
    processor.generate_twitter_post.return_value = str(output_dir / "twitter_post.md")
    processor.deploy_to_bunny.return_value = {
        "library_id": "lib123",
        "video_id": "vid123",
        "title": "Test Video",
        "video_uploaded": True,
        "chapters_uploaded": True,
        "transcript_uploaded": True,
        "pending": False,
    }
    return processor


def _build_params(temp_dir: Path, **overrides) -> dict:
    """Return a baseline parameter payload with sensible defaults."""
    params = {
        "input_dir": str(temp_dir),
        "repo_url": "https://github.com/test/repo",
        "video_title": "Test Video",
        "skip_silence_removal": True,
        "skip_concat": True,
        "skip_reprocessing": True,
        "skip_timestamps": True,
        "skip_transcript": True,
        "skip_context_cards": True,
        "skip_description": True,
        "skip_seo": True,
        "skip_linkedin": True,
        "skip_twitter": True,
        "skip_bunny_video_upload": True,
        "skip_bunny_chapter_upload": True,
        "skip_bunny_transcript_upload": True,
        "bunny_library_id": None,
        "bunny_collection_id": None,
        "bunny_caption_language": "en",
        "bunny_video_id": None,
        "verbose_logging": False,
    }
    params.update(overrides)
    return params


def _assert_only_called(processor: MagicMock, *expected_methods: str) -> None:
    """Assert that only the named processor methods were invoked exactly once."""
    expected = set(expected_methods)
    for method_name in PROCESSOR_METHODS:
        method = getattr(processor, method_name)
        if method_name in expected:
            assert method.call_count == 1, f"Expected {method_name} to be called once"
        else:
            assert method.call_count == 0, f"Did not expect {method_name} to be called"


# ---------------------------------------------------------------------------
# get_user_input validation
# ---------------------------------------------------------------------------


@patch("builtins.input")
def test_get_user_input_all_options(mock_input):
    """Collecting input without skipping any steps populates every flag."""
    mock_input.side_effect = [
        "/path/to/videos",
        "https://github.com/user/repo",
        "My Great Video",
        "n",  # skip_silence_removal?
        "n",  # skip_concat?
        "n",  # skip_reprocessing?
        "n",  # skip_timestamps?
        "n",  # skip_transcript?
        "n",  # skip_context_cards?
        "n",  # skip_description?
        "n",  # skip_seo?
        "n",  # skip_linkedin?
        "n",  # skip_twitter?
        "n",  # skip Bunny video upload?
        "n",  # skip Bunny chapter upload?
        "n",  # skip Bunny transcript upload?
        "library-123",
        "collection-456",
        "en",
        "n",  # verbose logging
    ]

    result = get_user_input()

    assert result == {
        "input_dir": "/path/to/videos",
        "repo_url": "https://github.com/user/repo",
        "video_title": "My Great Video",
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
        "skip_bunny_video_upload": False,
        "skip_bunny_chapter_upload": False,
        "skip_bunny_transcript_upload": False,
        "bunny_library_id": "library-123",
        "bunny_collection_id": "collection-456",
        "bunny_caption_language": "en",
        "bunny_video_id": None,
        "verbose_logging": False,
    }


@patch("builtins.input")
def test_get_user_input_skip_everything(mock_input):
    """Confirm answering 'y' to each prompt skips the associated step."""
    mock_input.side_effect = [
        "/path/to/videos",
        "",
        "",
        "y",  # skip silence removal
        "y",  # skip concatenation (skip_reprocessing prompt omitted)
        "y",  # skip timestamps
        "y",  # skip transcript
        "y",  # skip context cards
        "y",  # skip description
        "y",  # skip SEO keywords
        "y",  # skip LinkedIn post
        "y",  # skip Twitter post
        "y",  # skip Bunny video upload
        "y",  # skip Bunny chapter upload
        "y",  # skip Bunny transcript upload
        "y",  # verbose logging
    ]

    result = get_user_input()

    assert result == {
        "input_dir": "/path/to/videos",
        "repo_url": None,
        "video_title": None,
        "skip_silence_removal": True,
        "skip_concat": True,
        "skip_reprocessing": False,
        "skip_timestamps": True,
        "skip_transcript": True,
        "skip_context_cards": True,
        "skip_description": True,
        "skip_seo": True,
        "skip_linkedin": True,
        "skip_twitter": True,
        "skip_bunny_video_upload": True,
        "skip_bunny_chapter_upload": True,
        "skip_bunny_transcript_upload": True,
        "bunny_library_id": None,
        "bunny_collection_id": None,
        "bunny_caption_language": "en",
        "bunny_video_id": None,
        "verbose_logging": True,
    }


@patch("builtins.input")
def test_get_user_input_handles_quoted_path(mock_input):
    """Quoted directory paths are unwrapped and escape sequences normalised."""
    mock_input.side_effect = [
        '"/Volume/My Videos"',
        "",
        "Episode 1",
        "n",
        "y",  # skip concatenation to avoid skip_reprocessing prompt
        "y",  # skip timestamps
        "y",  # skip transcript
        "y",  # skip context cards
        "y",  # skip description
        "y",  # skip SEO
        "y",  # skip LinkedIn
        "y",  # skip Twitter
        "y",  # skip Bunny video upload
        "y",  # skip Bunny chapter upload
        "y",  # skip Bunny transcript upload
        "n",  # verbose logging
    ]

    result = get_user_input()

    assert result["input_dir"] == "/Volume/My Videos"
    assert result["video_title"] == "Episode 1"
    assert result["repo_url"] is None
    assert result["skip_concat"] is True
    assert result["skip_bunny_video_upload"] is True
    assert result["skip_bunny_chapter_upload"] is True
    assert result["skip_bunny_transcript_upload"] is True
    assert result["bunny_video_id"] is None
    assert result["verbose_logging"] is False


# ---------------------------------------------------------------------------
# main() workflow permutations
# ---------------------------------------------------------------------------


@pytest.fixture
def manual_cli_args():
    """Patch CLI parsing to emulate --manual runs inside integration tests."""
    base_flags = {spec.attr: False for spec in STEP_FLAG_SPECS}
    args = Namespace(
        command="run",
        manual=True,
        profile=None,
        input_dir=None,
        all=False,
        **base_flags,
    )
    with patch("main.parse_cli_args", return_value=args):
        yield


def test_main_full_workflow_runs_every_step(temp_dir, manual_cli_args):
    """Running with every step enabled invokes the complete pipeline."""
    processor = _create_processor_mock(temp_dir)
    params = _build_params(
        temp_dir,
        skip_silence_removal=False,
        skip_concat=False,
        skip_reprocessing=False,
        skip_timestamps=False,
        skip_transcript=False,
        skip_context_cards=False,
        skip_description=False,
        skip_seo=False,
        skip_linkedin=False,
        skip_twitter=False,
        skip_bunny_video_upload=False,
        skip_bunny_chapter_upload=False,
        skip_bunny_transcript_upload=False,
        bunny_library_id="library-123",
        bunny_collection_id="collection-456",
    )

    with patch("main.get_user_input", return_value=params), patch(
        "main.VideoProcessor", return_value=processor
    ):
        main()

    _assert_only_called(
        processor,
        "remove_silences",
        "generate_timestamps",
        "concatenate_videos",
        "generate_transcript",
        "generate_context_cards",
        "generate_description",
        "generate_seo_keywords",
        "generate_linkedin_post",
        "generate_twitter_post",
        "deploy_to_bunny",
    )
    processor.concatenate_videos.assert_called_once_with(skip_reprocessing=False)
    processor.generate_transcript.assert_called_once_with(str(processor.output_dir / "final.mp4"))
    processor.generate_context_cards.assert_called_once()
    context_args, context_kwargs = processor.generate_context_cards.call_args
    assert context_args[0] == str(processor.output_dir / "transcript.vtt")
    assert context_kwargs.get("output_path") is None
    processor.deploy_to_bunny.assert_called_once_with(
        str(processor.output_dir / "final.mp4"),
        upload_video=True,
        upload_chapters=True,
        upload_transcript=True,
        library_id=params["bunny_library_id"],
        collection_id=params["bunny_collection_id"],
        video_title=params["video_title"],
        chapters=[],
        transcript_path=str(processor.output_dir / "transcript.vtt"),
        caption_language=params["bunny_caption_language"],
        video_id=params["bunny_video_id"],
    )


def test_main_skip_all_steps(temp_dir, manual_cli_args):
    """When every flag is skipped, no processing methods are called."""
    processor = _create_processor_mock(temp_dir)
    params = _build_params(temp_dir, repo_url=None, video_title=None)

    with patch("main.get_user_input", return_value=params), patch(
        "main.VideoProcessor", return_value=processor
    ):
        main()

    _assert_only_called(processor)


@pytest.mark.parametrize(
    "flag_overrides, expected_calls",
    [
        (dict(skip_silence_removal=False), ["remove_silences"]),
        (dict(skip_timestamps=False), ["generate_timestamps"]),
        (dict(skip_concat=False, skip_reprocessing=False), ["concatenate_videos"]),
        (dict(skip_transcript=False), ["generate_transcript"]),
        (dict(skip_context_cards=False), ["generate_context_cards"]),
    ],
)
def test_main_individual_core_steps(temp_dir, manual_cli_args, flag_overrides, expected_calls):
    """Each core step can run in isolation without invoking neighbours."""
    processor = _create_processor_mock(temp_dir)
    params = _build_params(temp_dir, **flag_overrides)

    with patch("main.get_user_input", return_value=params), patch(
        "main.VideoProcessor", return_value=processor
    ):
        main()

    _assert_only_called(processor, *expected_calls)
    if "concatenate_videos" in expected_calls:
        processor.concatenate_videos.assert_called_once_with(
            skip_reprocessing=flag_overrides.get("skip_reprocessing", True)
        )
    if "generate_transcript" in expected_calls:
        expected_video = str(processor.output_dir / "final.mp4")
        processor.generate_transcript.assert_called_once_with(expected_video)
    if "generate_context_cards" in expected_calls:
        expected_transcript = str(processor.output_dir / "transcript.vtt")
        processor.generate_context_cards.assert_called_once()
        args, kwargs = processor.generate_context_cards.call_args
        assert args[0] == expected_transcript
        assert kwargs.get("output_path") is None


def test_main_generates_description_and_seo(temp_dir, manual_cli_args):
    """Description generation triggers the SEO keyword pass when enabled."""
    processor = _create_processor_mock(temp_dir)
    params = _build_params(
        temp_dir,
        skip_description=False,
        skip_seo=False,
    )

    with patch("main.get_user_input", return_value=params), patch(
        "main.VideoProcessor", return_value=processor
    ):
        main()

    _assert_only_called(processor, "generate_description", "generate_seo_keywords")
    processor.generate_description.assert_called_once_with(
        str(processor.output_dir / "final.mp4"),
        params["repo_url"],
        str(processor.output_dir / "transcript.vtt"),
    )
    description_path = processor.generate_description.return_value
    processor.generate_seo_keywords.assert_called_once_with(description_path)


def test_main_generates_social_posts(temp_dir, manual_cli_args):
    """Social post generation runs independently once transcript is present."""
    processor = _create_processor_mock(temp_dir)
    params = _build_params(
        temp_dir,
        skip_linkedin=False,
        skip_twitter=False,
    )

    with patch("main.get_user_input", return_value=params), patch(
        "main.VideoProcessor", return_value=processor
    ):
        main()

    _assert_only_called(processor, "generate_linkedin_post", "generate_twitter_post")
    transcript_path = str(processor.output_dir / "transcript.vtt")
    processor.generate_linkedin_post.assert_called_once_with(transcript_path)
    processor.generate_twitter_post.assert_called_once_with(transcript_path)


def test_main_skips_description_without_repo_url(temp_dir, manual_cli_args):
    """Description generation is skipped when a repository URL is not provided."""
    processor = _create_processor_mock(temp_dir)
    params = _build_params(
        temp_dir,
        repo_url=None,
        skip_description=False,
        skip_seo=False,
    )

    with patch("main.get_user_input", return_value=params), patch(
        "main.VideoProcessor", return_value=processor
    ):
        main()

    _assert_only_called(processor)


def _build_cli_args(**overrides) -> Namespace:
    """Helper to assemble a CLI namespace for non-manual invocations."""
    base_flags = {spec.attr: False for spec in STEP_FLAG_SPECS}
    base_payload = dict(
        command="run",
        manual=False,
        profile=None,
        input_dir=None,
        all=False,
        fast_concat=False,
        standard_concat=False,
        bunny_video_path=None,
        bunny_transcript_path=None,
        bunny_chapters_path=None,
    )
    base_payload.update(base_flags)
    base_payload.update(overrides)
    return Namespace(**base_payload)


def test_main_cli_transcript_only_runs_single_step(temp_dir):
    """Passing --transcript executes only the transcript stage."""
    processor = _create_processor_mock(temp_dir)
    args = _build_cli_args(input_dir=str(temp_dir), transcript=True)

    with patch("main.parse_cli_args", return_value=args), patch(
        "main.VideoProcessor", return_value=processor
    ):
        main()

    _assert_only_called(processor, "generate_transcript")
    expected_video = str(processor.output_dir / "final.mp4")
    processor.generate_transcript.assert_called_once_with(expected_video)


def test_main_cli_requires_input_dir_for_transcript(temp_dir):
    """Non-interactive transcript runs fail fast when no directory is provided."""
    args = _build_cli_args(transcript=True)

    with patch("main.parse_cli_args", return_value=args), patch(
        "main.VideoProcessor"
    ) as mock_processor, patch("main.console.print") as mock_console:
        main()

    mock_processor.assert_not_called()
    mock_console.assert_any_call(
        "[bold red]Input directory required.[/] "
        "Provide it to continue running Transcript."
    )


def test_main_cli_concat_handles_non_path_response(temp_dir):
    """Concatenation gracefully handles metadata results instead of file paths."""
    processor = _create_processor_mock(temp_dir)
    processor.concatenate_videos.return_value = {"metadata": {}}
    args = _build_cli_args(input_dir=str(temp_dir), concat=True)

    with patch("main.parse_cli_args", return_value=args), patch(
        "main.VideoProcessor", return_value=processor
    ), patch("main.console.print") as mock_console:
        main()

    processor.concatenate_videos.assert_called_once_with(skip_reprocessing=False)
    mock_console.assert_any_call(
        "[yellow]Video concatenation completed but no output file returned[/]"
    )


def test_main_cli_fast_concat_flag_enables_skip_reprocessing(temp_dir):
    """Fast concatenation flag switches the mode without prompting."""
    processor = _create_processor_mock(temp_dir)
    args = _build_cli_args(
        input_dir=str(temp_dir),
        concat=True,
        fast_concat=True,
    )

    with patch("main.parse_cli_args", return_value=args), patch(
        "main.VideoProcessor", return_value=processor
    ):
        main()

    processor.concatenate_videos.assert_called_once_with(skip_reprocessing=True)
