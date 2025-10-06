import os
import argparse
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger
from video_tool import VideoProcessor

def get_user_input():
    """Get parameters from user input."""
    print("\nVideo Processing Tool\n")
    
    # Get input directory
    while True:
        input_dir = input("Enter the input directory path: ").strip()
        # Remove surrounding quotes if present
        if input_dir.startswith('"') and input_dir.endswith('"'):
            input_dir = input_dir[1:-1]
        elif input_dir.startswith("'") and input_dir.endswith("'"):
            input_dir = input_dir[1:-1]
        else:
            # Handle escaped spaces by replacing \  with just space
            input_dir = input_dir.replace('\\ ', ' ')
        
        if input_dir:
            break
        print("Input directory is required!")
    
    # Get optional parameters
    repo_url = input("Enter GitHub repository URL (optional): ").strip()
    
    # Get processing options
    print("\nProcessing options (Enter 'y' to skip, any other key to process):")
    skip_silence_removal = input("Skip silence removal? ").lower().strip() == 'y'
    skip_concat = input("Skip video concatenation? ").lower().strip() == 'y'
    
    # Only ask about reprocessing if concatenation is not being skipped
    skip_reprocessing = False
    if not skip_concat:
        print("\nConcatenation options:")
        skip_reprocessing = input("Skip video reprocessing for faster concatenation (assumes same format)? ").lower().strip() == 'y'
    
    skip_timestamps = input("Skip timestamp generation? ").lower().strip() == 'y'
    skip_transcript = input("Skip transcript generation? ").lower().strip() == 'y'
    skip_description = input("Skip description generation? ").lower().strip() == 'y'
    skip_seo = input("Skip SEO keywords generation? ").lower().strip() == 'y'
    skip_linkedin = input("Skip LinkedIn post generation? ").lower().strip() == 'y'
    skip_twitter = input("Skip Twitter post generation? ").lower().strip() == 'y'
    
    return {
        'input_dir': input_dir,
        'repo_url': repo_url if repo_url else None,
        'skip_silence_removal': skip_silence_removal,
        'skip_concat': skip_concat,
        'skip_reprocessing': skip_reprocessing,
        'skip_timestamps': skip_timestamps,
        'skip_transcript': skip_transcript,
        'skip_description': skip_description,
        'skip_seo': skip_seo,
        'skip_linkedin': skip_linkedin,
        'skip_twitter': skip_twitter
    }

def main():
    load_dotenv()
    if not os.getenv('OPENAI_API_KEY'):
        logger.error('OPENAI_API_KEY environment variable not set')
        return
    if not os.getenv('GROQ_API_KEY'):
        logger.error('GROQ_API_KEY environment variable not set')
        return

    try:
        # Get parameters from user input
        params = get_user_input()
        
        # Convert to absolute path and handle spaces correctly
        input_dir = Path(params['input_dir']).expanduser().resolve()
        logger.info(f'Input directory path: {input_dir}')
        
        if not input_dir.exists():
            logger.error(f'Input directory does not exist: {input_dir}')
            return
        if not input_dir.is_dir():
            logger.error(f'Path is not a directory: {input_dir}')
            return

        processor = VideoProcessor(str(input_dir))

        # Remove silences
        if not params['skip_silence_removal']:
            logger.info('Removing silences from videos...')
            processed_dir = processor.remove_silences()
            logger.info(f'Silences removed successfully. Processed videos are in: {processed_dir}')

        # Generate timestamps for individual videos first
        if not params['skip_timestamps']:
            logger.info('Generating timestamps for individual videos...')
            processor.generate_timestamps()
            logger.info('Timestamps generated successfully for all videos')

        # Then proceed with concatenation
        output_video = None
        if not params['skip_concat']:
            logger.info('Starting video concatenation...')
            output_video = processor.concatenate_videos(skip_reprocessing=params['skip_reprocessing'])
            logger.info(f'Videos concatenated successfully: {output_video}')

        # Find a video file for transcript/description generation
        video_path = output_video
        if not video_path:
            mp4_files = list(input_dir.glob('*.mp4'))
            if mp4_files:
                video_path = mp4_files[0]
            else:
                logger.warning('No video files found for transcript/description generation')
                video_path = None

        if not params['skip_transcript'] and video_path:
            logger.info('Generating transcript...')
            transcript_path = processor.generate_transcript(str(video_path))
            logger.info(f'Transcript generated successfully: {transcript_path}')
        elif not params['skip_transcript']:
            logger.warning('Skipping transcript generation: no video file available')

        if not params['skip_description'] and params['repo_url'] and video_path:
            logger.info('Generating description...')
            description_path = processor.generate_description(
                str(video_path),
                params['repo_url'],
                str(input_dir / 'transcript.vtt')
            )
            logger.info(f'Description generated successfully: {description_path}')

            if not params['skip_seo']:
                logger.info('Generating SEO keywords...')
                keywords_path = processor.generate_seo_keywords(description_path)
                logger.info(f'SEO keywords generated successfully: {keywords_path}')
        elif not params['skip_description'] and params['repo_url']:
            logger.warning('Skipping description generation: no video file available')
        elif not params['skip_description']:
            logger.info('Skipping description generation: no repository URL provided')

        # Generate social media posts
        if not params['skip_linkedin'] and video_path and transcript_path and Path(transcript_path).exists():
            logger.info('Generating LinkedIn post...')
            linkedin_path = processor.generate_linkedin_post(transcript_path)
            logger.info(f'LinkedIn post generated successfully: {linkedin_path}')
        elif not params['skip_linkedin'] and video_path:
            logger.warning('Skipping LinkedIn post generation: no transcript file available')
        elif not params['skip_linkedin']:
            logger.warning('Skipping LinkedIn post generation: no video file available')

        if not params['skip_twitter'] and video_path and transcript_path and Path(transcript_path).exists():
            logger.info('Generating Twitter post...')
            twitter_path = processor.generate_twitter_post(transcript_path)
            logger.info(f'Twitter post generated successfully: {twitter_path}')
        elif not params['skip_twitter'] and video_path:
            logger.warning('Skipping Twitter post generation: no transcript file available')
        elif not params['skip_twitter']:
            logger.warning('Skipping Twitter post generation: no video file available')

    except Exception as e:
        logger.error(f'Error during processing: {e}')
        raise

if __name__ == '__main__':
    main()
