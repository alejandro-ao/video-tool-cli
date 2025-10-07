"""Unit tests for VideoProcessor content generation methods."""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
from openai import OpenAI
from groq import Groq

from video_tool.video_processor import VideoProcessor
from tests.test_data.mock_generators import (
    MockVideoGenerator,
    MockTranscriptGenerator,
    MockDescriptionGenerator,
    MockTimestampGenerator,
    MockKeywordsGenerator
)
from tests.test_data.sample_data import (
    SAMPLE_GROQ_RESPONSE,
    SAMPLE_OPENAI_DESCRIPTION_RESPONSE,
    SAMPLE_OPENAI_KEYWORDS_RESPONSE,
    SAMPLE_VTT_CONTENT,
    SAMPLE_DESCRIPTION_MD,
    SAMPLE_KEYWORDS,
    SAMPLE_ERROR_RESPONSES,
    SAMPLE_LINKEDIN_POST,
    SAMPLE_TWITTER_POST
)


class TestGenerateTimestamps:
    """Test generate_timestamps method."""
    
    def test_generate_timestamps_with_processed_videos(self, temp_dir, mock_video_processor):
        """Test timestamp generation with processed videos."""
        # Create processed video files
        processed_dir = temp_dir / "processed"
        processed_files = MockVideoGenerator.create_test_video_set(processed_dir, count=3)
        output_dir = temp_dir / "output"
        
        mock_video_processor.video_dir = temp_dir
        
        # Mock video metadata
        with patch.object(mock_video_processor, '_get_video_metadata') as mock_metadata:
            mock_metadata.side_effect = [
                {'duration': 300.0},  # 5 minutes
                {'duration': 450.0},  # 7.5 minutes
                {'duration': 600.0}   # 10 minutes
            ]
            
            result = mock_video_processor.generate_timestamps()
            
            # Verify timestamps file was created
            timestamps_file = output_dir / "timestamps.json"
            assert timestamps_file.exists()
            
            # Verify content
            with open(timestamps_file, 'r') as f:
                timestamps_data = json.load(f)
            
            assert len(timestamps_data) == 1
            assert 'timestamps' in timestamps_data[0]
            assert len(timestamps_data[0]['timestamps']) == 3
            
            # Verify cumulative timing
            timestamps = timestamps_data[0]['timestamps']
            assert timestamps[0]['start'] == "00:00:00"
            assert timestamps[0]['end'] == "00:05:00"
            assert timestamps[1]['start'] == "00:05:00"
            assert timestamps[1]['end'] == "00:12:30"
            assert timestamps[2]['start'] == "00:12:30"
            assert timestamps[2]['end'] == "00:22:30"
    
    def test_generate_timestamps_fallback_to_original(self, temp_dir, mock_video_processor):
        """Test timestamp generation falls back to original videos when no processed videos."""
        # Create only original video files (no processed directory)
        video_files = MockVideoGenerator.create_test_video_set(temp_dir, count=2)
        output_dir = temp_dir / "output"
        
        mock_video_processor.video_dir = temp_dir
        
        with patch.object(mock_video_processor, '_get_video_metadata') as mock_metadata:
            mock_metadata.side_effect = [
                {'duration': 240.0},  # 4 minutes
                {'duration': 360.0}   # 6 minutes
            ]
            
            result = mock_video_processor.generate_timestamps()
            
            timestamps_file = output_dir / "timestamps.json"
            assert timestamps_file.exists()
            
            with open(timestamps_file, 'r') as f:
                timestamps_data = json.load(f)
            
            timestamps = timestamps_data[0]['timestamps']
            assert len(timestamps) == 2
            assert timestamps[0]['end'] == "00:04:00"
            assert timestamps[1]['end'] == "00:10:00"
    
    def test_generate_timestamps_no_videos(self, temp_dir, mock_video_processor):
        """Test timestamp generation with no video files."""
        mock_video_processor.video_dir = temp_dir
        
        with patch('video_tool.video_processor.logger') as mock_logger:
            result = mock_video_processor.generate_timestamps()
            
            # Should warn about no videos found
            mock_logger.warning.assert_called()
    
    def test_generate_timestamps_metadata_error(self, temp_dir, mock_video_processor):
        """Test timestamp generation when metadata extraction fails."""
        video_files = MockVideoGenerator.create_test_video_set(temp_dir, count=1)
        
        mock_video_processor.video_dir = temp_dir
        
        with patch.object(mock_video_processor, '_get_video_metadata') as mock_metadata:
            mock_metadata.return_value = None  # Simulate metadata failure
            
            with patch('video_tool.video_processor.logger') as mock_logger:
                result = mock_video_processor.generate_timestamps()
                
                # Should handle error gracefully
                mock_logger.assert_called()


