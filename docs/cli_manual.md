# Video Tool CLI Manual

This guide explains every option exposed by the video processing CLI. It covers command invocation, targeted and interactive modes, profile management, and where configuration data is stored.

## Command Overview

```
video-tool [run] [options]
```

- `video-tool` is the recommended executable (an alias to `python main.py`).
- The optional `run` subcommand is accepted for readability. `video-tool --transcript` and `video-tool run --transcript` behave the same.
- Every invocation must opt into at least one processing step (via CLI flag or loaded profile); otherwise the CLI exits without work.

Environment requirements (API keys, ffmpeg availability, etc.) are unchanged from `README.md`.

## Processing Modes

### Targeted Mode (default)

- Runs only the steps that are explicitly enabled through CLI flags or profile configuration.
- Prompts for any missing inputs that the selected steps require (TTY only). For example, `--transcript` will request an input directory if one is not provided via `--input-dir` or the active profile.
- When concatenation runs without an explicit mode flag, the CLI asks whether to use fast (skip reprocessing) or standard concatenation.
- Prints a configuration summary—showing enabled stages, resolved paths, and metadata—before execution.
- Use `--all` to opt into the full pipeline when you want every stage to run.

### Manual Mode (`--manual`)

- Replays the interactive questionnaire that existed in previous versions.
- At completion, you can save the answers to a named profile for future runs.
- Non-interactive flags (such as `--all` or `--transcript`) are ignored in this mode and a warning is shown.

## Profiles

Profiles capture a complete set of answers from manual mode.

- Save: run `video-tool --manual`, finish the prompts, then accept the save prompt and provide a profile name.
- Load: `video-tool --profile <name>`.
- Default fallback: if no `--profile` flag is supplied, the CLI checks for a profile named `default` and uses it automatically.
- Profiles remember which stages should execute along with supporting metadata, except for the input directory, repository URL, and video title. Provide those per run via prompts or flags.
- CLI step flags override the stage selection stored in a profile; when you pass flags, only the flagged stages execute (unless `--all` is also set).

### Profile Storage

Profiles live in `profiles.json` inside the platform-specific config directory:

- macOS: `~/Library/Application Support/video-tool/profiles.json`
- Linux: `${XDG_CONFIG_HOME:-~/.config}/video-tool/profiles.json`
- Windows: `%APPDATA%\video-tool\profiles.json`

Delete or edit this JSON file to manage saved profiles manually.

## Selecting Steps

### All Steps

- `--all`: enable every available processing step in one flag.
- Combine with manual mode if you want to opt out of specific stages during the questionnaire.

### Individual Steps

- Step flags explicitly select the stages to run. When any flags are provided, the CLI limits execution to those stages (unless `--all` is also set).
- Example:

  ```
  video-tool --transcript --input-dir ./clips
  ```

  This command only generates the transcript for the provided input directory.

| Flag | Effect |
| ---- | ------ |
| `--silence-removal` | Remove silence from clips. *(requires input directory)* |
| `--concat` | Concatenate clips into a final MP4. *(requires input directory)* |
| `--timestamps` | Produce timestamp metadata. *(requires input directory)* |
| `--transcript` | Generate a transcript for the selected video. *(requires input directory)* |
| `--context-cards` | Identify context cards and resource mentions. *(requires input directory)* |
| `--description` | Draft the video description. *(requires input directory & repository URL)* |
| `--seo` | Generate SEO keywords. *(requires input directory & repository URL)* |
| `--linkedin` | Create LinkedIn copy. *(requires input directory)* |
| `--twitter` | Create Twitter/X copy. *(requires input directory)* |
| `--bunny-video` | Upload or re-upload the video to Bunny.net. |
| `--bunny-chapters` | Push chapter markers to Bunny.net. |
| `--bunny-transcript` | Upload transcript captions to Bunny.net. |

> Note: Social copy and Bunny uploads rely on previously generated assets (video file, transcript, timestamps). Enable the prerequisite steps or supply the required override paths before running these stages.

## Additional Options

- `--input-dir <path>`: provide the source directory. Required for non-interactive runs when any selected step touches the filesystem. If omitted on a TTY, the CLI will prompt for the path.
- `--profile <name>`: load a saved profile. Profiles are case insensitive. An error lists available profiles if the requested one is missing.
- `--manual`: enter interactive mode (see above).
- `--all`: shorthand to activate every processing step without naming them individually.
- `--fast-concat`: skip the reprocessing step during concatenation (fast mode). When omitted in an interactive shell, the CLI will prompt for the preferred mode.
- `--standard-concat`: force reprocessing during concatenation regardless of saved defaults.
- `--bunny-video-path <path>`: optionally supply an existing MP4 to upload to Bunny.net. Overrides the automatically selected final video. Ignored in manual mode.
- `--bunny-transcript-path <path>`: optionally supply a VTT/SRT file to upload as Bunny captions. Overrides the default `output/transcript.vtt`. Ignored in manual mode.
- `--bunny-chapters-path <path>`: optionally supply a JSON file containing chapter markers (title, start, end) for Bunny. Overrides the normalised chapters from `timestamps.json`. Ignored in manual mode.
- The CLI prompts for any metadata (repository URL, video title, etc.) that the selected steps need when running in a TTY. In non-interactive contexts, missing data causes the run to exit with instructions.

## Configuration Summary

Before execution, targeted mode prints a table showing:

- Resolved input path and optional metadata (repository URL, video title).
- Which processing stages will run.
- Bunny.net library/video identifiers if applicable.
- Bunny override paths if provided (video, transcript, chapters).
- Log verbosity.

Use this summary to confirm that applied profiles and CLI flags match expectations before any processing begins.

## Logging and Output

- Logs stream to the console and `video_processor.log`.
- All generated artifacts land inside the `output/` folder within the chosen input directory.
- Bunny uploads rely on environment variables (`BUNNY_LIBRARY_ID`, `BUNNY_ACCESS_KEY`, etc.) when optional IDs are not provided through prompts, profiles, or CLI overrides.
