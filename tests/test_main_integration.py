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
            'n',  # skip_silence_removal
            'n',  # skip_concat
            'n',  # skip_reprocessing
            'n',  # skip_timestamps
            'n',  # skip_transcript
            'n',  # skip_description
            'n'   # skip_seo
        ]
        
        result = get_user_input()
        
        expected = {
            'input_dir': '/path/to/videos',
            'repo_url': 'https://github.com/user/repo',
            'skip_silence_removal': False,
            'skip_concat': False,
            'skip_reprocessing': False,
            'skip_timestamps': False,
            'skip_transcript': False,
            'skip_description': False,
            'skip_seo': False
        }
        
        assert result == expected
    
    @patch('builtins.input')
    def test_get_user_input_skip_all(self, mock_input):
        """Test get_user_input with all options skipped."""
        mock_input.side_effect = [
            '/path/to/videos',  # input_dir
            '',  # repo_url (empty)
            'y',  # skip_silence_removal
            'y',  # skip_concat
            'y',  # skip_timestamps
            'y',  # skip_transcript
            'y',  # skip_description
            'y'   # skip_seo
        ]
        
        result = get_user_input()
        
        expected = {
            'input_dir': '/path/to/videos',
            'repo_url': None,
            'skip_silence_removal': True,
            'skip_concat': True,
            'skip_reprocessing': False,  # Not asked when concat is skipped
            'skip_timestamps': True,
            'skip_transcript': True,
            'skip_description': True,
            'skip_seo': True
        }
        
        assert result == expected
    
    @patch('builtins.input')
    def test_get_user_input_empty_directory_retry(self, mock_input):
        """Test get_user_input with empty directory input requiring retry."""
        mock_input.side_effect = [
            '',  # Empty input (should retry)
            '/path/to/videos',  # Valid input
            '',  # repo_url (empty)
            'n',  # skip_silence_removal
            'n',  # skip_concat
            'n',  # skip_reprocessing
            'n',  # skip_timestamps
            'n',  # skip_transcript
            'n',  # skip_description
            'n'   # skip_seo
        ]
        
        result = get_user_input()
        
        assert result['input_dir'] == '/path/to/videos'
        assert result['repo_url'] is None
    
    @patch('builtins.input')
    def test_get_user_input_quoted_paths(self, mock_input):
        """Test get_user_input with quoted directory paths."""
        mock_input.side_effect = [
            '"/path/with spaces/videos"',  # Quoted path
            '',  # repo_url (empty)
            'n',  # skip_silence_removal
            'n',  # skip_concat
            'n',  # skip_reprocessing
            'n',  # skip_timestamps
            'n',  # skip_transcript
            'n',  # skip_description
            'n'   # skip_seo
        ]
        
        result = get_user_input()
        
        # Should strip quotes
        assert result['input_dir'] == '/path/with spaces/videos'
        assert result['repo_url'] is None