class TestGenerateTranscript:
    """Test generate_transcript method."""
    
    @patch('groq.Groq')
    def test_generate_transcript_success(self, mock_groq_class, temp_dir, mock_video_processor):
        """Test successful transcript generation."""
        # Create concatenated video
        video_file = temp_dir / "output" / "concatenated_video.mp4"
        MockVideoGenerator.create_mock_mp4(video_file)
        output_dir = temp_dir / "output"
        
        # Mock Groq client
        mock_groq_instance = Mock()
        mock_groq_class.return_value = mock_groq_instance
        
        # Mock transcription response
        mock_response = Mock()
        mock_response.text = SAMPLE_GROQ_RESPONSE['text']
        mock_response.segments = SAMPLE_GROQ_RESPONSE['segments']
        
        mock_groq_instance.audio.transcriptions.create.return_value = mock_response
        
        mock_video_processor.video_dir = temp_dir
        mock_video_processor.groq = mock_groq_instance
        
        with patch('video_tool.video_processor.VideoFileClip') as mock_video_clip:
            # Mock audio extraction
            mock_clip = Mock()
            mock_audio = Mock()
            mock_clip.audio = mock_audio
            mock_video_clip.return_value = mock_clip
            
            result = mock_video_processor.generate_transcript(str(video_file))
            
            # Verify transcript file was created
            transcript_file = output_dir / "transcript.vtt"
            assert transcript_file.exists()
            
            # Verify Groq API was called
            mock_groq_instance.audio.transcriptions.create.assert_called_once()
    
    @patch('groq.Groq')
    def test_generate_transcript_large_file_chunking(self, mock_groq_class, temp_dir, mock_video_processor):
        """Test transcript generation with large file chunking."""
        video_file = temp_dir / "output" / "concatenated_video.mp4"
        MockVideoGenerator.create_mock_mp4(video_file)
        output_dir = temp_dir / "output"
        
        mock_groq_instance = Mock()
        mock_groq_class.return_value = mock_groq_instance
        
        # Mock multiple chunk responses
        chunk_responses = [
            Mock(text="First chunk text", segments=SAMPLE_GROQ_RESPONSE['segments'][:1]),
            Mock(text="Second chunk text", segments=SAMPLE_GROQ_RESPONSE['segments'][1:2])
        ]
        
        mock_groq_instance.audio.transcriptions.create.side_effect = chunk_responses
        
        mock_video_processor.video_dir = temp_dir
        mock_video_processor.groq = mock_groq_instance
        
        with patch('video_tool.video_processor.VideoFileClip') as mock_video_clip:
            # Mock large audio file that needs chunking
            mock_clip = Mock()
            mock_audio = Mock()
            mock_audio.duration = 3600  # 1 hour - should trigger chunking
            mock_clip.audio = mock_audio
            mock_video_clip.return_value = mock_clip
            
            with patch.object(mock_video_processor, '_merge_vtt_transcripts') as mock_merge:
                mock_merge.return_value = SAMPLE_VTT_CONTENT
                
                result = mock_video_processor.generate_transcript(str(video_file))
                
                # Should call transcription multiple times for chunks
                assert mock_groq_instance.audio.transcriptions.create.call_count >= 1
    
    @patch('groq.Groq')
    def test_generate_transcript_groq_error(self, mock_groq_class, temp_dir, mock_video_processor):
        """Test transcript generation when Groq API fails."""
        video_file = temp_dir / "output" / "concatenated_video.mp4"
        MockVideoGenerator.create_mock_mp4(video_file)
        
        mock_groq_instance = Mock()
        mock_groq_class.return_value = mock_groq_instance
        
        # Mock API error
        mock_groq_instance.audio.transcriptions.create.side_effect = Exception("API Error")
        
        mock_video_processor.video_dir = temp_dir
        mock_video_processor.groq = mock_groq_instance
        
        with patch('video_tool.video_processor.VideoFileClip'):
            with patch('video_tool.video_processor.logger') as mock_logger:
                video_file = temp_dir / "test_video.mp4"
                MockVideoGenerator.create_mock_mp4(video_file)  # Create the video file
                result = mock_video_processor.generate_transcript(str(video_file))
                
                # Should log the error
                mock_logger.assert_called()
    
    def test_generate_transcript_no_video_file(self, temp_dir, mock_video_processor):
        """Test transcript generation when concatenated video doesn't exist."""
        mock_video_processor.video_dir = temp_dir
        
        with patch('video_tool.video_processor.logger') as mock_logger:
            video_file = temp_dir / "nonexistent_video.mp4"
            result = mock_video_processor.generate_transcript(str(video_file))
            
            # Should log error about missing video file
            mock_logger.error.assert_called()
    
    def test_vtt_helper_methods(self, mock_video_processor):
        """Test VTT processing helper methods."""
        # Test VTT cleaning
        if hasattr(mock_video_processor, '_clean_vtt_transcript'):
            dirty_vtt = "WEBVTT\n\n00:00:00.000 --> 00:00:05.000\n[MUSIC] Hello world [APPLAUSE]\n\n"
            clean_vtt = mock_video_processor._clean_vtt_transcript(dirty_vtt)
            assert "[MUSIC]" not in clean_vtt
            assert "[APPLAUSE]" not in clean_vtt
        
        # Test Groq JSON to VTT conversion
        if hasattr(mock_video_processor, '_groq_verbose_json_to_vtt'):
            vtt_result = mock_video_processor._groq_verbose_json_to_vtt(SAMPLE_GROQ_RESPONSE)
            assert "WEBVTT" in vtt_result
            assert "00:00:00.000 --> 00:00:05.000" in vtt_result


