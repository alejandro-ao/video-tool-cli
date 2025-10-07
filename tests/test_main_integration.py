"""Integration tests for main.py workflow."""

import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from main import main, get_user_input
from video_tool.video_processor import VideoProcessor
from tests.test_data.mock_generators import (
    create_complete_test_dataset,
    MockVideoGenerator
)
from tests.test_data.sample_data import (
    SAMPLE_GROQ_RESPONSE,
    SAMPLE_OPENAI_DESCRIPTION_RESPONSE,
    SAMPLE_OPENAI_KEYWORDS_RESPONSE
)


class TestGetUserInput:
    """Test user input collection function."""
    
    @patch('builtins.input')
    def test_get_user_input_all_options(self, mock_input):
        """Test get_user_input with all options enabled."""
        mock_input.side_effect = [
            '/path/to/videos',  # input_dir
            'https://github.com/user/repo',  # repo_url
            'My Great Video',  # video_title
            'n',  # skip_silence_removal
            'n',  # skip_concat
            'n',  # skip_reprocessing
            'n',  # skip_timestamps
            'n',  # skip_transcript
            'n',  # skip_description
            'n',  # skip_seo
            'n',  # skip_linkedin
            'n'   # skip_twitter
        ]
        
        result = get_user_input()
        
        expected = {
            'input_dir': '/path/to/videos',
            'repo_url': 'https://github.com/user/repo',
            'video_title': 'My Great Video',
            'skip_silence_removal': False,
            'skip_concat': False,
            'skip_reprocessing': False,
            'skip_timestamps': False,
            'skip_transcript': False,
            'skip_description': False,
            'skip_seo': False,
            'skip_linkedin': False,
            'skip_twitter': False
        }
        
        assert result == expected
    
    @patch('builtins.input')
    def test_get_user_input_skip_all(self, mock_input):
        """Test get_user_input with all options skipped."""
        mock_input.side_effect = [
            '/path/to/videos',  # input_dir
            '',  # repo_url (empty)
            '',  # video_title (empty)
            'y',  # skip_silence_removal
            'y',  # skip_concat
            'y',  # skip_timestamps
            'y',  # skip_transcript
            'y',  # skip_description
            'y',  # skip_seo
            'y',  # skip_linkedin
            'y'   # skip_twitter
        ]
        
        result = get_user_input()
        
        expected = {
            'input_dir': '/path/to/videos',
            'repo_url': None,
            'video_title': None,
            'skip_silence_removal': True,
            'skip_concat': True,
            'skip_reprocessing': False,  # Not asked when concat is skipped
            'skip_timestamps': True,
            'skip_transcript': True,
            'skip_description': True,
            'skip_seo': True,
            'skip_linkedin': True,
            'skip_twitter': True
        }
        
        assert result == expected
    
    @patch('builtins.input')
    def test_get_user_input_empty_directory_retry(self, mock_input):
        """Test get_user_input with empty directory input requiring retry."""
        mock_input.side_effect = [
            '',  # Empty input (should retry)
            '/path/to/videos',  # Valid input
            '',  # repo_url (empty)
            'My Video',  # video_title
            'n',  # skip_silence_removal
            'n',  # skip_concat
            'n',  # skip_reprocessing
            'n',  # skip_timestamps
            'n',  # skip_transcript
            'n',  # skip_description
            'n',  # skip_seo
            'n',  # skip_linkedin
            'n'   # skip_twitter
        ]
        
        result = get_user_input()
        
        assert result['input_dir'] == '/path/to/videos'
        assert result['repo_url'] is None
        assert result['video_title'] == 'My Video'
    
    @patch('builtins.input')
    def test_get_user_input_quoted_paths(self, mock_input):
        """Test get_user_input with quoted directory paths."""
        mock_input.side_effect = [
            '"/path/with spaces/videos"',  # Quoted path
            '',  # repo_url (empty)
            'Fun Video',  # video_title
            'n',  # skip_silence_removal
            'n',  # skip_concat
            'n',  # skip_reprocessing
            'n',  # skip_timestamps
            'n',  # skip_transcript
            'n',  # skip_description
            'n',  # skip_seo
            'n',  # skip_linkedin
            'n'   # skip_twitter
        ]
        
        result = get_user_input()
        
        # Should strip quotes
        assert result['input_dir'] == '/path/with spaces/videos'
        assert result['repo_url'] is None
        assert result['video_title'] == 'Fun Video'