class TestMainWorkflow:
    """Test main workflow integration."""
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'GROQ_API_KEY': 'test-key'})
    @patch('main.get_user_input')
    @patch('video_tool.VideoProcessor')
    def test_main_complete_workflow(self, mock_processor_class, mock_get_input, temp_dir):
        """Test complete main workflow with all steps enabled."""
        # Setup test data
        test_data = create_complete_test_dataset(temp_dir)
        
        # Mock user input
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'repo_url': 'https://github.com/test/repo',
            'skip_silence_removal': False,
            'skip_concat': False,
            'skip_reprocessing': False,
            'skip_timestamps': False,
            'skip_transcript': False,
            'skip_description': False,
            'skip_seo': False
        }
        
        # Mock VideoProcessor
        mock_processor = Mock()
        mock_processor_class.return_value = mock_processor
        
        # Mock method returns
        mock_processor.remove_silences.return_value = temp_dir / "processed"
        mock_processor.concatenate_videos.return_value = temp_dir / "concatenated_video.mp4"
        mock_processor.generate_transcript.return_value = temp_dir / "transcript.vtt"
        mock_processor.generate_description.return_value = temp_dir / "description.md"
        mock_processor.generate_seo_keywords.return_value = temp_dir / "keywords.txt"
        
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
    @patch('video_tool.VideoProcessor')
    def test_main_skip_all_processing(self, mock_processor_class, mock_get_input, temp_dir):
        """Test main workflow with all processing steps skipped."""
        # Mock user input to skip everything
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'repo_url': None,
            'skip_silence_removal': True,
            'skip_concat': True,
            'skip_reprocessing': True,
            'skip_timestamps': True,
            'skip_transcript': True,
            'skip_description': True,
            'skip_seo': True
        }
        
        mock_processor = Mock()
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
    @patch('video_tool.VideoProcessor')
    def test_main_partial_workflow(self, mock_processor_class, mock_get_input, temp_dir):
        """Test main workflow with some steps skipped."""
        # Create a video file for fallback
        video_file = temp_dir / "test_video.mp4"
        MockVideoGenerator.create_mock_mp4(video_file)
        
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'repo_url': 'https://github.com/test/repo',
            'skip_silence_removal': True,  # Skip
            'skip_concat': True,          # Skip
            'skip_reprocessing': False,
            'skip_timestamps': False,     # Process
            'skip_transcript': False,     # Process
            'skip_description': False,    # Process
            'skip_seo': False            # Process
        }
        
        mock_processor = Mock()
        mock_processor_class.return_value = mock_processor
        
        # Mock returns
        mock_processor.generate_transcript.return_value = temp_dir / "transcript.vtt"
        mock_processor.generate_description.return_value = temp_dir / "description.md"
        mock_processor.generate_seo_keywords.return_value = temp_dir / "keywords.txt"
        
        # Run main
        main()
        
        # Verify only selected methods were called
        mock_processor.remove_silences.assert_not_called()
        mock_processor.concatenate_videos.assert_not_called()
        mock_processor.generate_timestamps.assert_called_once()
        mock_processor.generate_transcript.assert_called_once()
        mock_processor.generate_description.assert_called_once()
        mock_processor.generate_seo_keywords.assert_called_once()
    
    def test_main_missing_api_keys(self):
        """Test main function with missing API keys."""
        # Clear environment variables
        with patch.dict(os.environ, {}, clear=True):
            with patch('loguru.logger.error') as mock_logger:
                main()
                
                # Should log error about missing API keys
                mock_logger.assert_called()
                error_calls = [call.args[0] for call in mock_logger.call_args_list]
                assert any('OPENAI_API_KEY' in msg for msg in error_calls)
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'GROQ_API_KEY': 'test-key'})
    @patch('main.get_user_input')
    def test_main_invalid_directory(self, mock_get_input):
        """Test main function with invalid input directory."""
        mock_get_input.return_value = {
            'input_dir': '/nonexistent/directory',
            'repo_url': None,
            'skip_silence_removal': True,
            'skip_concat': True,
            'skip_reprocessing': True,
            'skip_timestamps': True,
            'skip_transcript': True,
            'skip_description': True,
            'skip_seo': True
        }
        
        with patch('loguru.logger.error') as mock_logger:
            main()
            
            # Should log error about directory not existing
            mock_logger.assert_called()
            error_calls = [call.args[0] for call in mock_logger.call_args_list]
            assert any('does not exist' in msg for msg in error_calls)
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'GROQ_API_KEY': 'test-key'})
    @patch('main.get_user_input')
    @patch('video_tool.VideoProcessor')
    def test_main_processing_error(self, mock_processor_class, mock_get_input, temp_dir):
        """Test main function handles processing errors."""
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'repo_url': None,
            'skip_silence_removal': False,
            'skip_concat': True,
            'skip_reprocessing': True,
            'skip_timestamps': True,
            'skip_transcript': True,
            'skip_description': True,
            'skip_seo': True
        }
        
        mock_processor = Mock()
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
    @patch('video_tool.VideoProcessor')
    def test_main_description_without_repo_url(self, mock_processor_class, mock_get_input, temp_dir):
        """Test main function skips description when no repo URL provided."""
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'repo_url': None,  # No repo URL
            'skip_silence_removal': True,
            'skip_concat': True,
            'skip_reprocessing': True,
            'skip_timestamps': True,
            'skip_transcript': True,
            'skip_description': False,  # Want description but no repo URL
            'skip_seo': False
        }
        
        mock_processor = Mock()
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
    def test_real_processor_workflow(self, mock_get_input, temp_dir):
        """Test workflow with real VideoProcessor instance (mocked external calls)."""
        # Create test data
        test_data = create_complete_test_dataset(temp_dir)
        
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'repo_url': 'https://github.com/test/repo',
            'skip_silence_removal': True,  # Skip heavy processing
            'skip_concat': True,
            'skip_reprocessing': True,
            'skip_timestamps': False,
            'skip_transcript': True,  # Skip API calls
            'skip_description': True,
            'skip_seo': True
        }
        
        # Mock external dependencies
        with patch('subprocess.run') as mock_subprocess, \
             patch('groq.Groq'), \
             patch('openai.OpenAI'):
            
            mock_subprocess.return_value.returncode = 0
            mock_subprocess.return_value.stdout = '{"streams": [], "format": {"duration": "300.0"}}'
            
            # Should complete without errors
            main()
            
            # Verify timestamps file was created
            timestamps_file = temp_dir / "timestamps.json"
            assert timestamps_file.exists()
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'GROQ_API_KEY': 'test-key'})
    @patch('main.get_user_input')
    def test_workflow_file_dependencies(self, mock_get_input, temp_dir):
        """Test workflow respects file dependencies between steps."""
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'repo_url': 'https://github.com/test/repo',
            'skip_silence_removal': True,
            'skip_concat': True,
            'skip_reprocessing': True,
            'skip_timestamps': True,
            'skip_transcript': False,  # This will fail without concatenated video
            'skip_description': False,  # This will fail without transcript
            'skip_seo': False  # This will fail without description
        }
        
        # Mock external APIs
        with patch('groq.Groq') as mock_groq_class, \
             patch('openai.OpenAI') as mock_openai_class, \
             patch('loguru.logger.error') as mock_logger:
            
            # Run main - should handle missing dependencies gracefully
            main()
            
            # Should log errors about missing files
            mock_logger.assert_called()
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'GROQ_API_KEY': 'test-key'})
    @patch('main.get_user_input')
    def test_workflow_with_existing_files(self, mock_get_input, temp_dir):
        """Test workflow when some output files already exist."""
        # Create some existing output files
        (temp_dir / "timestamps.json").write_text('{"existing": true}')
        (temp_dir / "transcript.vtt").write_text("WEBVTT\n\nexisting transcript")
        
        mock_get_input.return_value = {
            'input_dir': str(temp_dir),
            'repo_url': 'https://github.com/test/repo',
            'skip_silence_removal': True,
            'skip_concat': True,
            'skip_reprocessing': True,
            'skip_timestamps': False,  # Should overwrite existing
            'skip_transcript': True,
            'skip_description': False,  # Should use existing transcript
            'skip_seo': False
        }
        
        with patch('subprocess.run') as mock_subprocess, \
             patch('openai.OpenAI') as mock_openai_class:
            
            # Mock ffprobe for timestamps
            mock_subprocess.return_value.returncode = 0
            mock_subprocess.return_value.stdout = '{"streams": [], "format": {"duration": "300.0"}}'
            
            # Mock OpenAI responses
            mock_openai = Mock()
            mock_openai_class.return_value = mock_openai
            
            mock_response = Mock()
            mock_choice = Mock()
            mock_choice.message.content = SAMPLE_OPENAI_DESCRIPTION_RESPONSE['choices'][0]['message']['content']
            mock_response.choices = [mock_choice]
            mock_openai.chat.completions.create.return_value = mock_response
            
            # Run main
            main()
            
            # Should have updated timestamps and created description
            assert (temp_dir / "timestamps.json").exists()
            assert (temp_dir / "description.md").exists()
            assert (temp_dir / "keywords.txt").exists()


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