class TestGenerateDescription:
    """Test generate_description method."""
    
    def test_generate_description_success(self, temp_dir, mock_video_processor):
        """Test successful description generation."""
        # Create transcript file
        transcript_file = temp_dir / "output" / "transcript.vtt"
        MockTranscriptGenerator.create_vtt_transcript(transcript_file)
        
        # Create timestamps file
        timestamps_file = temp_dir / "output" / "timestamps.json"
        MockTimestampGenerator.create_timestamps_json(timestamps_file, ["test_video.mp4"])
        
        mock_video_processor.video_dir = temp_dir
        
        # Mock OpenAI response
        with patch.object(mock_video_processor.client.chat.completions, 'create') as mock_create:
            # Mock both generation and polishing responses
            responses = [
                Mock(choices=[Mock(message=Mock(content='Initial description'))]),
                Mock(choices=[Mock(message=Mock(content=SAMPLE_OPENAI_DESCRIPTION_RESPONSE['choices'][0]['message']['content']))])
            ]
            mock_create.side_effect = responses
            
            # Create dummy paths for the test
            video_path = str(temp_dir / "test_video.mp4")
            repo_url = "https://github.com/test/repo"
            transcript_path = str(temp_dir / "output" / "transcript.vtt")
            
            # Create a dummy transcript file
            with open(transcript_path, 'w') as f:
                f.write("Test transcript content")
            
            result = mock_video_processor.generate_description(video_path, repo_url, transcript_path)
            
            # Verify description file was created
            description_file = temp_dir / "output" / "description.md"
            assert description_file.exists()
            
            # Verify OpenAI API was called twice (generation + polishing)
            assert mock_create.call_count == 2
            
            # Check that transcript was used in the first prompt (generation call)
            first_call_args = mock_create.call_args_list[0]
            messages = first_call_args[1]['messages']
            assert any('transcript' in str(msg).lower() for msg in messages)
    
    def test_generate_description_with_polishing(self, temp_dir, mock_video_processor):
        """Test description generation with polishing step."""
        transcript_file = temp_dir / "output" / "transcript.vtt"
        MockTranscriptGenerator.create_vtt_transcript(transcript_file)
        
        # Create timestamps file
        timestamps_file = temp_dir / "output" / "timestamps.json"
        MockTimestampGenerator.create_timestamps_json(timestamps_file, ["test_video.mp4"])
        
        mock_video_processor.video_dir = temp_dir
        
        with patch.object(mock_video_processor.client.chat.completions, 'create') as mock_create:
            # Mock both generation and polishing responses
            responses = [
                Mock(choices=[Mock(message=Mock(content='Initial description'))]),
                Mock(choices=[Mock(message=Mock(content=SAMPLE_OPENAI_DESCRIPTION_RESPONSE['choices'][0]['message']['content']))])
            ]
            mock_create.side_effect = responses
            
            # Create dummy paths for the test
            video_path = str(temp_dir / "test_video.mp4")
            repo_url = "https://github.com/test/repo"
            transcript_path = str(temp_dir / "output" / "transcript.vtt")
            
            # Create a dummy transcript file
            with open(transcript_path, 'w') as f:
                f.write("Test transcript content")
            
            result = mock_video_processor.generate_description(video_path, repo_url, transcript_path)
            
            # Should call OpenAI twice (generation + polishing)
            assert mock_create.call_count == 2
            
            description_file = temp_dir / "output" / "description.md"
            assert description_file.exists()
    
    def test_generate_description_no_transcript(self, temp_dir, mock_video_processor):
        """Test description generation when transcript doesn't exist."""
        # Create timestamps file
        timestamps_file = temp_dir / "output" / "timestamps.json"
        MockTimestampGenerator.create_timestamps_json(timestamps_file, ["test_video.mp4"])
        
        mock_video_processor.video_dir = temp_dir
        
        with patch('video_tool.video_processor.logger') as mock_logger:
            # Create dummy paths for the test
            video_path = str(temp_dir / "test_video.mp4")
            repo_url = "https://github.com/test/repo"
            transcript_path = str(temp_dir / "output" / "transcript.vtt")
            
            # DO NOT create the transcript file - this is what we're testing
            
            result = mock_video_processor.generate_description(video_path, repo_url, transcript_path)
            
            # Should log error about missing transcript
            mock_logger.error.assert_called()
            # Should return empty string when transcript is missing
            assert result == ""
    
    def test_generate_description_openai_error(self, temp_dir, mock_video_processor):
        """Test description generation when OpenAI API fails."""
        transcript_file = temp_dir / "output" / "transcript.vtt"
        MockTranscriptGenerator.create_vtt_transcript(transcript_file)
        
        # Create timestamps file
        timestamps_file = temp_dir / "output" / "timestamps.json"
        MockTimestampGenerator.create_timestamps_json(timestamps_file, ["test_video.mp4"])
        
        mock_video_processor.video_dir = temp_dir
        
        with patch.object(mock_video_processor.client.chat.completions, 'create') as mock_create:
            mock_create.side_effect = Exception("OpenAI API Error")
            
            with patch('video_tool.video_processor.logger') as mock_logger:
                # Create dummy paths for the test
                video_path = str(temp_dir / "test_video.mp4")
                repo_url = "https://github.com/test/repo"
                transcript_path = str(temp_dir / "output" / "transcript.vtt")
                
                # Create a dummy transcript file
                with open(transcript_path, 'w') as f:
                    f.write("Test transcript content")
                
                # Expect the exception to be raised since there's no error handling
                with pytest.raises(Exception, match="OpenAI API Error"):
                    result = mock_video_processor.generate_description(video_path, repo_url, transcript_path)
    
    def test_generate_description_with_timestamps(self, temp_dir, mock_video_processor):
        """Test description generation includes timestamps."""
        # Create transcript and timestamps
        transcript_file = temp_dir / "output" / "transcript.vtt"
        timestamps_file = temp_dir / "output" / "timestamps.json"
        
        MockTranscriptGenerator.create_vtt_transcript(transcript_file)
        MockTimestampGenerator.create_timestamps_json(timestamps_file, ["video1.mp4", "video2.mp4"])
        
        mock_video_processor.video_dir = temp_dir
        
        with patch.object(mock_video_processor.client.chat.completions, 'create') as mock_create:
            mock_choice = Mock()
            mock_choice.message.content = SAMPLE_OPENAI_DESCRIPTION_RESPONSE['choices'][0]['message']['content']
            mock_response = Mock()
            mock_response.choices = [mock_choice]
            mock_create.return_value = mock_response
            
            # Create dummy paths for the test
            video_path = str(temp_dir / "test_video.mp4")
            repo_url = "https://github.com/test/repo"
            transcript_path = str(temp_dir / "output" / "transcript.vtt")
            
            # Create a dummy transcript file
            with open(transcript_path, 'w') as f:
                f.write("Test transcript content")
            
            result = mock_video_processor.generate_description(video_path, repo_url, transcript_path)
            
            description_file = temp_dir / "output" / "description.md"
            assert description_file.exists()
            
            # Verify timestamps were included in the description
            with open(description_file, 'r') as f:
                content = f.read()
                assert "00:00:00" in content or "Timestamps" in content


