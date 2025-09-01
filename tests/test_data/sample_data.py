"""Sample test data for unit tests."""

from typing import Dict, List, Any

# Sample video metadata for testing
SAMPLE_VIDEO_METADATA = {
    "test_video_01.mp4": {
        "duration": 300.5,
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "codec": "h264",
        "bitrate": "5000k",
        "audio_codec": "aac",
        "audio_bitrate": "128k",
        "creation_time": "2024-01-01T12:00:00Z"
    },
    "test_video_02.mp4": {
        "duration": 450.2,
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "codec": "h264",
        "bitrate": "5000k",
        "audio_codec": "aac",
        "audio_bitrate": "128k",
        "creation_time": "2024-01-02T12:00:00Z"
    },
    "test_video_03.mp4": {
        "duration": 600.8,
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "codec": "h264",
        "bitrate": "5000k",
        "audio_codec": "aac",
        "audio_bitrate": "128k",
        "creation_time": "2024-01-03T12:00:00Z"
    }
}

# Sample ffprobe output for testing
SAMPLE_FFPROBE_OUTPUT = {
    "streams": [
        {
            "index": 0,
            "codec_name": "h264",
            "codec_type": "video",
            "width": 1920,
            "height": 1080,
            "r_frame_rate": "30/1",
            "avg_frame_rate": "30/1",
            "duration": "300.500000",
            "bit_rate": "5000000"
        },
        {
            "index": 1,
            "codec_name": "aac",
            "codec_type": "audio",
            "sample_rate": "48000",
            "channels": 2,
            "duration": "300.500000",
            "bit_rate": "128000"
        }
    ],
    "format": {
        "filename": "test_video.mp4",
        "nb_streams": 2,
        "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
        "duration": "300.500000",
        "size": "187812500",
        "bit_rate": "5000000",
        "tags": {
            "creation_time": "2024-01-01T12:00:00.000000Z"
        }
    }
}

# Sample VTT transcript content
SAMPLE_VTT_CONTENT = """WEBVTT

00:00:00.000 --> 00:00:05.000
Hello and welcome to this comprehensive video tutorial.

00:00:05.000 --> 00:00:10.000
Today we'll be exploring advanced video processing techniques.

00:00:10.000 --> 00:00:15.000
We'll start with the basics of video manipulation and encoding.

00:00:15.000 --> 00:00:20.000
Then we'll move on to more complex operations like concatenation.

00:00:20.000 --> 00:00:25.000
Finally, we'll discuss automated transcript generation and SEO optimization.
"""

# Sample Groq API response for transcription
SAMPLE_GROQ_RESPONSE = {
    "text": "Hello and welcome to this comprehensive video tutorial. Today we'll be exploring advanced video processing techniques.",
    "segments": [
        {
            "id": 0,
            "seek": 0,
            "start": 0.0,
            "end": 5.0,
            "text": " Hello and welcome to this comprehensive video tutorial.",
            "tokens": [50364, 2425, 293, 2928, 281, 341, 13914, 960, 10686, 13, 50614],
            "temperature": 0.0,
            "avg_logprob": -0.2876847982406616,
            "compression_ratio": 1.0
        },
        {
            "id": 1,
            "seek": 500,
            "start": 5.0,
            "end": 10.0,
            "text": " Today we'll be exploring advanced video processing techniques.",
            "tokens": [50614, 2692, 321, 603, 312, 12736, 7339, 960, 9007, 7512, 13, 50864],
            "temperature": 0.0,
            "avg_logprob": -0.2876847982406616,
            "compression_ratio": 1.0
        }
    ],
    "language": "en"
}

# Sample OpenAI API response for description generation
SAMPLE_OPENAI_DESCRIPTION_RESPONSE = {
    "choices": [{
        "message": {
            "content": """# Advanced Video Processing Tutorial

This comprehensive tutorial covers essential video processing techniques using Python and modern tools. Learn how to manipulate, encode, and optimize videos for various platforms.

## Topics Covered
- Video encoding and compression techniques
- Automated transcript generation using AI
- SEO optimization for video content
- Batch processing workflows
- Quality control and testing strategies

## Links
- GitHub Repository: https://github.com/example/video-tool
- Documentation: https://docs.example.com/video-processing
- Support Forum: https://forum.example.com

## Timestamps
00:00:00 - Introduction and Overview
00:05:00 - Basic Video Operations
00:10:00 - Advanced Processing Techniques
00:15:00 - Automation and Scripting
00:20:00 - Conclusion and Next Steps
"""
        }
    }]
}

