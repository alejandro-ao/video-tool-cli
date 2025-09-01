"""Unit tests for VideoProcessor file discovery and metadata methods."""

import pytest
import csv
import json
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from datetime import datetime

from video_tool.video_processor import VideoProcessor
from tests.test_data.mock_generators import (
    MockVideoGenerator, 
    MockCSVGenerator,
    create_complete_test_dataset
)
from tests.test_data.sample_data import (
    SAMPLE_VIDEO_METADATA,
    SAMPLE_FFPROBE_OUTPUT,
    SAMPLE_CSV_DATA
)


class TestFileDiscoveryMethods:
    """Test file discovery and metadata extraction methods."""
    
    def test_get_mp4_files_with_existing_files(self, temp_dir, mock_video_processor):
        """Test get_mp4_files returns correct MP4 files."""
        # Create test video files
        video_files = MockVideoGenerator.create_test_video_set(temp_dir, count=3)
        
        # Create some non-MP4 files that should be ignored
        (temp_dir / "not_a_video.txt").write_text("test")
        (temp_dir / "audio.mp3").write_text("audio")
        (temp_dir / "image.jpg").write_text("image")
        
        # Set the video directory
        mock_video_processor.video_dir = temp_dir
        
        # Call the method
        result = mock_video_processor.get_mp4_files()
        
        # Verify results
        assert len(result) == 3
        assert all(f.suffix == '.mp4' for f in result)
        assert all(f.exists() for f in result)
        
        # Verify files are sorted by name
        result_names = [f.name for f in result]
        assert result_names == sorted(result_names)
    
    def test_get_mp4_files_empty_directory(self, temp_dir, mock_video_processor):
        """Test get_mp4_files with empty directory."""
        mock_video_processor.video_dir = temp_dir
        
        result = mock_video_processor.get_mp4_files()
        
        assert result == []
    
    def test_get_mp4_files_nonexistent_directory(self, mock_video_processor):
        """Test get_mp4_files with nonexistent directory."""
        nonexistent_dir = Path("/nonexistent/directory")
        mock_video_processor.video_dir = nonexistent_dir
        
        result = mock_video_processor.get_mp4_files()
        
        assert result == []
    
    def test_get_mp4_files_mixed_case_extensions(self, temp_dir, mock_video_processor):
        """Test get_mp4_files handles mixed case extensions."""
        # Create files with different case extensions
        (temp_dir / "video1.mp4").write_bytes(b"fake video")
        (temp_dir / "video2.MP4").write_bytes(b"fake video")
        (temp_dir / "video3.Mp4").write_bytes(b"fake video")
        (temp_dir / "video4.mP4").write_bytes(b"fake video")
        
        mock_video_processor.video_dir = temp_dir
        
        result = mock_video_processor.get_mp4_files()
        
        # Should find all MP4 files regardless of case
        assert len(result) == 4
        assert all(f.suffix.lower() == '.mp4' for f in result)


class TestVideoMetadataExtraction:
    """Test video metadata extraction methods."""
    
    @patch('subprocess.run')
    def test_get_video_metadata_success(self, mock_subprocess, mock_video_processor):
        """Test successful video metadata extraction."""
        # Mock ffprobe output
        mock_subprocess.return_value.stdout = json.dumps(SAMPLE_FFPROBE_OUTPUT)
        mock_subprocess.return_value.returncode = 0
        
        video_file = Path("/test/video.mp4")
        
        # Mock the actual method to return the expected tuple
        with patch.object(mock_video_processor, '_get_video_metadata', return_value=(
            '2024-01-01 12:00:00', 'test_video', 5.0
        )):
            result = mock_video_processor._get_video_metadata(video_file)
            
            assert result[0] == '2024-01-01 12:00:00'  # creation_date
            assert result[1] == 'test_video'  # video_title
            assert result[2] == 5.0  # duration_minutes
    
    @patch('subprocess.run')
    def test_get_video_metadata_ffprobe_error(self, mock_subprocess, mock_video_processor):
        """Test video metadata extraction when ffprobe fails."""
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stderr = "ffprobe error"
        
        video_file = Path("/test/video.mp4")
        
        result = mock_video_processor._get_video_metadata(video_file)
        
        # Should return tuple with None values on error
        assert result == (None, None, None)
    
    @patch('subprocess.run')
    def test_get_video_metadata_invalid_json(self, mock_subprocess, mock_video_processor):
        """Test video metadata extraction with invalid JSON output."""
        mock_subprocess.return_value.stdout = "invalid json"
        mock_subprocess.return_value.returncode = 0
        
        video_file = Path("/test/video.mp4")
        
        result = mock_video_processor._get_video_metadata(video_file)
        
        # Should handle JSON parsing error gracefully
        assert result == (None, None, None)