class TestGenerateSEOKeywords:
    """Test generate_seo_keywords method."""
    
    def test_generate_seo_keywords_success(self, temp_dir, mock_video_processor):
        """Test successful SEO keywords generation."""
        # Create description file
        description_file = temp_dir / "output" / "description.md"
        MockDescriptionGenerator.create_description_md(description_file)
        
        mock_video_processor.video_dir = temp_dir
        
        with patch.object(mock_video_processor.client.chat.completions, 'create') as mock_create:
            mock_response = Mock()
            mock_choice = Mock()
            mock_choice.message.content = SAMPLE_OPENAI_KEYWORDS_RESPONSE['choices'][0]['message']['content']
            mock_response.choices = [mock_choice]
            mock_create.return_value = mock_response
            
            result = mock_video_processor.generate_seo_keywords(str(description_file))
            
            # Verify keywords file was created
            keywords_file = temp_dir / "output" / "keywords.txt"
            assert keywords_file.exists()
            
            # Verify content
            with open(keywords_file, 'r') as f:
                content = f.read()
                assert len(content.strip()) > 0
                assert ',' in content  # Should be comma-separated
            
            # Verify OpenAI API was called
            mock_create.assert_called_once()
    
    def test_generate_seo_keywords_no_description(self, temp_dir, mock_video_processor):
        """Test SEO keywords generation when description doesn't exist."""
        # Create timestamps file
        timestamps_file = temp_dir / "output" / "timestamps.json"
        MockTimestampGenerator.create_timestamps_json(timestamps_file, ["test_video.mp4"])
        
        mock_video_processor.video_dir = temp_dir
        
        # Create a non-existent description path to test error handling
        description_path = str(temp_dir / "output" / "nonexistent_description.md")
        
        with patch('video_tool.video_processor.logger') as mock_logger:
            result = mock_video_processor.generate_seo_keywords(description_path)
            
            # Should log error about missing description
            mock_logger.error.assert_called()
    
    def test_generate_seo_keywords_openai_error(self, temp_dir, mock_video_processor, mock_logger):
        """Test SEO keywords generation when OpenAI API fails."""
        description_file = temp_dir / "output" / "description.md"
        MockDescriptionGenerator.create_description_md(description_file)
        
        mock_video_processor.video_dir = temp_dir
        
        with patch.object(mock_video_processor.client.chat.completions, 'create') as mock_create:
            mock_create.side_effect = Exception("OpenAI API Error")
            
            # Should return empty string and log error instead of raising exception
            result = mock_video_processor.generate_seo_keywords(str(description_file))
            assert result == ""
            mock_logger.error.assert_called()
    
    def test_generate_seo_keywords_rate_limit_handling(self, temp_dir, mock_video_processor, mock_logger):
        """Test SEO keywords generation with rate limit handling."""
        description_file = temp_dir / "output" / "description.md"
        MockDescriptionGenerator.create_description_md(description_file)
        
        mock_video_processor.video_dir = temp_dir
        
        with patch.object(mock_video_processor.client.chat.completions, 'create') as mock_create:
            mock_create.side_effect = Exception("Rate limit exceeded")
            
            # Should return empty string and log error instead of raising exception
            result = mock_video_processor.generate_seo_keywords(str(description_file))
            assert result == ""
            mock_logger.error.assert_called()


