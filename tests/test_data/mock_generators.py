import os
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import tempfile
import numpy as np

try:
    from moviepy import VideoClip, AudioClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False


class MockVideoGenerator:
    """Generate mock video files for testing."""
    
    @staticmethod
    def create_mock_mp4(file_path: Path, duration_seconds: float = 10.0, 
                       width: int = 1920, height: int = 1080) -> Path:
        """Create a mock MP4 file.
        
        If moviepy is available, creates a real video file.
        Otherwise, creates a dummy file for basic tests.
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        if MOVIEPY_AVAILABLE:
            try:
                # Create a simple colored video
                def make_frame(t):
                    # Create a simple gradient that changes over time
                    color_value = int(128 + 127 * np.sin(2 * np.pi * t / duration_seconds))
                    frame = np.full((height, width, 3), color_value, dtype=np.uint8)
                    return frame
                
                # Create video clip
                video = VideoClip(make_frame, duration=duration_seconds)
                
                # Create simple audio (sine wave)
                def make_audio(t):
                    return np.sin(2 * np.pi * 440 * t)  # 440 Hz tone
                
                audio = AudioClip(make_audio, duration=duration_seconds)
                video = video.set_audio(audio)
                
                # Write video file
                video.write_videofile(str(file_path), verbose=False, logger=None)
                video.close()
                
            except Exception:
                # Fallback to dummy file if moviepy fails
                MockVideoGenerator._create_dummy_mp4(file_path, duration_seconds)
        else:
            # Create dummy file when moviepy not available
            MockVideoGenerator._create_dummy_mp4(file_path, duration_seconds)
        
        # Set file modification time to simulate creation date
        timestamp = datetime(2024, 1, 1, 12, 0, 0).timestamp()
        os.utime(file_path, (timestamp, timestamp))
        
        return file_path
    
    @staticmethod
    def _create_dummy_mp4(file_path: Path, duration_seconds: float = 10.0):
        """Create a dummy MP4 file for basic tests."""
        # Create MP4-like header (simplified)
        mp4_header = (
            b'\x00\x00\x00\x20'  # Box size
            b'ftyp'              # Box type
            b'mp42'              # Major brand
            b'\x00\x00\x00\x00'  # Minor version
            b'mp42isom'          # Compatible brands
        )
        
        # Add some dummy data to simulate video content
        dummy_data = b'\x00' * int(duration_seconds * 1000)  # Rough size simulation
        
        file_path.write_bytes(mp4_header + dummy_data)
    
    @staticmethod
    def create_test_video_set(base_dir: Path, count: int = 3) -> List[Path]:
        """Create a set of test video files."""
        files = []
        for i in range(count):
            file_path = base_dir / f"test_video_{i+1:02d}.mp4"
            duration = 10.0 + (i * 5.0)  # Varying durations
            MockVideoGenerator.create_mock_mp4(file_path, duration)
            files.append(file_path)
        return files


class MockAudioGenerator:
    """Generate mock audio files for testing."""
    
    @staticmethod
    def create_mock_mp3(file_path: Path, duration_seconds: float = 10.0) -> Path:
        """Create a mock MP3 file."""
        # MP3 header (simplified)
        mp3_header = b'\xff\xfb\x90\x00'  # MP3 sync word and header
        dummy_data = b'\x00' * int(duration_seconds * 1000)
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(mp3_header + dummy_data)
        
        return file_path


class MockTranscriptGenerator:
    """Generate mock transcript files for testing."""
    
    @staticmethod
    def create_vtt_transcript(file_path: Path, segments: Optional[List[Dict]] = None) -> Path:
        """Create a VTT transcript file."""
        if segments is None:
            segments = [
                {"start": 0.0, "end": 5.0, "text": "Hello and welcome to this video."},
                {"start": 5.0, "end": 10.0, "text": "Today we'll be discussing video processing."},
                {"start": 10.0, "end": 15.0, "text": "Let's get started with the basics."},
                {"start": 15.0, "end": 20.0, "text": "This is a test transcript for unit testing."}
            ]
        
        vtt_content = "WEBVTT\n\n"
        
        for segment in segments:
            start_time = MockTranscriptGenerator._format_timestamp(segment["start"])
            end_time = MockTranscriptGenerator._format_timestamp(segment["end"])
            vtt_content += f"{start_time} --> {end_time}\n"
            vtt_content += f"{segment['text']}\n\n"
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(vtt_content)
        
        return file_path
    
    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Format seconds to VTT timestamp format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    
    @staticmethod
    def create_vtt_file(file_path: Path, segments: Optional[List[Dict]] = None) -> Path:
        """Create a VTT file (alias for create_vtt_transcript for backward compatibility)."""
        return MockTranscriptGenerator.create_vtt_transcript(file_path, segments)


class MockDescriptionGenerator:
    """Generate mock description files for testing."""
    
    @staticmethod
    def create_description_md(file_path: Path, title: str = "Test Video") -> Path:
        """Create a markdown description file."""
        content = f"""# {title}

        This is a comprehensive test video that covers various aspects of video processing and testing methodologies.

        ## Topics Covered
        - Video processing techniques
        - Unit testing strategies
        - Mock data generation
        - File system operations
        - API integration testing

        ## Links
        - GitHub Repository: https://github.com/test/video-tool
        - Documentation: https://docs.test.com
        - Support: https://support.test.com

        ## Timestamps
        00:00:00 - Introduction
        00:05:00 - Main Content
        00:10:00 - Advanced Topics
        00:15:00 - Conclusion
        """
                
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        
        return file_path


class MockTimestampGenerator:
    """Generate mock timestamp files for testing."""
    
    @staticmethod
    def create_timestamps_json(file_path: Path, video_files: List[str]) -> Path:
        """Create a timestamps JSON file."""
        timestamps = []
        current_time = 0
        
        for video_file in video_files:
            duration = 300  # 5 minutes default
            start_time = current_time
            end_time = current_time + duration
            
            timestamps.append({
                "start": f"{start_time//3600:02d}:{(start_time%3600)//60:02d}:{start_time%60:02d}",
                "end": f"{end_time//3600:02d}:{(end_time%3600)//60:02d}:{end_time%60:02d}",
                "title": Path(video_file).stem
            })
            
            current_time = end_time
        
        video_info = [{
            "timestamps": timestamps,
            "metadata": {
                "creation_date": datetime.now().isoformat()
            }
        }]
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(video_info, indent=2))
        
        return file_path


class MockCSVGenerator:
    """Generate mock CSV files for testing."""
    
    @staticmethod
    def create_video_metadata_csv(file_path: Path, video_files: List[str]) -> Path:
        """Create a video metadata CSV file."""
        import csv
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['creation_date', 'video_title', 'duration_minutes'])
            
            for i, video_file in enumerate(video_files):
                creation_date = f"2024-01-{i+1:02d} 12:00:00"
                video_title = Path(video_file).stem
                duration_minutes = 5.0 + (i * 2.5)  # Varying durations
                writer.writerow([creation_date, video_title, duration_minutes])
        
        return file_path


class MockKeywordsGenerator:
    """Generate mock keywords files for testing."""
    
    @staticmethod
    def create_keywords_txt(file_path: Path) -> Path:
        """Create a keywords text file."""
        keywords = [
            "video processing", "python", "automation", "testing",
            "ffmpeg", "moviepy", "audio processing", "transcription",
            "AI", "machine learning", "content creation", "youtube",
            "SEO", "optimization", "tutorial", "programming"
        ]
        
        content = ", ".join(keywords)
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        
        return file_path


def create_complete_test_dataset(base_dir: Path) -> Dict[str, List[Path]]:
    """Create a complete test dataset with all file types."""
    base_dir.mkdir(parents=True, exist_ok=True)
    output_dir = base_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create video files
    video_files = MockVideoGenerator.create_test_video_set(base_dir, count=3)
    
    # Create processed directory with processed videos
    processed_dir = base_dir / "processed"
    processed_files = MockVideoGenerator.create_test_video_set(processed_dir, count=3)
    
    # Create audio files
    audio_files = []
    for video_file in video_files:
        audio_file = video_file.with_suffix('.mp3')
        MockAudioGenerator.create_mock_mp3(audio_file)
        audio_files.append(audio_file)
    
    # Create transcript
    transcript_file = output_dir / "transcript.vtt"
    MockTranscriptGenerator.create_vtt_transcript(transcript_file)
    
    # Create description
    description_file = output_dir / "description.md"
    MockDescriptionGenerator.create_description_md(description_file)
    
    # Create timestamps
    timestamps_file = output_dir / "timestamps.json"
    MockTimestampGenerator.create_timestamps_json(
        timestamps_file, [f.name for f in video_files]
    )
    
    # Create CSV metadata
    csv_file = output_dir / "video_metadata.csv"
    MockCSVGenerator.create_video_metadata_csv(
        csv_file, [f.name for f in video_files]
    )
    
    # Create keywords
    keywords_file = output_dir / "keywords.txt"
    MockKeywordsGenerator.create_keywords_txt(keywords_file)
    
    return {
        "videos": video_files,
        "processed_videos": processed_files,
        "audio": audio_files,
        "transcript": [transcript_file],
        "description": [description_file],
        "timestamps": [timestamps_file],
        "csv": [csv_file],
        "keywords": [keywords_file]
    }