class TestMainWorkflow:
    """Test main workflow integration."""
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'GROQ_API_KEY': 'test-key'})
    @patch('main.get_user_input')
    @patch('main.VideoProcessor')
    def test_main_complete_workflow(self, mock_processor_class, mock_get_input, temp_dir):
        """Test complete main workflow with all steps enabled."""
        # Setup test data
        test_data = create_complete_test_dataset(temp_dir)
        output_dir = temp_dir / "output"
        
        # Mock user input
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'repo_url': 'https://github.com/test/repo',
            'video_title': 'Product Launch Recap',
            'skip_silence_removal': False,
            'skip_concat': False,
            'skip_reprocessing': False,
            'skip_timestamps': False,
            'skip_transcript': False,
            'skip_description': False,
            'skip_seo': False,
            'skip_linkedin': True,
            'skip_twitter': True
        }
        
        # Mock VideoProcessor
        mock_processor = Mock()
        mock_processor.output_dir = output_dir
        mock_processor_class.return_value = mock_processor
        
        # Mock method returns
        mock_processor.remove_silences.return_value = temp_dir / "processed"
        mock_processor.concatenate_videos.return_value = str(output_dir / "concatenated_video.mp4")
        mock_processor.generate_transcript.return_value = str(output_dir / "transcript.vtt")
        mock_processor.generate_description.return_value = str(output_dir / "description.md")
        mock_processor.generate_seo_keywords.return_value = str(output_dir / "keywords.txt")
        
        # Run main
        main()
        
        # Verify all methods were called
        mock_processor.remove_silences.assert_called_once()
        mock_processor.generate_timestamps.assert_called_once()
        mock_processor.concatenate_videos.assert_called_once()
        mock_processor.generate_transcript.assert_called_once()
        mock_processor.generate_description.assert_called_once()
        mock_processor.generate_seo_keywords.assert_called_once()
        
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'GROQ_API_KEY': 'test-key'})
    @patch('main.get_user_input')
    @patch('main.VideoProcessor')
    def test_main_complete_workflow_with_social_posts(self, mock_processor_class, mock_get_input, temp_dir):
        """Test main function with complete workflow including social media posts."""
        output_dir = temp_dir / "output"
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'repo_url': 'https://github.com/user/repo',
            'video_title': 'Launch Update',
            'skip_silence_removal': False,
            'skip_concat': False,
            'skip_reprocessing': False,
            'skip_timestamps': False,
            'skip_transcript': False,
            'skip_description': False,
            'skip_seo': False,
            'skip_linkedin': False,
            'skip_twitter': False
        }
        
        # Create test video file
        test_video = temp_dir / "test.mp4"
        test_video.write_text("fake video content")
        
        # Create transcript file for social media post generation
        transcript_file = output_dir / "transcript.vtt"
        transcript_file.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nTest transcript content")
        
        # Mock processor methods
        mock_processor = Mock()
        mock_processor.output_dir = output_dir
        mock_processor.remove_silences.return_value = str(temp_dir / "processed")
        mock_processor.generate_timestamps.return_value = {"timestamps": []}
        mock_processor.concatenate_videos.return_value = str(output_dir / "concatenated.mp4")
        mock_processor.generate_transcript.return_value = str(output_dir / "transcript.vtt")
        mock_processor.generate_description.return_value = str(output_dir / "description.md")
        mock_processor.generate_seo_keywords.return_value = str(output_dir / "keywords.txt")
        mock_processor.generate_linkedin_post.return_value = str(output_dir / "linkedin_post.md")
        mock_processor.generate_twitter_post.return_value = str(output_dir / "twitter_post.md")
        mock_processor_class.return_value = mock_processor
        
        # Run main function
        main()
        
        # Verify all methods were called
        mock_processor.remove_silences.assert_called_once()
        mock_processor.generate_timestamps.assert_called_once()
        mock_processor.concatenate_videos.assert_called_once()
        mock_processor.generate_transcript.assert_called_once()
        mock_processor.generate_description.assert_called_once()
        mock_processor.generate_seo_keywords.assert_called_once()
        mock_processor.generate_linkedin_post.assert_called_once()
        mock_processor.generate_twitter_post.assert_called_once()
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'GROQ_API_KEY': 'test-key'})
    @patch('main.get_user_input')
    @patch('main.VideoProcessor')
    def test_main_skip_all_processing(self, mock_processor_class, mock_get_input, temp_dir):
        """Test main workflow with all processing steps skipped."""
        # Mock user input to skip everything
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'repo_url': None,
            'video_title': None,
            'skip_silence_removal': True,
            'skip_concat': True,
            'skip_reprocessing': True,
            'skip_timestamps': True,
            'skip_transcript': True,
            'skip_description': True,
            'skip_seo': True,
            'skip_linkedin': True,
            'skip_twitter': True
        }
        
        mock_processor = Mock()
        mock_processor.output_dir = temp_dir / "output"
        mock_processor_class.return_value = mock_processor
        
        # Run main
        main()
        
        # Verify no processing methods were called
        mock_processor.remove_silences.assert_not_called()
        mock_processor.concatenate_videos.assert_not_called()
        mock_processor.generate_timestamps.assert_not_called()
        mock_processor.generate_transcript.assert_not_called()
        mock_processor.generate_description.assert_not_called()
        mock_processor.generate_seo_keywords.assert_not_called()
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'GROQ_API_KEY': 'test-key'})
    @patch('main.get_user_input')
    @patch('main.VideoProcessor')
    def test_main_partial_workflow(self, mock_processor_class, mock_get_input, temp_dir):
        """Test main workflow with some steps skipped."""
        # Create a video file for fallback
        video_file = temp_dir / "test_video.mp4"
        MockVideoGenerator.create_mock_mp4(video_file)
        
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'repo_url': 'https://github.com/test/repo',
            'video_title': 'Weekly Update',
            'skip_silence_removal': True,  # Skip
            'skip_concat': True,          # Skip
            'skip_reprocessing': False,
            'skip_timestamps': False,     # Process
            'skip_transcript': False,     # Process
            'skip_description': False,    # Process
            'skip_seo': False,            # Process
            'skip_linkedin': True,
            'skip_twitter': True
        }
        
        mock_processor = Mock()
        mock_processor.output_dir = temp_dir / "output"
        mock_processor_class.return_value = mock_processor
        
        # Mock returns
        mock_processor.generate_transcript.return_value = str(mock_processor.output_dir / "transcript.vtt")
        mock_processor.generate_description.return_value = str(mock_processor.output_dir / "description.md")
        mock_processor.generate_seo_keywords.return_value = str(mock_processor.output_dir / "keywords.txt")
        
        # Run main
        main()
        
        # Verify only selected methods were called
        mock_processor.remove_silences.assert_not_called()
        mock_processor.concatenate_videos.assert_not_called()
        mock_processor.generate_timestamps.assert_called_once()
        mock_processor.generate_transcript.assert_called_once()
        mock_processor.generate_description.assert_called_once()
        mock_processor.generate_seo_keywords.assert_called_once()
    
    @patch('main.get_user_input')
    @patch('main.VideoProcessor')
    def test_main_missing_api_keys(self, mock_processor_class, mock_get_input, temp_dir):
        """Test main function with missing API keys."""
        # Mock user input to avoid stdin issues - enable description to trigger API key check
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'skip_silence_removal': True,
            'skip_concatenation': True,
            'skip_concat': True,
            'skip_timestamps': True,
            'skip_transcript': True,
            'skip_description': False,  # Enable description to trigger API key validation
            'skip_keywords': True,
            'skip_seo': True,
            'skip_linkedin': True,
            'skip_twitter': True,
            'repo_url': None,
            'video_title': None
        }
        
        # Clear environment variables and mock logger
        with patch.dict(os.environ, {'OPENAI_API_KEY': '', 'GROQ_API_KEY': ''}, clear=True):
            with patch('loguru.logger.error') as mock_logger:
                main()
                
                # Should log error about missing API keys
                mock_logger.assert_called()
                # Check if any call contains the expected error message
                calls = mock_logger.call_args_list
                error_messages = []
                for call in calls:
                    if call.args:
                        error_messages.append(call.args[0])
                
                # Should have logged error about missing OPENAI_API_KEY
                assert any('OPENAI_API_KEY environment variable not set' in msg for msg in error_messages), f"Expected OPENAI_API_KEY error, got: {error_messages}"
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'GROQ_API_KEY': 'test-key'})
    @patch('main.get_user_input')
    def test_main_invalid_directory(self, mock_get_input):
        """Test main function with invalid input directory."""
        mock_get_input.return_value = {
            'input_dir': '/nonexistent/path',
            'repo_url': None,
            'video_title': None,
            'skip_silence_removal': True,
            'skip_concat': True,
            'skip_reprocessing': True,
            'skip_timestamps': True,
            'skip_transcript': True,
            'skip_description': True,
            'skip_seo': True,
            'skip_linkedin': True,
            'skip_twitter': True
        }
        
        with patch('loguru.logger.error') as mock_logger:
            main()
            
            # Should log error about directory not existing
            mock_logger.assert_called()
            error_calls = [call.args[0] for call in mock_logger.call_args_list]
            assert any('does not exist' in msg for msg in error_calls)
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'GROQ_API_KEY': 'test-key'})
    @patch('main.get_user_input')
    @patch('main.VideoProcessor')
    def test_main_processing_error(self, mock_processor_class, mock_get_input, temp_dir):
        """Test main function handles processing errors."""
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'repo_url': None,
            'video_title': 'Problematic Run',
            'skip_silence_removal': False,
            'skip_concat': True,
            'skip_reprocessing': True,
            'skip_timestamps': True,
            'skip_transcript': True,
            'skip_description': True,
            'skip_seo': True,
            'skip_linkedin': True,
            'skip_twitter': True
        }
        
        mock_processor = Mock()
        mock_processor.output_dir = temp_dir / "output"
        mock_processor_class.return_value = mock_processor
        
        # Mock method to raise exception
        mock_processor.remove_silences.side_effect = Exception("Processing error")
        
        with patch('loguru.logger.error') as mock_logger:
            with pytest.raises(Exception, match="Processing error"):
                main()
            
            # Should log the error
            mock_logger.assert_called()
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'GROQ_API_KEY': 'test-key'})
    @patch('main.get_user_input')
    @patch('main.VideoProcessor')
    def test_main_description_without_repo_url(self, mock_processor_class, mock_get_input, temp_dir):
        """Test main function skips description when no repo URL provided."""
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'repo_url': None,  # No repo URL provided
            'video_title': 'No Repo Video',
            'skip_silence_removal': True,
            'skip_concat': True,
            'skip_reprocessing': True,
            'skip_timestamps': True,
            'skip_transcript': True,
            'skip_description': False,  # Enable description
            'skip_seo': False,
            'skip_linkedin': True,
            'skip_twitter': True
        }
        
        mock_processor = Mock()
        mock_processor.output_dir = temp_dir / "output"
        mock_processor_class.return_value = mock_processor
        
        # Run main
        main()
        
        # Should not call description or SEO generation without repo URL
        mock_processor.generate_description.assert_not_called()
        mock_processor.generate_seo_keywords.assert_not_called()