class TestContentGenerationIntegration:
    """Integration tests for content generation workflow."""
    
    def test_complete_content_generation_workflow(self, temp_dir, mock_video_processor):
        """Test complete content generation from timestamps to keywords."""
        # Create initial video files
        video_files = MockVideoGenerator.create_test_video_set(temp_dir, count=2)
        processed_dir = temp_dir / "processed"
        processed_files = MockVideoGenerator.create_test_video_set(processed_dir, count=2)
        
        # Create concatenated video
        concat_video = temp_dir / "output" / "concatenated_video.mp4"
        MockVideoGenerator.create_mock_mp4(concat_video)
        
        # Create timestamps file
        timestamps_file = temp_dir / "output" / "timestamps.json"
        MockTimestampGenerator.create_timestamps_json(timestamps_file, ["test_video.mp4"])
        
        mock_video_processor.video_dir = temp_dir
        
        # Mock all external dependencies
        with patch.object(mock_video_processor, '_get_video_metadata') as mock_metadata, \
             patch.object(mock_video_processor.groq.audio.transcriptions, 'create') as mock_groq, \
             patch.object(mock_video_processor.client.chat.completions, 'create') as mock_openai, \
             patch('video_tool.video_processor.VideoFileClip'):
            
            # Setup mocks
            mock_metadata.return_value = {'duration': 300.0}
            
            mock_groq_response = Mock()
            mock_groq_response.text = SAMPLE_GROQ_RESPONSE['text']
            mock_groq_response.segments = SAMPLE_GROQ_RESPONSE['segments']
            mock_groq.return_value = mock_groq_response
            
            # Set up mock responses for multiple OpenAI calls (2 for description, 1 for keywords)
            description_response = Mock(choices=[Mock(message=Mock(content=SAMPLE_OPENAI_DESCRIPTION_RESPONSE['choices'][0]['message']['content']))])
            polished_description_response = Mock(choices=[Mock(message=Mock(content="Polished: " + SAMPLE_OPENAI_DESCRIPTION_RESPONSE['choices'][0]['message']['content']))])
            keywords_response = Mock(choices=[Mock(message=Mock(content=SAMPLE_OPENAI_KEYWORDS_RESPONSE['choices'][0]['message']['content']))])
            mock_openai.side_effect = [description_response, polished_description_response, keywords_response]
            
            # Run complete workflow
            timestamps_result = mock_video_processor.generate_timestamps()
            transcript_result = mock_video_processor.generate_transcript()
            
            # Ensure transcript file exists for description generation
            transcript_file = temp_dir / "output" / "transcript.vtt"
            if not transcript_file.exists():
                MockTranscriptGenerator.create_vtt_file(transcript_file)
            
            description_result = mock_video_processor.generate_description()
            
            # Create a dummy description file for the test
            description_file = temp_dir / "output" / "description.md"
            MockDescriptionGenerator.create_description_md(description_file)
            keywords_result = mock_video_processor.generate_seo_keywords(str(description_file))
            
            # Verify all files were created
            assert (temp_dir / "output" / "timestamps.json").exists()
            assert (temp_dir / "output" / "transcript.vtt").exists()
            assert (temp_dir / "output" / "description.md").exists()
            assert (temp_dir / "output" / "keywords.txt").exists()
    
    def test_content_generation_error_recovery(self, temp_dir, mock_video_processor):
        """Test error recovery in content generation workflow."""
        # Create minimal setup
        video_files = MockVideoGenerator.create_test_video_set(temp_dir, count=1)
        concat_video = temp_dir / "output" / "concatenated_video.mp4"
        MockVideoGenerator.create_mock_mp4(concat_video)
        
        mock_video_processor.video_dir = temp_dir
        
        # Test partial failure scenario
        with patch.object(mock_video_processor, '_get_video_metadata') as mock_metadata, \
             patch.object(mock_video_processor.groq.audio.transcriptions, 'create') as mock_groq, \
             patch.object(mock_video_processor.client.chat.completions, 'create') as mock_openai, \
             patch('video_tool.video_processor.VideoFileClip'), \
             patch('video_tool.video_processor.logger') as mock_logger:
            
            # Setup mocks - some succeed, some fail
            mock_metadata.return_value = {'duration': 300.0}
            mock_groq.side_effect = Exception("Groq API Error")
            mock_openai.return_value = Mock(choices=[Mock(message=Mock(content=SAMPLE_OPENAI_DESCRIPTION_RESPONSE['choices'][0]['message']['content']))])
            
            # Run workflow - should handle errors gracefully
            timestamps_result = mock_video_processor.generate_timestamps()
            transcript_result = mock_video_processor.generate_transcript()
            
            # Timestamps should succeed, transcript should fail
            assert (temp_dir / "output" / "timestamps.json").exists()
            assert not (temp_dir / "output" / "transcript.vtt").exists()
            
            # Should log errors
            mock_logger.error.assert_called()
    
    def test_file_dependencies_in_workflow(self, temp_dir, mock_video_processor):
        """Test that methods properly handle file dependencies."""
        # Create timestamps file
        timestamps_file = temp_dir / "output" / "timestamps.json"
        MockTimestampGenerator.create_timestamps_json(timestamps_file, ["test_video.mp4"])
        
        mock_video_processor.video_dir = temp_dir
        
        # Test description generation without transcript
        with patch('video_tool.video_processor.logger') as mock_logger:
            video_path = str(temp_dir / "test_video.mp4")
            repo_url = "https://github.com/test/repo"
            transcript_path = str(temp_dir / "output" / "nonexistent_transcript.vtt")
            description_result = mock_video_processor.generate_description(video_path, repo_url, transcript_path)
            mock_logger.error.assert_called()  # Should error about missing transcript
        
        # Test keywords generation without description
        with patch('video_tool.video_processor.logger') as mock_logger:
            description_path = str(temp_dir / "output" / "nonexistent_description.md")
            keywords_result = mock_video_processor.generate_seo_keywords(description_path)
            mock_logger.error.assert_called()  # Should error about missing description
        
        # Test transcript generation without concatenated video
        with patch('video_tool.video_processor.logger') as mock_logger:
            video_path = str(temp_dir / "nonexistent_video.mp4")
            transcript_result = mock_video_processor.generate_transcript(video_path)
            mock_logger.error.assert_called()  # Should error about missing video