# Sample OpenAI API response for SEO keywords
SAMPLE_OPENAI_KEYWORDS_RESPONSE = {
    "choices": [{
        "message": {
            "content": "video processing, python tutorial, ffmpeg, automation, video encoding, transcription, AI, machine learning, content creation, youtube optimization, SEO, video compression, batch processing, moviepy, audio processing"
        }
    }]
}

# Sample timestamps JSON structure
SAMPLE_TIMESTAMPS = [
    {
        "timestamps": [
            {
                "start": "00:00:00",
                "end": "00:05:00",
                "title": "test_video_01"
            },
            {
                "start": "00:05:00",
                "end": "00:12:30",
                "title": "test_video_02"
            },
            {
                "start": "00:12:30",
                "end": "00:22:30",
                "title": "test_video_03"
            }
        ],
        "metadata": {
            "creation_date": "2024-01-01T12:00:00Z",
            "total_duration": "00:22:30",
            "video_count": 3
        }
    }
]

# Sample CSV data for video metadata
SAMPLE_CSV_DATA = [
    ["creation_date", "video_title", "duration_minutes"],
    ["2024-01-01 12:00:00", "test_video_01", "5.0"],
    ["2024-01-02 12:00:00", "test_video_02", "7.5"],
    ["2024-01-03 12:00:00", "test_video_03", "10.0"]
]

# Sample description markdown content
SAMPLE_DESCRIPTION_MD = """# Test Video Tutorial

This is a comprehensive test video that demonstrates various video processing capabilities and testing methodologies.

## Topics Covered
- Video file manipulation and processing
- Automated testing strategies for media files
- Mock data generation for unit tests
- Integration testing with external APIs
- Performance optimization techniques

## Links
- Project Repository: https://github.com/test/video-tool
- Documentation: https://docs.test.com/video-processing
- API Reference: https://api.test.com/docs
- Community Support: https://community.test.com

## Timestamps
00:00:00 - Introduction and Setup
00:03:00 - Basic Video Operations
00:07:00 - Advanced Processing Techniques
00:12:00 - Testing and Quality Assurance
00:18:00 - Deployment and Optimization
00:22:00 - Conclusion and Resources
"""

# Sample keywords for SEO
SAMPLE_KEYWORDS = "video processing, python, automation, testing, ffmpeg, moviepy, audio processing, transcription, AI, machine learning, content creation, youtube, SEO, optimization, tutorial, programming, unit testing, mock data, integration testing"

# Error responses for testing error handling
SAMPLE_ERROR_RESPONSES = {
    "openai_rate_limit": {
        "error": {
            "message": "Rate limit exceeded",
            "type": "rate_limit_error",
            "code": "rate_limit_exceeded"
        }
    },
    "groq_auth_error": {
        "error": {
            "message": "Invalid API key",
            "type": "authentication_error",
            "code": "invalid_api_key"
        }
    },
    "ffmpeg_error": "ffmpeg: error while loading shared libraries",
    "file_not_found": "No such file or directory"
}

# Configuration for different test scenarios
TEST_SCENARIOS = {
    "small_dataset": {
        "video_count": 2,
        "total_duration": 600,  # 10 minutes
        "file_sizes": [50_000_000, 75_000_000]  # 50MB, 75MB
    },
    "medium_dataset": {
        "video_count": 5,
        "total_duration": 1800,  # 30 minutes
        "file_sizes": [100_000_000, 150_000_000, 200_000_000, 120_000_000, 180_000_000]
    },
    "large_dataset": {
        "video_count": 10,
        "total_duration": 3600,  # 60 minutes
        "file_sizes": [200_000_000] * 10  # 200MB each
    }
}