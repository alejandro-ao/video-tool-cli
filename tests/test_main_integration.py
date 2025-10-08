"""Integration tests for the main.py CLI workflow.

These tests exercise all operational branches by toggling the skip flags
returned from ``get_user_input`` and asserting the expected calls on the
``VideoProcessor`` facade.  They validate that each processing step can run
independently, that the complete workflow executes every stage, and that a user
choosing to skip all actions is handled cleanly.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from main import get_user_input, main


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
        "skip_bunny_upload": True,
        "bunny_library_id": None,
        "bunny_collection_id": None,
        "bunny_caption_language": "en",
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
        "n",  # skip_bunny_upload?
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
        "skip_bunny_upload": False,
        "bunny_library_id": "library-123",
        "bunny_collection_id": "collection-456",
        "bunny_caption_language": "en",
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
        "y",  # skip Bunny upload
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
        "skip_bunny_upload": True,
        "bunny_library_id": None,
        "bunny_collection_id": None,
        "bunny_caption_language": "en",
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
        "y",
        "y",
        "y",
        "y",
        "y",
        "y",
        "y",
        "y",
        "n",
    ]

    result = get_user_input()

    assert result["input_dir"] == "/Volume/My Videos"
    assert result["video_title"] == "Episode 1"
    assert result["repo_url"] is None
    assert result["skip_concat"] is True
    assert result["skip_bunny_upload"] is True
    assert result["verbose_logging"] is False


# ---------------------------------------------------------------------------
# main() workflow permutations
# ---------------------------------------------------------------------------


def test_main_full_workflow_runs_every_step(temp_dir):
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
        skip_bunny_upload=False,
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
    processor.generate_context_cards.assert_called_once_with(
        str(processor.output_dir / "transcript.vtt")
    )
    processor.deploy_to_bunny.assert_called_once_with(
        str(processor.output_dir / "final.mp4"),
        library_id=params["bunny_library_id"],
        collection_id=params["bunny_collection_id"],
        video_title=params["video_title"],
        chapters=[],
        transcript_path=str(processor.output_dir / "transcript.vtt"),
        caption_language=params["bunny_caption_language"],
    )


def test_main_skip_all_steps(temp_dir):
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
def test_main_individual_core_steps(temp_dir, flag_overrides, expected_calls):
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
        processor.generate_context_cards.assert_called_once_with(expected_transcript)


def test_main_generates_description_and_seo(temp_dir):
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


def test_main_generates_social_posts(temp_dir):
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


def test_main_skips_description_without_repo_url(temp_dir):
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
