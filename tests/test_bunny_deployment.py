from unittest.mock import MagicMock, patch


def _make_response(json_payload=None, status=200):
    response = MagicMock()
    response.status_code = status
    response.raise_for_status = MagicMock()
    if json_payload is None:
        response.json.side_effect = ValueError("No JSON")
    else:
        response.json.return_value = json_payload
    return response


def test_deploy_to_bunny_requires_credentials(mock_video_processor, temp_dir):
    """Ensure missing credentials short-circuit the upload step."""
    video_path = temp_dir / "output" / "final.mp4"
    video_path.write_bytes(b"\x00\x00test")

    with patch("video_tool.video_processor.requests.request") as mock_request:
        result = mock_video_processor.deploy_to_bunny(str(video_path))

    assert result is None
    mock_request.assert_not_called()


def test_deploy_to_bunny_uploads_video_and_metadata(mock_video_processor, temp_dir):
    """Uploading performs the expected Bunny API calls in sequence."""
    output_dir = temp_dir / "output"
    video_path = output_dir / "final.mp4"
    video_path.write_bytes(b"\x00fakevideo")

    transcript_path = output_dir / "transcript.vtt"
    transcript_path.write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nHello\n", encoding="utf-8")

    chapters = [
        {"title": "Intro", "start": "00:00:00", "end": "00:01:00"},
    ]

    responses = [
        _make_response({"videoId": "vid-123"}),
        _make_response({}),
        _make_response({}),
        _make_response({"guid": "cap-123"}),
        _make_response({}),
    ]

    with patch("video_tool.video_processor.requests.request", side_effect=responses) as mock_request:
        result = mock_video_processor.deploy_to_bunny(
            str(video_path),
            library_id="lib-1",
            access_key="access-1",
            collection_id="collection-9",
            video_title="Demo Video",
            chapters=chapters,
            transcript_path=str(transcript_path),
            caption_language="en",
        )

    assert result == {
        "library_id": "lib-1",
        "video_id": "vid-123",
        "title": "Demo Video",
    }

    assert mock_request.call_count == 5
    methods = [call.kwargs["method"] for call in mock_request.call_args_list]
    assert methods == ["POST", "PUT", "POST", "POST", "PUT"]

    # Create video request payload
    create_kwargs = mock_request.call_args_list[0].kwargs
    assert create_kwargs["url"].endswith("/library/lib-1/videos")
    assert create_kwargs["json"] == {
        "title": "Demo Video",
        "collectionId": "collection-9",
    }
    assert create_kwargs["headers"]["AccessKey"] == "access-1"

    # Upload binary request
    upload_kwargs = mock_request.call_args_list[1].kwargs
    assert upload_kwargs["url"].endswith("/library/lib-1/videos/vid-123")
    assert upload_kwargs["headers"]["Content-Type"] == "application/octet-stream"
    assert upload_kwargs["headers"]["AccessKey"] == "access-1"

    # Chapter update request payload should be normalised
    chapters_kwargs = mock_request.call_args_list[2].kwargs
    assert chapters_kwargs["json"] == {
        "chapters": [{"title": "Intro", "start": "0:00", "end": "1:00"}]
    }

    # Caption creation request
    caption_kwargs = mock_request.call_args_list[3].kwargs
    assert caption_kwargs["json"] == {
        "srclang": "en",
        "captionTitle": "EN",
    }

    # Caption upload request contains file payload
    caption_upload_kwargs = mock_request.call_args_list[4].kwargs
    files = caption_upload_kwargs["files"]
    assert "captionsFile" in files
    filename, file_content, content_type = files["captionsFile"]
    assert filename == "transcript.vtt"
    assert content_type == "text/vtt"
    assert b"Hello" in file_content