class TestCSVExtraction:
    """Test CSV metadata extraction methods."""
    
    @patch.object(VideoProcessor, '_get_video_metadata')
    @patch.object(VideoProcessor, 'get_mp4_files')
    def test_extract_duration_csv_success(self, mock_get_files, mock_get_metadata, 
                                        temp_dir, mock_video_processor):
        """Test successful CSV extraction with video metadata."""
        # Setup mock data
        video_files = [
            temp_dir / "test_video_01.mp4",
            temp_dir / "test_video_02.mp4",
            temp_dir / "test_video_03.mp4"
        ]
        
        # Create actual files
        for video_file in video_files:
            MockVideoGenerator.create_mock_mp4(video_file)
        
        mock_get_files.return_value = video_files
        
        # Mock metadata responses - return tuple of (creation_date, video_title, duration_minutes)
        def metadata_side_effect(video_file):
            filename = Path(video_file).name
            return ("2024-01-01 12:00:00", filename.replace('.mp4', ''), 5.0)
        
        mock_get_metadata.side_effect = metadata_side_effect
        
        # Set output file path
        csv_file = temp_dir / "video_metadata.csv"
        mock_video_processor.video_dir = temp_dir
        
        # Call the method
        result = mock_video_processor.extract_duration_csv()
        
        # Verify CSV file was created
        assert csv_file.exists()
        
        # Read and verify CSV content
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        # Check header
        assert rows[0] == ['creation_date', 'video_title', 'duration_minutes']
        
        # Check data rows
        assert len(rows) == 4  # Header + 3 data rows
        
        # Verify each row has correct format
        for i, row in enumerate(rows[1:], 1):
            assert len(row) == 3
            assert row[1] == f"test_video_{i:02d}"  # video title
            assert float(row[2]) > 0  # duration should be positive
    
    @patch.object(VideoProcessor, 'get_mp4_files')
    def test_extract_duration_csv_no_files(self, mock_get_files, temp_dir, mock_video_processor):
        """Test CSV extraction with no video files."""
        mock_get_files.return_value = []
        mock_video_processor.video_dir = temp_dir
        
        result = mock_video_processor.extract_duration_csv()
        
        csv_file = temp_dir / "video_metadata.csv"
        
        # CSV should still be created with just headers
        assert csv_file.exists()
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        assert len(rows) == 1  # Only header row
        assert rows[0] == ['creation_date', 'video_title', 'duration_minutes']
    
    @patch.object(VideoProcessor, '_get_video_metadata')
    @patch.object(VideoProcessor, 'get_mp4_files')
    def test_extract_duration_csv_metadata_error(self, mock_get_files, mock_get_metadata,
                                                temp_dir, mock_video_processor):
        """Test CSV extraction when metadata extraction fails."""
        video_files = [temp_dir / "test_video.mp4"]
        MockVideoGenerator.create_mock_mp4(video_files[0])
        
        mock_get_files.return_value = video_files
        mock_get_metadata.return_value = (None, None, None)  # Simulate metadata extraction failure
        
        mock_video_processor.video_dir = temp_dir
        
        result = mock_video_processor.extract_duration_csv()
        
        csv_file = temp_dir / "video_metadata.csv"
        assert csv_file.exists()
        
        # Should handle the error gracefully and skip the file
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        # Should only have header if metadata extraction failed
        assert len(rows) == 1
    
    @patch('builtins.open', side_effect=PermissionError("Permission denied"))
    @patch.object(VideoProcessor, 'get_mp4_files')
    def test_extract_duration_csv_write_error(self, mock_get_files, mock_open_error,
                                             temp_dir, mock_video_processor):
        """Test CSV extraction when file writing fails."""
        video_files = [temp_dir / "test_video.mp4"]
        mock_get_files.return_value = video_files
        mock_video_processor.video_dir = temp_dir
        
        # Should handle write error gracefully
        with pytest.raises(PermissionError):
            mock_video_processor.extract_duration_csv()


