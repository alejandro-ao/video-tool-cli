import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import json
from loguru import logger
from openai import OpenAI
from moviepy.editor import VideoFileClip, concatenate_videoclips


class VideoProcessor:
    def __init__(self, input_dir: str):
        self.input_dir = Path(input_dir)
        self.client = OpenAI()
        self.setup_logging()
        self.github_repo_url = input("Enter the GitHub repository URL:")

    def setup_logging(self):
        logger.add(
            "video_processor.log", rotation="1 day", retention="1 week", level="INFO"
        )

    def get_mp4_files(self) -> List[Path]:
        """Get all MP4 files in the input directory."""
        return sorted(self.input_dir.glob("*.mp4"))

    def concatenate_videos(self, output_filename: Optional[str] = None) -> str:
        """Concatenate multiple MP4 videos in alphabetical order."""
        mp4_files = self.get_mp4_files()
        if not mp4_files:
            raise ValueError("No MP4 files found in the input directory")

        logger.info(f"Found {len(mp4_files)} MP4 files to concatenate")
        clips = [VideoFileClip(str(mp4)) for mp4 in mp4_files]

        if not output_filename:
            output_filename = f"{datetime.now().strftime('%Y-%m-%d')}_concatenated.mp4"

        output_path = self.input_dir / output_filename
        final_clip = concatenate_videoclips(clips)
        final_clip.write_videofile(str(output_path))

        for clip in clips:
            clip.close()

        return str(output_path)

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
                    "start": str(datetime.timedelta(seconds=start_time)),
                    "end": str(datetime.timedelta(seconds=end_time)),
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
                "resolution": f"{final_video.size[0]}x{final_video.size[1]}",
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
        """Generate VTT transcript using OpenAI's Whisper API."""
        audio_path = Path(video_path).with_suffix(".mp3")
        video = VideoFileClip(video_path)
        video.audio.write_audiofile(str(audio_path))
        video.close()

        try:
            with open(audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1", file=audio_file, response_format="vtt"
                )

            output_path = Path(video_path).parent / "transcript.vtt"
            with open(output_path, "w") as f:
                f.write(transcript)

            os.remove(audio_path)  # Cleanup
            return str(output_path)

        except Exception as e:
            logger.error(f"Error generating transcript: {e}")
            if os.path.exists(audio_path):
                os.remove(audio_path)
            raise

    def generate_description(
        self, video_path: str, repo_url: str, transcript_path: str
    ) -> str:
        """Generate video description using LLM."""
        with open(transcript_path) as f:
            transcript = f.read()

        prompt = f"""Based on this transcript, generate a comprehensive video description 
        and timestamps in markdown format. Include relevant technical details and key points.
        
        The description should include:
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
            {"url": self.github_repo_url, "description": "Code from the video"},
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

        description = f"""# {Path(video_path).stem}

                      {response.choices[0].message.content}

                      ## Links
                      {''.join(f'- [{link["description"]}]({link["url"]})' for link in links)}
                      
                      ## Timestamps
                      {''.join(f'{timestamp["start"]} - {timestamp["title"]}' for timestamp in timestamps)}
                      """

        output_path = Path(video_path).parent / "description.md"
        with open(output_path, "w") as f:
            f.write(description)

        return str(output_path)

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
