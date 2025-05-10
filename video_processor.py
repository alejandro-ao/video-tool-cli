import os
import subprocess
from pathlib import Path
from textwrap import dedent
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
from loguru import logger
from openai import OpenAI
from moviepy.video.io.VideoFileClip import VideoFileClip


class VideoProcessor:
    def __init__(self, input_dir: str):
        self.input_dir = Path(input_dir)
        self.client = OpenAI()
        self.setup_logging()

    def setup_logging(self):
        logger.add(
            "video_processor.log", rotation="1 day", retention="1 week", level="INFO"
        )

    def get_mp4_files(self) -> List[Path]:
        """Get all MP4 files in the input directory."""
        return sorted(self.input_dir.glob("*.mp4"))

    def concatenate_videos(self, output_filename: Optional[str] = None) -> str:
        """Concatenate multiple MP4 videos in alphabetical order using ffmpeg."""
        mp4_files = self.get_mp4_files()
        if not mp4_files:
            raise ValueError("No MP4 files found in the input directory")

        logger.info(f"Found {len(mp4_files)} MP4 files to concatenate")

        if not output_filename:
            output_filename = f"{datetime.now().strftime('%Y-%m-%d')}_concatenated.mp4"

        output_path = self.input_dir / output_filename
        
        # Create a temporary file listing all videos to concatenate
        concat_list = self.input_dir / "concat_list.txt"
        with open(concat_list, "w") as f:
            for mp4_file in mp4_files:
                f.write(f"file '{mp4_file.name}'\n")

        try:
            # Use ffmpeg to concatenate videos
            subprocess.run([
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_list),
                '-c', 'copy',  # Copy streams without re-encoding
                str(output_path)
            ], check=True)

            # Clean up the temporary file
            os.remove(concat_list)
            return str(output_path)

        except subprocess.CalledProcessError as e:
            logger.error(f"Error concatenating videos: {e}")
            if os.path.exists(concat_list):
                os.remove(concat_list)
            raise

    def generate_timestamps(self, video_path: str) -> Dict:
        """Generate timestamp information for the video with chapters based on input videos."""
        mp4_files = self.get_mp4_files()
        if not mp4_files:
            raise ValueError("No MP4 files found in the input directory")

        timestamps = []
        current_time = 0

        # Generate timestamps for each input video
        for mp4_file in mp4_files:
            video = VideoFileClip(str(mp4_file))
            duration = int(video.duration)
            start_time = current_time
            end_time = current_time + duration

            timestamps.append(
                {
                    "start": str(timedelta(seconds=start_time)),
                    "end": str(timedelta(seconds=end_time)),
                    "title": mp4_file.stem,
                }
            )

            current_time = end_time
            video.close()

        # Get metadata from the final concatenated video
        final_video = VideoFileClip(video_path)
        video_info = {
            "video_duration": str(int(final_video.duration)),
            "video_title": Path(video_path).name,
            "timestamps": timestamps,
            "metadata": {
                "resolution": f"{final_video.w}x{final_video.h}",
                "file_size": f"{os.path.getsize(video_path) // (1024*1024)}MB",
                "creation_date": datetime.now().isoformat(),
            },
        }
        final_video.close()

        output_path = Path(video_path).parent / "timestamps.json"
        with open(output_path, "w") as f:
            json.dump([video_info], f, indent=2)

        return video_info

    def generate_transcript(self, video_path: str) -> str:
        """Generate VTT transcript using OpenAI's Whisper API.
        For audio files larger than 25MB, splits into chunks and processes separately.
        """
        from pydub import AudioSegment
        
        audio_path = Path(video_path).with_suffix(".mp3")
        video = VideoFileClip(video_path)
        video.audio.write_audiofile(str(audio_path))
        video.close()

        try:
            # Check file size
            file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            
            if file_size_mb <= 25:
                # Process normally if file is under 25MB
                with open(audio_path, "rb") as audio_file:
                    transcript = self.client.audio.transcriptions.create(
                        model="whisper-1", file=audio_file, response_format="vtt"
                    )
            else:
                # Split and process audio in chunks
                logger.info(f"Audio file size: {file_size_mb:.2f}MB. Splitting into chunks...")
                audio = AudioSegment.from_mp3(str(audio_path))
                chunk_length = 10 * 60 * 1000  # 10 minutes in milliseconds
                chunks = []
                
                # Split audio into chunks
                for i in range(0, len(audio), chunk_length):
                    chunk = audio[i:i + chunk_length]
                    chunk_path = audio_path.parent / f"chunk_{i//chunk_length}.mp3"
                    chunk.export(str(chunk_path), format="mp3")
                    chunks.append(chunk_path)
                
                # Process each chunk
                transcripts = []
                for i, chunk_path in enumerate(chunks):
                    logger.info(f"Processing chunk {i+1}/{len(chunks)}")
                    with open(chunk_path, "rb") as chunk_file:
                        chunk_transcript = self.client.audio.transcriptions.create(
                            model="whisper-1", file=chunk_file, response_format="vtt"
                        )
                        transcripts.append(self._clean_vtt_transcript(chunk_transcript))
                    os.remove(chunk_path)
                
                # Combine transcripts
                transcript = self._merge_vtt_transcripts(transcripts)
            
            output_path = Path(video_path).parent / "transcript.vtt"
            with open(output_path, "w") as f:
                f.write(transcript)

            # os.remove(audio_path)  # Cleanup
            return str(output_path)

        except Exception as e:
            logger.error(f"Error generating transcript: {e}")
            raise

    def generate_description(
        self, video_path: str, repo_url: str, transcript_path: str
    ) -> str:
        """Generate video description using LLM."""
        with open(transcript_path) as f:
            transcript = f.read()

        prompt = f"""
        Based on this transcript, generate a comprehensive video description in markdown format. 
        Include relevant technical details and key points.
        
        The description should include only these two things:
        - A short paragraph explaining the video's purpose and content.
        - A list of topics that are covered in the video (good for SEO). For example:
            - How to create a FastAPI app
            - How to use Docker
            - Creating a Docker image
            - etc.
        
        Here is an example of what the description should look like:
        
        # Video Title
        Short paragraph explaining the video's purpose and content.
        ## Topics
        - Topic 1
        - Topic 2
        - Topic 3
        
        Transcript: {transcript}"""

        response = self.client.chat.completions.create(
            model="gpt-4.1", messages=[{"role": "user", "content": prompt}]
        )

        links = [
            {"url": repo_url, "description": "Code from the video"},
            {
                "url": "aibootcamp.dev",
                "description": "🚀 Complete AI Engineer Bootcamp",
            },
            {
                "url": "https://link.alejandro-ao.com/l83gNq",
                "description": "❤️ Buy me a coffee... or a beer (thanks)",
            },
            {
                "url": "https://link.alejandro-ao.com/HrFKZn",
                "description": "💬 Join the Discord Help Server",
            },
            {
                "url": "https://link.alejandro-ao.com/AIIguB",
                "description": "✉️ Get the news from the channel and AI Engineering",
            },
        ]

        timestamps = json.load(open(Path(video_path).parent / "timestamps.json"))[0][
            "timestamps"
        ]

        description = dedent(f"""# {Path(video_path).stem}

                      {response.choices[0].message.content}

                      ## Links
                      {''.join(f'- [{link["description"]}]({link["url"]})' for link in links)}
                      
                      ## Timestamps
                      {''.join(f'{timestamp["start"]} - {timestamp["title"]} \n' for timestamp in timestamps)}
                      
                      """)

        output_path = Path(video_path).parent / "description.md"
        with open(output_path, "w") as f:
            f.write(description)

        return str(output_path)

    def _clean_vtt_transcript(self, vtt_content: str) -> str:
        """Remove VTT headers and clean up transcript content."""
        # Skip the VTT header (first 2 lines)
        lines = vtt_content.split('\n')[2:]
        return '\n'.join(lines)

    def _merge_vtt_transcripts(self, transcripts: List[str]) -> str:
        """Merge multiple VTT transcripts into a single file with robust validation."""
        merged = "WEBVTT\n\n"  # Add VTT header
        time_offset = 0
        
        for transcript in transcripts:
            if not transcript.strip():  # Skip empty transcripts
                continue
                
            lines = transcript.split('\n')
            i = 0
            while i < len(lines):
                # Find next timestamp line
                while i < len(lines) and '-->' not in lines[i]:
                    i += 1
                
                if i >= len(lines):
                    break
                    
                # Process timestamp block
                timestamp_line = lines[i]
                try:
                    times = timestamp_line.split(' --> ')
                    if len(times) != 2:
                        i += 1
                        continue
                        
                    start = self._adjust_timestamp(times[0].strip(), time_offset)
                    end = self._adjust_timestamp(times[1].strip(), time_offset)
                    
                    # Get subtitle text if available
                    subtitle_text = lines[i + 1] if i + 1 < len(lines) else ''
                    
                    # Add to merged output
                    merged += f"{start} --> {end}\n"
                    merged += f"{subtitle_text}\n\n"
                    
                except (ValueError, IndexError):
                    logger.warning(f"Skipping malformed timestamp block at line {i}")
                    
                i += 2  # Move to next potential block
            
            # Calculate time offset using last valid timestamp
            try:
                last_timestamp = next(
                    (line.split(' --> ')[1].strip()
                     for line in reversed(lines)
                     if '-->' in line),
                    "00:00:00.000"
                )
                time_offset += self._timestamp_to_seconds(last_timestamp)
            except (ValueError, IndexError):
                logger.warning("Could not determine time offset, using default")
                time_offset += 0  # Keep existing offset
        
        return merged

    def _adjust_timestamp(self, timestamp: str, offset: float) -> str:
        """Adjust a VTT timestamp by adding an offset in seconds."""
        seconds = self._timestamp_to_seconds(timestamp) + offset
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

    def _timestamp_to_seconds(self, timestamp: str) -> float:
        """Convert a VTT timestamp to seconds."""
        h, m, s = timestamp.split(':')
        return float(h) * 3600 + float(m) * 60 + float(s)

    def generate_seo_keywords(self, description_path: str) -> str:
        """Generate SEO keywords based on video description."""
        with open(description_path) as f:
            description = f.read()

        prompt = f"""Based on this video description, generate a list of relevant SEO keywords 
        that would help with video discoverability. Focus on technical and specific terms.
        Description: {description}"""

        response = self.client.chat.completions.create(
            model="gpt-4", messages=[{"role": "user", "content": prompt}]
        )

        output_path = Path(description_path).parent / "keywords.txt"
        with open(output_path, "w") as f:
            f.write(response.choices[0].message.content)

        return str(output_path)
