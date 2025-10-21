import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
import json
from datetime import datetime

# Test data and fixtures

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    (temp_path / "output").mkdir(parents=True, exist_ok=True)
    yield temp_path
    shutil.rmtree(temp_path)

@pytest.fixture
def mock_logger():
    """Create a mock logger for tests."""
    with patch('video_tool.video_processor.logger') as mock_logger:
        yield mock_logger

@pytest.fixture
def mock_video_processor(temp_dir):
    """Create a VideoProcessor instance with mocked dependencies."""
    with patch('video_tool.video_processor.OpenAI') as mock_openai, \
         patch('video_tool.video_processor.Groq') as mock_groq, \
         patch('video_tool.video_processor.logger') as mock_logger:
        
        # Mock the prompts loading
        mock_prompts = {
            'generate_description': 'Test description prompt: {transcript}',
            'polish_description': 'Polish prompt: {description}',
            'generate_seo_keywords': 'SEO prompt: {description}',
            'generate_linkedin_post': 'Test LinkedIn prompt: {transcript}',
            'generate_twitter_post': 'Test Twitter prompt: {transcript}',
        }
        
        with patch('video_tool.video_processor.VideoProcessor._load_prompts', return_value=mock_prompts):
            from video_tool.video_processor import VideoProcessor
            processor = VideoProcessor(str(temp_dir))
            processor.client = mock_openai.return_value
            processor.groq = mock_groq.return_value
            yield processor

# Removed redundant fixtures - using test_data/sample_data.py and test_data/mock_generators.py instead

# Removed redundant mock response fixtures - using test_data/sample_data.py instead

# Removed redundant video metadata fixture - using test_data/sample_data.py instead

@pytest.fixture
def mock_ffmpeg_success():
    """Mock successful ffmpeg subprocess calls."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ''
        mock_run.return_value.stderr = ''
        yield mock_run

@pytest.fixture
def mock_ffprobe_video_info():
    """Mock ffprobe video information response."""
    return {
        'streams': [{
            'width': 1920,
            'height': 1080,
            'r_frame_rate': '30/1',
            'codec_name': 'h264',
            'bit_rate': '5000000',
            'pix_fmt': 'yuv420p'
        }]
    }

@pytest.fixture
def mock_ffprobe_audio_info():
    """Mock ffprobe audio information response."""
    return {
        'streams': [{
            'codec_name': 'aac',
            'sample_rate': '48000',
            'channels': 2,
            'bit_rate': '128000'
        }]
    }

@pytest.fixture(autouse=True)
def setup_test_env():
    """Setup test environment variables."""
    original_env = os.environ.copy()
    os.environ['OPENAI_API_KEY'] = 'test-key'
    os.environ['GROQ_API_KEY'] = 'test-key'
    # Ensure Bunny deployment tests don't pick up real environment values
    for key in (
        'BUNNY_LIBRARY_ID',
        'BUNNY_ACCESS_KEY',
        'BUNNY_COLLECTION_ID',
        'BUNNY_CAPTION_LANGUAGE',
        'BUNNY_VIDEO_ID',
    ):
        if key in os.environ:
            del os.environ[key]
    yield
    os.environ.clear()
    os.environ.update(original_env)

# Helper functions for tests

def create_mock_video_file(file_path: Path, duration_seconds: float = 10.0):
    """Create a mock video file with basic metadata."""
    # Create a minimal file that looks like an MP4
    file_path.write_bytes(b'\x00\x00\x00\x20ftypmp42' + b'\x00' * 1000)
    
    # Set file modification time to simulate creation date
    timestamp = datetime(2024, 1, 1, 12, 0, 0).timestamp()
    os.utime(file_path, (timestamp, timestamp))

def create_mock_audio_segment(duration_ms: int = 10000):
    """Create a mock AudioSegment for testing."""
    mock_audio = Mock()
    mock_audio.duration_seconds = duration_ms / 1000
    mock_audio.__len__ = Mock(return_value=duration_ms)
    return mock_audio