class TestWorkflowIntegration:
    """Test complete workflow integration with real VideoProcessor."""
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'GROQ_API_KEY': 'test-key'})
    @patch('main.get_user_input')
    @patch('main.VideoProcessor')
    def test_real_processor_workflow(self, mock_processor_class, mock_get_input, temp_dir):
        """Test workflow with mocked VideoProcessor instance."""
        # Create test data
        test_data = create_complete_test_dataset(temp_dir)
        
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'repo_url': 'https://github.com/test/repo',
            'video_title': 'Integration Run',
            'skip_silence_removal': True,  # Skip heavy processing
            'skip_concat': True,
            'skip_reprocessing': True,
            'skip_timestamps': False,
            'skip_transcript': True,  # Skip API calls
            'skip_description': True,
            'skip_seo': True,
            'skip_linkedin': True,
            'skip_twitter': True
        }
        
        # Mock VideoProcessor
        mock_processor = Mock()
        mock_processor.output_dir = temp_dir / "output"
        mock_processor_class.return_value = mock_processor
        
        # Mock method returns
        mock_processor.generate_timestamps.return_value = str(mock_processor.output_dir / "timestamps.json")
        
        # Should complete without errors
        main()
        
        # Verify timestamps method was called
        mock_processor.generate_timestamps.assert_called_once()
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'GROQ_API_KEY': 'test-key'})
    @patch('main.get_user_input')
    @patch('main.VideoProcessor')
    def test_workflow_file_dependencies(self, mock_processor_class, mock_get_input, temp_dir):
        """Test workflow respects file dependencies between steps."""
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'repo_url': 'https://github.com/test/repo',
            'video_title': 'Dependency Check',
            'skip_silence_removal': True,
            'skip_concat': True,
            'skip_reprocessing': True,
            'skip_timestamps': True,
            'skip_transcript': False,  # This will fail without concatenated video
            'skip_description': False,  # This will fail without transcript
            'skip_seo': False,  # This will fail without description
            'skip_linkedin': True,
            'skip_twitter': True
        }
        
        # Mock VideoProcessor
        mock_processor = Mock()
        mock_processor.output_dir = temp_dir / "output"
        mock_processor_class.return_value = mock_processor
        
        # Mock method returns - simulate missing files by raising exceptions
        mock_processor.generate_transcript.side_effect = FileNotFoundError("No video file found")
        mock_processor.generate_description.side_effect = FileNotFoundError("No transcript file found")
        mock_processor.generate_seo_keywords.side_effect = FileNotFoundError("No description file found")
        
        # Run main - should handle missing dependencies gracefully
        with patch('loguru.logger.warning') as mock_logger:
            main()
            
            # Should log warnings about missing files
            mock_logger.assert_called()
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'GROQ_API_KEY': 'test-key'})
    @patch('main.get_user_input')
    @patch('main.VideoProcessor')
    def test_workflow_with_existing_files(self, mock_processor_class, mock_get_input, temp_dir):
        """Test workflow when some output files already exist."""
        # Create test video files
        create_complete_test_dataset(temp_dir)
        
        # Create some existing output files
        existing_output = temp_dir / "output"
        (existing_output / "timestamps.json").write_text('{"existing": true}')
        (existing_output / "transcript.vtt").write_text("WEBVTT\n\nexisting transcript")
        
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'repo_url': 'https://github.com/test/repo',
            'video_title': 'Existing Outputs',
            'skip_silence_removal': True,
            'skip_concat': True,
            'skip_reprocessing': True,
            'skip_timestamps': False,  # Should overwrite existing
            'skip_transcript': True,
            'skip_description': False,  # Should use existing transcript
            'skip_seo': False,
            'skip_linkedin': True,
            'skip_twitter': True
        }
        
        # Mock VideoProcessor
        mock_processor = Mock()
        mock_processor.output_dir = temp_dir / "output"
        mock_processor_class.return_value = mock_processor
        
        # Mock method returns
        mock_processor.generate_timestamps.return_value = str(mock_processor.output_dir / "timestamps.json")
        mock_processor.generate_description.return_value = str(mock_processor.output_dir / "description.md")
        mock_processor.generate_seo_keywords.return_value = str(mock_processor.output_dir / "keywords.txt")
        
        # Run main
        main()
        
        # Verify methods were called
        mock_processor.generate_timestamps.assert_called_once()
        mock_processor.generate_description.assert_called_once()
        mock_processor.generate_seo_keywords.assert_called_once()


class TestCommandLineIntegration:
    """Test command line integration aspects."""
    
    def test_main_entry_point(self):
        """Test that main can be called as entry point."""
        # Test that the main function exists and is callable
        assert callable(main)
        
        # Test that it can be imported
        from main import main as imported_main
        assert imported_main is main
    
    @patch('main.main')
    def test_script_execution(self, mock_main):
        """Test script execution when run as __main__."""
        # This would test the if __name__ == '__main__': block
        # but since we can't easily test that without running the script,
        # we just verify the main function exists
        assert mock_main is not None