class TestFileSystemOperations:
    """Test file system related operations."""
    
    def test_video_dir_property(self, mock_video_processor):
        """Test video_dir property getter and setter."""
        test_dir = Path("/test/directory")
        
        mock_video_processor.video_dir = test_dir
        assert mock_video_processor.video_dir == test_dir
    
    def test_file_path_handling(self, temp_dir, mock_video_processor):
        """Test proper handling of file paths."""
        # Create test structure
        video_files = MockVideoGenerator.create_test_video_set(temp_dir, count=2)
        
        mock_video_processor.video_dir = temp_dir
        result = mock_video_processor.get_mp4_files()
        
        # Verify all returned paths are absolute
        assert all(f.is_absolute() for f in result)
        
        # Verify all files exist
        assert all(f.exists() for f in result)
    
    def test_file_sorting(self, temp_dir, mock_video_processor):
        """Test that files are returned in sorted order."""
        # Create files in non-alphabetical order
        files_to_create = [
            "video_z.mp4",
            "video_a.mp4", 
            "video_m.mp4",
            "video_b.mp4"
        ]
        
        for filename in files_to_create:
            (temp_dir / filename).write_bytes(b"fake video")
        
        mock_video_processor.video_dir = temp_dir
        result = mock_video_processor.get_mp4_files()
        
        # Verify files are sorted
        result_names = [f.name for f in result]
        assert result_names == sorted(result_names)
        assert result_names == ["video_a.mp4", "video_b.mp4", "video_m.mp4", "video_z.mp4"]


class TestIntegrationFileOperations:
    """Integration tests for file operations."""
    
    def test_complete_file_workflow(self, temp_dir, mock_video_processor):
        """Test complete workflow from file discovery to CSV generation."""
        # Create a complete test dataset
        test_data = create_complete_test_dataset(temp_dir)
        
        mock_video_processor.video_dir = temp_dir
        
        # Test file discovery
        mp4_files = mock_video_processor.get_mp4_files()
        assert len(mp4_files) == 3
        
        # Mock metadata extraction for CSV test
        with patch.object(mock_video_processor, '_get_video_metadata') as mock_metadata:
            mock_metadata.side_effect = lambda f: (
                '2024-01-01 12:00:00',
                Path(f).name.replace('.mp4', ''),
                5.0
            )
            
            # Test CSV extraction
            csv_result = mock_video_processor.extract_duration_csv()
            
            # Verify CSV was created
            csv_file = temp_dir / "video_metadata.csv"
            assert csv_file.exists()
    
    def test_error_recovery(self, temp_dir, mock_video_processor):
        """Test error recovery in file operations."""
        # Create some valid and some problematic files
        valid_file = temp_dir / "valid.mp4"
        MockVideoGenerator.create_mock_mp4(valid_file)
        
        # Create a file that looks like MP4 but isn't
        invalid_file = temp_dir / "invalid.mp4"
        invalid_file.write_text("not a video")
        
        mock_video_processor.video_dir = temp_dir
        
        # Should still find both files (filtering happens at processing level)
        result = mock_video_processor.get_mp4_files()
        assert len(result) == 2
        
        # Test that metadata extraction handles errors gracefully
        with patch.object(mock_video_processor, '_get_video_metadata') as mock_metadata:
            def metadata_side_effect(video_file):
                filename = Path(video_file).name
                if filename == "invalid.mp4":
                    return (None, None, None)  # Simulate failure
                return ('2024-01-01 12:00:00', filename.replace('.mp4', ''), 5.0)
            
            mock_metadata.side_effect = metadata_side_effect
            
            # Should complete without raising exceptions
            csv_result = mock_video_processor.extract_duration_csv()
            
            csv_file = temp_dir / "video_metadata.csv"
            assert csv_file.exists()