class TestGenerateLinkedInPost:
    """Test generate_linkedin_post method."""
    
    def test_generate_linkedin_post_success(self, temp_dir, mock_video_processor):
        """Test successful LinkedIn post generation."""
        # Create transcript file
        transcript_file = temp_dir / "output" / "transcript.vtt"
        transcript_file.write_text(SAMPLE_VTT_CONTENT)
        
        mock_video_processor.input_dir = temp_dir
        
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = SAMPLE_LINKEDIN_POST
        
        with patch.object(mock_video_processor.client.chat.completions, 'create', return_value=mock_response):
            result = mock_video_processor.generate_linkedin_post(str(transcript_file))
            
            # Verify file was created
            linkedin_file = temp_dir / "output" / "linkedin_post.md"
            assert linkedin_file.exists()
            assert result == str(linkedin_file)
            
            # Verify content
            content = linkedin_file.read_text()
            assert "🚀" in content  # Should contain emojis
            assert "#" in content   # Should contain hashtags
    
    def test_generate_linkedin_post_no_transcript(self, temp_dir, mock_video_processor):
        """Test LinkedIn post generation with missing transcript file."""
        mock_video_processor.input_dir = temp_dir
        
        with pytest.raises(FileNotFoundError):
            mock_video_processor.generate_linkedin_post(str(temp_dir / "nonexistent.vtt"))
    
    def test_generate_linkedin_post_openai_error(self, temp_dir, mock_video_processor, mock_logger):
        """Test LinkedIn post generation with OpenAI API error."""
        transcript_file = temp_dir / "output" / "transcript.vtt"
        transcript_file.write_text(SAMPLE_VTT_CONTENT)
        
        mock_video_processor.input_dir = temp_dir
        
        # Mock OpenAI error
        with patch.object(mock_video_processor.client.chat.completions, 'create', side_effect=Exception("API Error")):
            with pytest.raises(Exception, match="API Error"):
                mock_video_processor.generate_linkedin_post(str(transcript_file))


