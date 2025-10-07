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
    video_title = input("Enter the video title (optional): ").strip()
    
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
    skip_context_cards = input("Skip context cards generation? ").lower().strip() == 'y'
    skip_description = input("Skip description generation? ").lower().strip() == 'y'
    skip_seo = input("Skip SEO keywords generation? ").lower().strip() == 'y'
    skip_linkedin = input("Skip LinkedIn post generation? ").lower().strip() == 'y'
    skip_twitter = input("Skip Twitter post generation? ").lower().strip() == 'y'
    
    return {
        'input_dir': input_dir,
        'repo_url': repo_url if repo_url else None,
        'video_title': video_title if video_title else None,
        'skip_silence_removal': skip_silence_removal,
        'skip_concat': skip_concat,
        'skip_reprocessing': skip_reprocessing,
        'skip_timestamps': skip_timestamps,
        'skip_transcript': skip_transcript,
        'skip_context_cards': skip_context_cards,
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

        processor = VideoProcessor(str(input_dir), video_title=params['video_title'])
        logger.info(f'Output directory path: {processor.output_dir}')

        # Remove silences
        if not params['skip_silence_removal']:
            logger.info('🔇 Removing silences from videos...')
            processed_dir = processor.remove_silences()
            logger.info(f'✅ Silences removed. Processed videos in: {processed_dir}')

        # Generate timestamps for individual videos first
        if not params['skip_timestamps']:
            logger.info('⏰ Generating timestamps for individual videos...')
            processor.generate_timestamps()
            logger.info('✅ Timestamps generated for all videos')

        # Then proceed with concatenation
        output_video = None
        if not params['skip_concat']:
            logger.info('🎬 Starting video concatenation...')
            output_video = processor.concatenate_videos(skip_reprocessing=params['skip_reprocessing'])
            if output_video:
                file_size = Path(output_video).stat().st_size / (1024*1024)
                logger.info(f'✅ Videos concatenated: {Path(output_video).name} ({file_size:.1f} MB)')
            else:
                logger.warning('⚠️ Video concatenation completed but no output file returned')

        # Find video file for transcript/description generation
        logger.info("🎥 Selecting video file for content generation...")
        video_path = output_video
        
        if not video_path:
            mp4_files = list(processor.output_dir.glob('*.mp4'))
            if not mp4_files:
                mp4_files = list(input_dir.glob('*.mp4'))
            if mp4_files:
                # Sort by size (largest first) to get the main video
                mp4_files_with_size = [(f, f.stat().st_size) for f in mp4_files]
                mp4_files_with_size.sort(key=lambda x: x[1], reverse=True)
                
                video_path = mp4_files_with_size[0][0]
                largest_size = mp4_files_with_size[0][1] / (1024*1024)
                logger.info(f"📁 Selected largest MP4: {video_path.name} ({largest_size:.1f} MB)")
            else:
                logger.warning('❌ No video files found for content generation')
                video_path = None
        else:
            logger.info(f"📁 Using concatenated video: {Path(video_path).name}")

        # Transcript generation
        transcript_path = None
        if not params['skip_transcript'] and video_path:
            logger.info('📝 Generating transcript...')
            transcript_path = processor.generate_transcript(str(video_path))
            
            if transcript_path and Path(transcript_path).exists():
                transcript_size = Path(transcript_path).stat().st_size
                logger.info(f'✅ Transcript generated ({transcript_size} bytes)')
            else:
                logger.error('❌ Transcript generation failed')
        elif not params['skip_transcript']:
            logger.warning('⚠️ Skipping transcript: no video file available')

        # Context cards and resource mentions
        if not params['skip_context_cards']:
            transcript_candidate = None
            if transcript_path and Path(transcript_path).exists():
                transcript_candidate = Path(transcript_path)
            else:
                default_transcript = processor.output_dir / "transcript.vtt"
                if default_transcript.exists():
                    transcript_candidate = default_transcript

            if transcript_candidate:
                logger.info('🗂️ Identifying YouTube card opportunities and resource mentions...')
                cards_path = processor.generate_context_cards(str(transcript_candidate))
                if cards_path:
                    logger.info(f'✅ Context cards generated: {Path(cards_path).name}')
                else:
                    logger.error('❌ Context cards generation failed')
            else:
                logger.warning('⚠️ Skipping context cards: no transcript available')

        # Description generation
        if not params['skip_description'] and params['repo_url'] and video_path:
            logger.info('📄 Generating description...')
            
            transcript_vtt_path = str(processor.output_dir / 'transcript.vtt')
            if not Path(transcript_vtt_path).exists():
                logger.warning(f'⚠️ Transcript file not found: {transcript_vtt_path}')
            
            description_path = processor.generate_description(
                str(video_path),
                params['repo_url'],
                transcript_vtt_path
            )
            
            if description_path:
                logger.info(f'✅ Description generated: {Path(description_path).name}')
                
                if not params['skip_seo']:
                    logger.info('🔍 Generating SEO keywords...')
                    keywords_path = processor.generate_seo_keywords(description_path)
                    if keywords_path:
                        logger.info(f'✅ SEO keywords generated: {Path(keywords_path).name}')
                    else:
                        logger.error('❌ SEO keywords generation failed')
            else:
                logger.error('❌ Description generation failed')
        elif not params['skip_description'] and params['repo_url']:
            logger.warning('⚠️ Skipping description: no video file available')
        elif not params['skip_description']:
            logger.info('ℹ️ Skipping description: no repository URL provided')

        # Generate social media posts
        if not params['skip_linkedin'] and video_path and transcript_path and Path(transcript_path).exists():
            logger.info('📱 Generating LinkedIn post...')
            linkedin_path = processor.generate_linkedin_post(transcript_path)
            if linkedin_path:
                logger.info(f'✅ LinkedIn post generated: {Path(linkedin_path).name}')
            else:
                logger.error('❌ LinkedIn post generation failed')
        elif not params['skip_linkedin'] and video_path:
            logger.warning('⚠️ Skipping LinkedIn post: no transcript available')
        elif not params['skip_linkedin']:
            logger.warning('⚠️ Skipping LinkedIn post: no video file available')

        if not params['skip_twitter'] and video_path and transcript_path and Path(transcript_path).exists():
            logger.info('🐦 Generating Twitter post...')
            twitter_path = processor.generate_twitter_post(transcript_path)
            if twitter_path:
                logger.info(f'✅ Twitter post generated: {Path(twitter_path).name}')
            else:
                logger.error('❌ Twitter post generation failed')
        elif not params['skip_twitter'] and video_path:
            logger.warning('⚠️ Skipping Twitter post: no transcript available')
        elif not params['skip_twitter']:
            logger.warning('⚠️ Skipping Twitter post: no video file available')

    except Exception as e:
        logger.error(f'Error during processing: {e}')
        raise

if __name__ == '__main__':
    main()
