# TODO

- [x] rename file final video file with llm
- [x] identify when to add cards and links to add to the video description
- [x] output files into ./output directory
- [X] rewrite linkedin post with shorter, more direct version
  - [X] add example
  - [X] make it remove adverbs
- [X] rewrite twitter post
- [x] add tests
- [X] refactor script
- [X] improve CLI UX
- [X] deploy automatically to bunny.net
  - [X] upload transcription & chapters through API
- [X] switch to langchain for LLM calls
- [X] integrate langsmith for tracing
- [X] fix chapter names with LLM right into the json file

- [x] generate a blog post (skill)
  - [x] create agent with access to github repo (skill)
  - [x] have agent write the blog post with transcript & repo (skill)

## New Commands

- [x] `video extract-audio` - extract audio track from video
- [x] `video enhance-audio` - voice enhancement (noise reduction, normalization)
- [x] `video youtube-upload` - upload to YouTube via Data API

## Maintenance

- [ ] Split the `VideoProcessor` facade into per-domain modules/functions with explicit dependencies (mixins currently share implicit state)
- [ ] Standardize exit codes and add a `--json` output option for scripting
- [ ] Add a LICENSE file
- [ ] Add mypy to dev tooling