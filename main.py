import os
import argparse
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger
from video_processor import VideoProcessor

def get_user_input():
    """Get parameters from user input."""
    print("\nVideo Processing Tool\n")
    
    # Get input directory
    while True:
        input_dir = input("Enter the input directory path: ").strip().strip("'\"")
        if input_dir:
            break
        print("Input directory is required!")
    
    # Get optional parameters
    repo_url = input("Enter GitHub repository URL (optional): ").strip()
    
    # Get processing options
    print("\nProcessing options (Enter 'y' to skip, any other key to process):")
    skip_concat = input("Skip video concatenation? ").lower().strip() == 'y'
    skip_timestamps = input("Skip timestamp generation? ").lower().strip() == 'y'
    skip_transcript = input("Skip transcript generation? ").lower().strip() == 'y'
    skip_description = input("Skip description generation? ").lower().strip() == 'y'
    skip_seo = input("Skip SEO keywords generation? ").lower().strip() == 'y'
    
    return {
        'input_dir': input_dir,
        'repo_url': repo_url if repo_url else None,
        'skip_concat': skip_concat,
        'skip_timestamps': skip_timestamps,
        'skip_transcript': skip_transcript,
        'skip_description': skip_description,
        'skip_seo': skip_seo
    }

def main():
    load_dotenv()
    if not os.getenv('OPENAI_API_KEY'):
        logger.error('OPENAI_API_KEY environment variable not set')
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

        # Generate timestamps for individual videos first
        if not params['skip_timestamps']:
            logger.info('Generating timestamps for individual videos...')
            processor.generate_timestamps()
            logger.info('Timestamps generated successfully for all videos')

        # Then proceed with concatenation
        output_video = None
        if not params['skip_concat']:
            logger.info('Starting video concatenation...')
            output_video = processor.concatenate_videos()
            logger.info(f'Videos concatenated successfully: {output_video}')

        video_path = output_video or next(input_dir.glob('*.mp4'))

        if not params['skip_transcript']:
            logger.info('Generating transcript...')
            transcript_path = processor.generate_transcript(str(video_path))
            logger.info(f'Transcript generated successfully: {transcript_path}')

        if not params['skip_description'] and params['repo_url']:
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

    except Exception as e:
        logger.error(f'Error during processing: {e}')
        raise

if __name__ == '__main__':
    main()
