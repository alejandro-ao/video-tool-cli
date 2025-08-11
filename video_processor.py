import os
import subprocess
from pathlib import Path
from textwrap import dedent
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
from loguru import logger
from openai import OpenAI
from moviepy import VideoFileClip
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import csv


class VideoProcessor:
    def __init__(self, input_dir: str):
        self.input_dir = Path(input_dir)
        self.client = OpenAI()
        self.setup_logging()

    def setup_logging(self):
        logger.add(
            "video_processor.log", rotation="1 day", retention="1 week", level="INFO"
        )

    def extract_duration_csv(self) -> str:
        """Processes all mp4 files in a directory and its subdirectories, and writes metadata to a CSV."""
        output_csv = self.input_dir / "video_metadata.csv"
        with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            # Write header
            csv_writer.writerow(['creation_date', 'video_title', 'duration_minutes'])

            for root, dirs, files in os.walk(self.input_dir):
                # Exclude directories ending with .screenstudio
                dirs[:] = [d for d in dirs if not d.endswith('.screenstudio')]
                for filename in files:
                    if filename.lower().endswith('.mp4'):
                        file_path = os.path.join(root, filename)
                        creation_date, video_title, duration_minutes = self._get_video_metadata(file_path)
                        if creation_date:
                            csv_writer.writerow([creation_date, video_title, duration_minutes])
                            logger.info(f"Processed: {video_title}")

        logger.info(f"Metadata exported to {output_csv}")
        return str(output_csv)

    def _get_video_metadata(self, file_path):
        """Extracts metadata from a video file."""
        try:
            # Get creation time
            creation_timestamp = os.path.getctime(file_path)
            creation_date = datetime.fromtimestamp(creation_timestamp).strftime('%Y-%m-%d %H:%M:%S')

            # Get video title from filename (without extension)
            video_title = os.path.splitext(os.path.basename(file_path))[0]

            # Get video duration
            with VideoFileClip(file_path) as clip:
                duration_seconds = clip.duration
                duration_minutes = round(duration_seconds / 60, 2)

            return creation_date, video_title, duration_minutes
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return None, None, None

    def get_mp4_files(self, directory: Optional[str] = None) -> List[Path]:
        """Get all MP4 files in the specified directory."""
        try:
            search_dir = Path(directory) if directory else self.input_dir
            input_path = search_dir.expanduser().resolve()
            logger.debug(f"Searching for MP4 files in: {input_path}")

            if not input_path.exists() or not input_path.is_dir():
                raise ValueError(f"Directory does not exist or is not a directory: {input_path}")

            mp4_files = sorted([f for f in input_path.iterdir() if f.is_file() and f.suffix.lower() == '.mp4'])
            logger.debug(f"Found {len(mp4_files)} MP4 files: {[f.name for f in mp4_files]}")

            if not mp4_files:
                logger.warning(f"No MP4 files found in directory: {input_path}")
            return mp4_files
        except Exception as e:
            logger.error(f"Error accessing directory {search_dir}: {e}")
            raise

    def remove_silences(self) -> str:
        """
        Detects and removes silences from all videos in the input directory,
        saving the processed videos to a 'processed' subdirectory.
        """
        processed_dir = self.input_dir / "processed"
        processed_dir.mkdir(exist_ok=True)

        for mp4_file in self.get_mp4_files():
            logger.info(f"Processing video: {mp4_file.name}")
            audio = AudioSegment.from_file(str(mp4_file), format="mp4")

            # Detect non-silent chunks with more conservative parameters
            nonsilent_chunks = detect_nonsilent(
                audio,
                min_silence_len=1000,  # Keep 1 second minimum silence length
                silence_thresh=-45,    # More permissive threshold (-45dB instead of -40dB)
                seek_step=1           # Fine-grained analysis
            )

            # Convert tuples to list for modification
            nonsilent_chunks = [(start, end) for start, end in nonsilent_chunks]
            
            # Add buffer around speech segments to preserve transitions
            buffer_ms = 250  # 0.25 seconds buffer
            for i in range(len(nonsilent_chunks)):
                # Extend start time (but not before 0)
                nonsilent_chunks[i] = (
                    max(0, nonsilent_chunks[i][0] - buffer_ms),
                    min(len(audio), nonsilent_chunks[i][1] + buffer_ms)
                )

            # If no nonsilent chunks are found, skip this video
            if not nonsilent_chunks:
                logger.warning(f"No non-silent chunks found in {mp4_file.name}, skipping.")
                continue
            # Extend the last chunk to the end of the video to avoid cutting it off
            if nonsilent_chunks:
                last_chunk = list(nonsilent_chunks[-1])
                last_chunk_end = last_chunk[1]
                audio_duration_ms = len(audio)
                # If the last chunk ends before the video truly ends, extend it
                if last_chunk_end < audio_duration_ms:
                    logger.info(f"Extending last chunk to the end of the video by {((audio_duration_ms - last_chunk_end) / 1000):.2f}s.")
                    last_chunk[1] = audio_duration_ms
                    nonsilent_chunks[-1] = tuple(last_chunk)

            # Calculate number of silences (gaps between non-silent chunks)
            num_silences = len(nonsilent_chunks) - 1
            total_duration = audio.duration_seconds
            total_nonsilent_duration = sum((end - start) / 1000 for start, end in nonsilent_chunks)
            silence_duration = total_duration - total_nonsilent_duration
            
            logger.info(f"Found {num_silences} silences in {mp4_file.name}. "
                       f"Total silence duration: {silence_duration:.2f} seconds "
                       f"({(silence_duration/total_duration)*100:.1f}% of video)")

            # Log each silence period
            if len(nonsilent_chunks) > 1:
                for i in range(len(nonsilent_chunks) - 1):
                    silence_start = nonsilent_chunks[i][1] / 1000  # Convert to seconds
                    silence_end = nonsilent_chunks[i + 1][0] / 1000  # Convert to seconds
                    silence_length = silence_end - silence_start
                    logger.info(f"Silence {i + 1}/{num_silences} in {mp4_file.name}: "
                               f"from {timedelta(seconds=int(silence_start))} "
                               f"to {timedelta(seconds=int(silence_end))} "
                               f"(duration: {silence_length:.2f}s)")

            self._process_video_with_concat_filter(mp4_file, nonsilent_chunks, processed_dir)

        return str(processed_dir)

    def concatenate_videos(self, output_filename: Optional[str] = None, skip_reprocessing: bool = False) -> str:
        """Concatenate multiple MP4 videos in alphabetical order using ffmpeg.
        
        Args:
            output_filename: Optional custom filename for the output video
            skip_reprocessing: If True, skips video standardization and assumes all videos have the same format.
                             This provides much faster concatenation when videos are already compatible.
        
        First standardizes all videos to match the encoding parameters of the first video (unless skip_reprocessing=True).
        Utilizes hardware acceleration when available.
        """
        # Try to get files from processed directory first, fall back to input directory
        processed_dir = self.input_dir / "processed"
        mp4_files = []
        
        if processed_dir.exists():
            try:
                mp4_files = self.get_mp4_files(str(processed_dir))
                logger.info(f"Using videos from processed directory: {processed_dir}")
            except ValueError:
                pass  # Fall through to use input directory
        
        if not mp4_files:
            # No processed directory or no files in it, use original input directory
            mp4_files = self.get_mp4_files()
            logger.info(f"Using videos from input directory: {self.input_dir}")
            
        if not mp4_files:
            raise ValueError(f"No MP4 files found in either the processed directory ({processed_dir}) or input directory ({self.input_dir})")

        logger.info(f"Found {len(mp4_files)} MP4 files to concatenate")

        if not output_filename:
            output_filename = f"{datetime.now().strftime('%Y-%m-%d')}_concatenated.mp4"

        output_path = self.input_dir / output_filename
        temp_dir = self.input_dir / "temp_processed"
        temp_dir.mkdir(exist_ok=True)
        
        try:
            if skip_reprocessing:
                # Fast concatenation without reprocessing - assume all videos have the same format
                logger.info("Fast concatenation mode: skipping video reprocessing")
                
                # Create a temporary file listing all videos to concatenate directly
                concat_list = temp_dir / "concat_list.txt"
                with open(concat_list, "w") as f:
                    for mp4_file in mp4_files:
                        f.write(f"file '{mp4_file.resolve()}'\n")

                # Concatenate the videos directly without reprocessing
                logger.info("Concatenating videos without reprocessing")
                subprocess.run([
                    'ffmpeg',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', str(concat_list),
                    '-c', 'copy',
                    str(output_path)
                ], check=True)
            else:
                # Original behavior: standardize all videos first
                logger.info("Standard concatenation mode: reprocessing videos for compatibility")
                
                # Get encoding parameters from the first video
                probe_cmd = [
                    'ffprobe',
                    '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=width,height,r_frame_rate,codec_name',
                    '-of', 'json',
                    str(mp4_files[0])
                ]
                probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
                video_info = json.loads(probe_result.stdout)
                stream_info = video_info['streams'][0]
                
                # Get audio parameters
                audio_probe_cmd = [
                    'ffprobe',
                    '-v', 'error',
                    '-select_streams', 'a:0',
                    '-show_entries', 'stream=codec_name,sample_rate,channels',
                    '-of', 'json',
                    str(mp4_files[0])
                ]
                audio_result = subprocess.run(audio_probe_cmd, capture_output=True, text=True, check=True)
                audio_info = json.loads(audio_result.stdout)
                audio_stream = audio_info['streams'][0] if audio_info['streams'] else None

                # Process each video to match parameters
                processed_files = []
                for mp4_file in mp4_files:
                    output_file = temp_dir / f"processed_{mp4_file.name}"
                    fps = stream_info['r_frame_rate'].split('/')
                    fps = float(int(fps[0]) / int(fps[1]))
                    
                    # Build ffmpeg command for standardization with hardware acceleration
                    cmd = [
                        'ffmpeg',
                        '-hwaccel', 'auto',  # Automatically select best hardware acceleration
                        '-i', str(mp4_file)
                    ]
                    
                    # Video encoding parameters
                    cmd.extend([
                        '-c:v', 'h264_videotoolbox' if stream_info['codec_name'] == 'h264' else stream_info['codec_name'],
                        '-s', f"{stream_info['width']}x{stream_info['height']}",
                        '-r', str(fps),
                        '-preset', 'fast',  # Use fast encoding preset
                        '-profile:v', 'high',  # High quality profile
                    ])
                    
                    # Add audio parameters if present
                    if audio_stream:
                        cmd.extend([
                            '-c:a', audio_stream['codec_name'],
                            '-ar', audio_stream['sample_rate'],
                            '-ac', str(audio_stream['channels'])
                        ])
                    
                    cmd.extend(['-y', str(output_file)])
                    
                    logger.info(f"Standardizing video with hardware acceleration: {mp4_file.name}")
                    subprocess.run(cmd, check=True)
                    processed_files.append(output_file)

                # Create a temporary file listing all processed videos to concatenate
                concat_list = temp_dir / "concat_list.txt"
                with open(concat_list, "w") as f:
                    for proc_file in processed_files:
                        f.write(f"file '{proc_file.name}'\n")

                # Concatenate the processed videos
                logger.info("Concatenating standardized videos")
                subprocess.run([
                    'ffmpeg',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', str(concat_list),
                    '-c', 'copy',
                    str(output_path)
                ], check=True)

            return str(output_path)

        except subprocess.CalledProcessError as e:
            logger.error(f"Error during video processing: {e}")
            raise
        finally:
            # Clean up temporary files
            if temp_dir.exists():
                for temp_file in temp_dir.glob("*"):
                    temp_file.unlink()
                temp_dir.rmdir()

    def generate_timestamps(self) -> Dict:
        """Generate timestamp information for the video with chapters based on input videos."""
        # Try to get files from processed directory first, fall back to input directory
        processed_dir = self.input_dir / "processed"
        mp4_files = []
        
        if processed_dir.exists():
            try:
                mp4_files = self.get_mp4_files(str(processed_dir))
                logger.info(f"Generating timestamps from processed directory: {processed_dir}")
            except ValueError:
                pass  # Fall through to use input directory
        
        if not mp4_files:
            # No processed directory or no files in it, use original input directory
            mp4_files = self.get_mp4_files()
            logger.info(f"Generating timestamps from input directory: {self.input_dir}")
            
        if not mp4_files:
            raise ValueError(f"No MP4 files found in either the processed directory ({processed_dir}) or input directory ({self.input_dir})")

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
        video_info = {
            "timestamps": timestamps,
            "metadata": {
                "creation_date": datetime.now().isoformat(),
            },
        }

        output_path = Path(self.input_dir) / "timestamps.json"
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

        from string import Template

        # Create link list
        link_list = '\n'.join(f'- {link["description"]}: {link["url"]}' for link in links)
        
        # Create timestamp list
        timestamp_list = '\n'.join(f'{timestamp["start"]} - {timestamp["title"]}' for timestamp in timestamps)
        
        # Define template
        template = Template(dedent("""
            # $title

            $content

            ## Links
            $links
            
            ## Timestamps
            $timestamps
            """))
        
        # Substitute values
        description = template.substitute(
            title=Path(video_path).stem,
            content=response.choices[0].message.content,
            links=link_list,
            timestamps=timestamp_list
        )

        output_path = Path(video_path).parent / "description.md"
        with open(output_path, "w") as f:
            f.write(description)

        return str(output_path)

    def match_video_encoding(self, source_video_path: str, reference_video_path: str, output_filename: Optional[str] = None) -> str:
        """
        Re-encode source video to match the encoding parameters of the reference video.
        
        Args:
            source_video_path: Path to the video that needs to be re-encoded (video A)
            reference_video_path: Path to the reference video whose encoding to match (video B)
            output_filename: Optional custom filename for the output video
            
        Returns:
            Path to the re-encoded video file
        """
        source_path = Path(source_video_path)
        reference_path = Path(reference_video_path)
        
        # Validate input files
        if not source_path.exists():
            raise ValueError(f"Source video does not exist: {source_path}")
        if not reference_path.exists():
            raise ValueError(f"Reference video does not exist: {reference_path}")
            
        logger.info(f"Re-encoding {source_path.name} to match encoding of {reference_path.name}")
        
        # Get video encoding parameters from reference video
        video_probe_cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,r_frame_rate,codec_name,bit_rate,pix_fmt,profile,level',
            '-of', 'json',
            str(reference_path)
        ]
        video_result = subprocess.run(video_probe_cmd, capture_output=True, text=True, check=True)
        video_info = json.loads(video_result.stdout)
        video_stream = video_info['streams'][0]
        
        # Get audio encoding parameters from reference video
        audio_probe_cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=codec_name,sample_rate,channels,bit_rate',
            '-of', 'json',
            str(reference_path)
        ]
        audio_result = subprocess.run(audio_probe_cmd, capture_output=True, text=True, check=True)
        audio_info = json.loads(audio_result.stdout)
        audio_stream = audio_info['streams'][0] if audio_info['streams'] else None
        
        # Calculate frame rate
        fps_fraction = video_stream['r_frame_rate'].split('/')
        fps = float(int(fps_fraction[0]) / int(fps_fraction[1]))
        
        # Prepare output filename
        if not output_filename:
            source_stem = source_path.stem
            reference_stem = reference_path.stem
            output_filename = f"{source_stem}_reencoded_to_match_{reference_stem}.mp4"
            
        output_path = source_path.parent / output_filename
        
        # Build ffmpeg command for re-encoding with hardware acceleration
        cmd = [
            'ffmpeg',
            '-hwaccel', 'auto',  # Automatically select best hardware acceleration
            '-i', str(source_path),
            '-y'  # Overwrite output file if it exists
        ]
        
        # Video encoding parameters to match reference
        video_codec = video_stream['codec_name']
        
        # Use hardware accelerated encoder when possible
        if video_codec == 'h264':
            cmd.extend(['-c:v', 'h264_videotoolbox'])
        elif video_codec == 'hevc':
            cmd.extend(['-c:v', 'hevc_videotoolbox'])
        else:
            cmd.extend(['-c:v', video_codec])
            
        # Set video parameters
        cmd.extend([
            '-s', f"{video_stream['width']}x{video_stream['height']}",
            '-r', str(fps)
        ])
        
        # Add pixel format if available
        # if 'pix_fmt' in video_stream:
        #     cmd.extend(['-pix_fmt', video_stream['pix_fmt']])
            
        # Add video bitrate if available (but use a more conservative approach)
        if 'bit_rate' in video_stream and video_stream['bit_rate'] != 'N/A':
            bitrate_kbps = int(int(video_stream['bit_rate']) / 1000)
            # Use target bitrate instead of strict bitrate for more flexibility
            cmd.extend(['-b:v', f'{bitrate_kbps}k', '-maxrate', f'{int(bitrate_kbps * 1.5)}k', '-bufsize', f'{int(bitrate_kbps * 2)}k'])
            
        # For h264_videotoolbox, let it choose profile and level automatically
        # The encoder will pick appropriate settings based on resolution and framerate
        
        # Audio encoding parameters to match reference
        if audio_stream:
            cmd.extend([
                '-c:a', audio_stream['codec_name'],
                '-ar', audio_stream['sample_rate'],
                '-ac', str(audio_stream['channels'])
            ])
            
            # Add audio bitrate if available
            if 'bit_rate' in audio_stream and audio_stream['bit_rate'] != 'N/A':
                audio_bitrate_kbps = int(int(audio_stream['bit_rate']) / 1000)
                cmd.extend(['-b:a', f'{audio_bitrate_kbps}k'])
        else:
            # If reference has no audio, remove audio from source
            cmd.extend(['-an'])
            
        cmd.append(str(output_path))
        
        logger.info(f"Re-encoding {source_path.name} with parameters from {reference_path.name}")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"Successfully re-encoded video to {output_path}")
            return str(output_path)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to re-encode {source_path.name}")
            logger.error(f"FFmpeg command: {' '.join(cmd)}")
            logger.error(f"FFmpeg stderr: {e.stderr}")
            raise

    def _process_video_with_concat_filter(self, mp4_file: Path, nonsilent_chunks: list, processed_dir: Path):
        """
        Processes a video file by concatenating non-silent chunks using ffmpeg's concat filter.
        """
        output_path = processed_dir / mp4_file.name
        
        # If there are no non-silent chunks, we can't process the video.
        if not nonsilent_chunks:
            logger.warning(f"No content to process for {mp4_file.name}.")
            return

        # Prepare the filter complex string for ffmpeg
        filter_complex = []
        for i, (start, end) in enumerate(nonsilent_chunks):
            # Trim each non-silent segment
            filter_complex.append(f"[0:v]trim=start={start/1000}:end={end/1000},setpts=PTS-STARTPTS[v{i}];"
                                  f"[0:a]atrim=start={start/1000}:end={end/1000},asetpts=PTS-STARTPTS[a{i}]")

        # Prepare the concatenation part of the filter
        concat_video_streams = "".join([f"[v{i}]" for i in range(len(nonsilent_chunks))])
        concat_audio_streams = "".join([f"[a{i}]" for i in range(len(nonsilent_chunks))])
        filter_complex.append(f"{concat_video_streams}concat=n={len(nonsilent_chunks)}:v=1:a=0[outv]")
        filter_complex.append(f"{concat_audio_streams}concat=n={len(nonsilent_chunks)}:v=0:a=1[outa]")

        # Construct the full ffmpeg command
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(mp4_file),
            "-filter_complex", ";".join(filter_complex),
            "-map", "[outv]",
            "-map", "[outa]",
            str(output_path)
        ]

        logger.info(f"Running ffmpeg with concat filter for {mp4_file.name}")
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"Successfully processed {mp4_file.name} to {output_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to process {mp4_file.name} with ffmpeg.")
            logger.error(f"FFmpeg command: {' '.join(cmd)}")
            logger.error(f"FFmpeg stderr: {e.stderr}")
            raise

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

        prompt = f"""Based on this video description, generate a comma-separated list of relevant SEO keywords 
        that would help with video discoverability. Focus on technical and specific terms.
        Description: {description}"""

        response = self.client.chat.completions.create(
            model="gpt-4.1", messages=[{"role": "user", "content": prompt}]
        )

        output_path = Path(description_path).parent / "keywords.txt"
        with open(output_path, "w") as f:
            f.write(response.choices[0].message.content)

        return str(output_path)
