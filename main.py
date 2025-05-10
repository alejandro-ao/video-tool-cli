import os
import argparse
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger
from video_processor import VideoProcessor

def setup_argparse():
    parser = argparse.ArgumentParser(description='Video Processing Tool')
    parser.add_argument('--input-dir', type=str, required=True,
                        help='Directory containing input MP4 files')
    parser.add_argument('--repo-url', type=str,
                        help='GitHub repository URL for video description')
    parser.add_argument('--skip-concat', action='store_true',
                        help='Skip video concatenation')
    parser.add_argument('--skip-timestamps', action='store_true',
                        help='Skip timestamp generation')
    parser.add_argument('--skip-transcript', action='store_true',
                        help='Skip transcript generation')
    parser.add_argument('--skip-description', action='store_true',
                        help='Skip description generation')
    parser.add_argument('--skip-seo', action='store_true',
                        help='Skip SEO keywords generation')
    return parser

def main():
    load_dotenv()
    if not os.getenv('OPENAI_API_KEY'):
        logger.error('OPENAI_API_KEY environment variable not set')
        return

    parser = setup_argparse()
    args = parser.parse_args()

    processor = VideoProcessor(args.input_dir)
    output_video = None

    try:
        if not args.skip_concat:
            logger.info('Starting video concatenation...')
            output_video = processor.concatenate_videos()
            logger.info(f'Videos concatenated successfully: {output_video}')

        video_path = output_video or next(Path(args.input_dir).glob('*.mp4'))

        if not args.skip_timestamps:
            logger.info('Generating timestamps...')
            processor.generate_timestamps(str(video_path))
            logger.info('Timestamps generated successfully')

        if not args.skip_transcript:
            logger.info('Generating transcript...')
            transcript_path = processor.generate_transcript(str(video_path))
            logger.info(f'Transcript generated successfully: {transcript_path}')

        if not args.skip_description and args.repo_url:
            logger.info('Generating description...')
            description_path = processor.generate_description(
                str(video_path),
                args.repo_url,
                str(Path(args.input_dir) / 'transcript.vtt')
            )
            logger.info(f'Description generated successfully: {description_path}')

            if not args.skip_seo:
                logger.info('Generating SEO keywords...')
                keywords_path = processor.generate_seo_keywords(description_path)
                logger.info(f'SEO keywords generated successfully: {keywords_path}')

    except Exception as e:
        logger.error(f'Error during processing: {e}')
        raise

if __name__ == '__main__':
    main()
