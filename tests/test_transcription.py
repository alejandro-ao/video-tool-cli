"""Tests for backend-neutral transcription support."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from video_tool.transcription import (
    MissingBackendDependency,
    TranscriptionService,
    TranscriptResult,
    TranscriptSegment,
    list_models,
    recommend_model,
    render_vtt,
    resolve_model,
)
from video_tool.transcription.backends.groq import GroqBackend


@pytest.mark.unit
def test_registry_exposes_local_and_remote_models():
    models = list_models()
    assert any(item.id == "mlx/parakeet-tdt-0.6b-v2" and item.local for item in models)
    assert any(item.id == "groq/whisper-large-v3-turbo" and not item.local for item in models)
    assert resolve_model(None, "transformers").repository == "openai/whisper-large-v3-turbo"


@pytest.mark.unit
def test_groq_backend_normalizes_response(tmp_path):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"audio")
    client = Mock()
    client.audio.transcriptions.create.return_value = SimpleNamespace(
        text="Hello world",
        segments=[SimpleNamespace(start=0.0, end=1.5, text=" Hello world ")],
    )

    result = GroqBackend(client).transcribe(audio, model="whisper-large-v3-turbo")

    assert result.text == "Hello world"
    assert result.segments == [TranscriptSegment(0.0, 1.5, "Hello world")]
    client.audio.transcriptions.create.assert_called_once()


@pytest.mark.unit
def test_groq_backend_chunks_oversized_audio(tmp_path):
    audio = tmp_path / "large.mp3"
    audio.write_bytes(b"x" * (24 * 1024 * 1024 + 1))
    client = Mock()
    client.audio.transcriptions.create.side_effect = [
        SimpleNamespace(text="First", segments=[{"start": 0, "end": 2, "text": "First"}]),
        SimpleNamespace(text="Second", segments=[{"start": 0, "end": 2, "text": "Second"}]),
    ]
    decoded = Mock()
    decoded.__len__ = Mock(return_value=20 * 60 * 1000)
    chunk = Mock()
    chunk.export.side_effect = lambda path, format: path.write_bytes(b"chunk")
    decoded.__getitem__ = Mock(return_value=chunk)

    with patch("video_tool.transcription.backends.groq.AudioSegment.from_file", return_value=decoded):
        result = GroqBackend(client).transcribe(audio, model="whisper-large-v3-turbo")

    assert client.audio.transcriptions.create.call_count == 2
    assert result.segments[1].start == 600


@pytest.mark.unit
def test_service_dispatches_registered_model(tmp_path):
    expected = TranscriptResult("hello", [], "mlx-parakeet", "model", "en")
    backend = Mock()
    backend.transcribe.return_value = expected
    with patch("video_tool.transcription.service.create_backend", return_value=backend) as factory:
        result = TranscriptionService().transcribe(
            tmp_path / "audio.wav", model="mlx/parakeet-tdt-0.6b-v2", language="en"
        )
    assert result is expected
    factory.assert_called_once_with("mlx-parakeet", groq_client=None)
    backend.transcribe.assert_called_once_with(
        tmp_path / "audio.wav",
        model="mlx-community/parakeet-tdt-0.6b-v2",
        language="en",
        device="auto",
        compute_type="auto",
    )


@pytest.mark.unit
def test_vtt_renderer_sanitizes_and_orders_segments():
    result = TranscriptResult(
        "",
        [TranscriptSegment(5, 6, "Second"), TranscriptSegment(-1, 2, "First\x00")],
        "test",
        "test",
    )
    rendered = render_vtt(result)
    assert rendered.startswith("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nFirst")
    assert rendered.index("First") < rendered.index("Second")


@pytest.mark.unit
def test_missing_optional_dependency_has_install_command(tmp_path):
    from video_tool.transcription.backends.mlx_parakeet import MlxParakeetBackend

    with patch.dict("sys.modules", {"parakeet_mlx": None}):
        with pytest.raises(MissingBackendDependency, match="transcription-mlx"):
            MlxParakeetBackend().transcribe(tmp_path / "audio.wav", model="model")


@pytest.mark.unit
def test_apple_silicon_recommends_parakeet_for_english():
    with patch("sys.platform", "darwin"), patch("platform.machine", return_value="arm64"):
        choice = recommend_model(language="en")
    assert choice.model_id == "mlx/parakeet-tdt-0.6b-v2"
    assert "Apple Silicon detected" in choice.reasons
