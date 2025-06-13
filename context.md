📽️ YouTube Video Generator from Clip Directory

This project is a Python script designed to automate the creation of a YouTube video from a folder containing multiple video clips. It processes the clips through a pipeline of operations to produce a ready-to-publish video along with optimized metadata. 

The pipeline includes:
- Timestamp Generation: Assigns a timestamp to each clip, forming a structured video outline.
- Clip Concatenation: Merges all clips into a single continuous video.
- Transcription: Transcribes the final video using a speech-to-text model.
- Video Description Generation: Uses a large language model (LLM) to write a YouTube-friendly video description based on the transcript.
- SEO Keyword Generation: Automatically creates relevant keywords to improve the video’s discoverability.

This tool streamlines the video publishing workflow, especially for content creators working with segmented footage.