# Common Workflows

## Download and Process YouTube Video

```bash
# Download
video-tool video download -u "https://youtube.com/watch?v=XXX" -o ./downloads -n "my-video"

# Remove silence
video-tool video silence-removal -i ./downloads/my-video.mp4 -o ./output/cleaned.mp4

# Generate transcript
video-tool generate transcript -i ./output/cleaned.mp4 -o ./output/transcript.vtt
```

## Extract and Enhance Audio

```bash
# Extract audio
video-tool video extract-audio -i video.mp4 -o audio.mp3

# Enhance (requires Replicate API token via `video-tool config keys`)
video-tool video enhance-audio -i audio.mp3 -o enhanced.mp3

# Replace in original video
video-tool video replace-audio -v video.mp4 -a enhanced.mp3 -o final.mp4
```

## Create Video with Chapters for YouTube

```bash
# Concatenate clips
video-tool video concat -i ./clips/ -o ./output/full.mp4 -f

# Generate timestamps from clips
video-tool video timestamps -m clips -i ./clips/ -o ./output/timestamps.json

# Generate transcript
video-tool generate transcript -i ./output/full.mp4 -o ./output/transcript.vtt

# Generate description with chapters
video-tool generate description -i ./output/transcript.vtt -t ./output/timestamps.json -o ./output/description.md

# Upload to YouTube
video-tool upload youtube-video -i ./output/full.mp4 -t "My Video" --description-file ./output/description.md -p private
video-tool upload youtube-transcript -v VIDEO_ID -t ./output/transcript.vtt
```

## Quick Edit: Remove a Bad Section

```bash
# Check video duration first
video-tool video info -i recording.mp4

# Cut out unwanted segment (e.g., 5:00-7:30)
video-tool video cut -i recording.mp4 -o fixed.mp4 -f 00:05:00 -t 00:07:30
```

## Speed Up a Long Video

```bash
# 1.5x speed with pitch preservation
video-tool video speed -i lecture.mp4 -o faster.mp4 -f 1.5 -p
```

## Extract a Clip

```bash
# Keep only 2:30 to 5:00
video-tool video extract-segment -i full.mp4 -o clip.mp4 -s 00:02:30 -e 00:05:00
```

## Full Pipeline (Non-Interactive)

Process everything automatically:

```bash
video-tool pipeline -i ./clips/ -o ./output/ -t "Tutorial Video" -y
```

This runs: concat → timestamps → transcript → description → context cards

## Bunny.net CDN Upload

```bash
# Upload video
video-tool upload bunny-video -v ./output/final.mp4

# Add captions (use video ID from previous command)
video-tool upload bunny-transcript -v BUNNY_VIDEO_ID -t ./output/transcript.vtt

# Add chapters
video-tool upload bunny-chapters -v BUNNY_VIDEO_ID -c ./output/timestamps.json
```
