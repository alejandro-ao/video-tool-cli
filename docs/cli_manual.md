# Video Tool CLI Manual

This guide explains every option exposed by the video processing CLI. It covers command invocation, interactive and automated modes, profile management, and where configuration data is stored.

## Command Overview

```
video-tool [run] [options]
```

- `video-tool` is the recommended executable (an alias to `python main.py`).
- The optional `run` subcommand is accepted for readability. `video-tool --profile default` and `video-tool run --profile default` behave the same.

Environment requirements (API keys, ffmpeg availability, etc.) are unchanged from `README.md`.

## Processing Modes

### Automatic Mode (default)

- Runs every supported step unless skipped by profile settings or CLI flags.
- Prompts for the input directory if it is not provided via profile or CLI flag (TTY only).
- Prints a summary of the configuration before starting.
- Use `--input-dir` to override the input directory without editing profiles.

### Manual Mode (`--manual`)

- Replays the existing interactive questionnaire.
- At completion, you can save the answers to a named profile for future runs.
- Non-interactive flags (such as `--skip-all` or `--timestamps`) are ignored in this mode and a warning is shown.

## Profiles

Profiles capture a complete set of answers from manual mode.

- Save: run `video-tool --manual`, finish the prompts, then accept the save prompt and provide a profile name.
- Load: `video-tool --profile <name>`.
- Default fallback: if no `--profile` flag is supplied, the CLI checks for a profile named `default` and uses it automatically.
- Profiles include skip toggles and supporting metadata except the input directory, repository URL, and video title. Provide those per run via prompts or flags.

### Profile Storage

Profiles live in `profiles.json` inside the platform-specific config directory:

- macOS: `~/Library/Application Support/video-tool/profiles.json`
- Linux: `${XDG_CONFIG_HOME:-~/.config}/video-tool/profiles.json`
- Windows: `%APPDATA%\video-tool\profiles.json`

Delete or edit this JSON file to manage saved profiles manually.

## Skip Strategy Flags

### Global Skip

- `--skip-all`: mark every optional step as skipped.
- Combine with step flags below to opt back into specific stages. Example:

  ```
  video-tool run --skip-all --timestamps --transcript
  ```

  This command only generates timestamps and a transcript.

### Step Toggles

All step flags override `--skip-all` and force the associated stage to run. They have no effect if the stage is already enabled through defaults or a profile.

| Flag | Effect |
| ---- | ------ |
| `--silence-removal` | Remove silence from clips. |
| `--concat` | Concatenate clips into a final MP4. |
| `--timestamps` | Produce timestamp metadata. |
| `--transcript` | Generate a transcript for the selected video. |
| `--context-cards` | Identify context cards and resource mentions. |
| `--description` | Draft the video description (requires repository URL). |
| `--seo` | Generate SEO keywords. |
| `--linkedin` | Create LinkedIn copy. |
| `--twitter` | Create Twitter/X copy. |
| `--bunny-video` | Upload or re-upload the video to Bunny.net. |
| `--bunny-chapters` | Push chapter markers to Bunny.net. |
| `--bunny-transcript` | Upload transcript captions to Bunny.net. |

> Note: Social copy and Bunny uploads rely on previously generated assets (video file, transcript, timestamps). If those are skipped, associated stages will emit warnings and exit gracefully.

## Additional Options

- `--input-dir <path>`: provide the source directory. Required for non-interactive runs unless the active profile defines it. If omitted on a TTY, the CLI will prompt for the path.
- `--profile <name>`: load a saved profile. Profiles are case insensitive. An error lists available profiles if the requested one is missing.
- `--manual`: enter interactive mode (see above).
- `--bunny-video-path <path>`: optionally supply an existing MP4 to upload to Bunny.net. Overrides the automatically selected final video. Ignored in manual mode.
- `--bunny-transcript-path <path>`: optionally supply a VTT/SRT file to upload as Bunny captions. Overrides the default `output/transcript.vtt`. Ignored in manual mode.
- `--bunny-chapters-path <path>`: optionally supply a JSON file containing chapter markers (title, start, end) for Bunny. Overrides the normalised chapters from `timestamps.json`. Ignored in manual mode.
- When description generation is enabled without a stored URL, the CLI prompts for the repository (TTY) or exits with instructions.
- Every run asks for a video title; provide it when prompted or via `--manual` responses.

## Configuration Summary

Before execution, automatic mode prints a table showing:

- Resolved input path and optional metadata (repository URL, video title).
- Which processing stages will run or skip.
- Bunny.net library/video identifiers if applicable.
- Bunny override paths if provided (video, transcript, chapters).
- Log verbosity.

Use this summary to confirm that applied profiles and CLI flags match expectations before any processing begins.

## Logging and Output

- Logs stream to the console and `video_processor.log`.
- All generated artifacts land inside the `output/` folder within the chosen input directory.
- Bunny uploads rely on environment variables (`BUNNY_LIBRARY_ID`, `BUNNY_ACCESS_KEY`, etc.) when optional IDs are not provided through prompts, profiles, or CLI overrides.