class TestGenerateTwitterPost:
    """Test generate_twitter_post method."""
    
    def test_generate_twitter_post_success(self, temp_dir, mock_video_processor):
        """Test successful Twitter post generation."""
        # Create transcript file
        transcript_file = temp_dir / "output" / "transcript.vtt"
        transcript_file.write_text(SAMPLE_VTT_CONTENT)
        
        mock_video_processor.input_dir = temp_dir
        
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = SAMPLE_TWITTER_POST
        
        with patch.object(mock_video_processor.client.chat.completions, 'create', return_value=mock_response):
            result = mock_video_processor.generate_twitter_post(str(transcript_file))
            
            # Verify file was created
            twitter_file = temp_dir / "output" / "twitter_post.md"
            assert twitter_file.exists()
            assert result == str(twitter_file)
            
            # Verify content
            content = twitter_file.read_text()
            assert len(content) <= 280  # Twitter character limit
            assert "#" in content       # Should contain hashtags
    
    def test_generate_twitter_post_no_transcript(self, temp_dir, mock_video_processor):
        """Test Twitter post generation with missing transcript file."""
        mock_video_processor.input_dir = temp_dir
        
        with pytest.raises(FileNotFoundError):
            mock_video_processor.generate_twitter_post(str(temp_dir / "nonexistent.vtt"))
    
    def test_generate_twitter_post_openai_error(self, temp_dir, mock_video_processor, mock_logger):
        """Test Twitter post generation with OpenAI API error."""
        transcript_file = temp_dir / "output" / "transcript.vtt"
        transcript_file.write_text(SAMPLE_VTT_CONTENT)
        
        mock_video_processor.input_dir = temp_dir
        
        # Mock OpenAI error
        with patch.object(mock_video_processor.client.chat.completions, 'create', side_effect=Exception("API Error")):
            with pytest.raises(Exception, match="API Error"):
                mock_video_processor.generate_twitter_post(str(transcript_file))
