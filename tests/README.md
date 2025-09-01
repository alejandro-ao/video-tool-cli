# Video Tool Test Suite

This directory contains comprehensive unit and integration tests for the video-tool package.

## Overview

The test suite is designed to thoroughly test all components of the video processing pipeline, including:

- File discovery and metadata extraction
- Video processing operations (silence removal, concatenation, compression)
- Content generation (transcription, descriptions, SEO keywords)
- Main workflow integration
- Error handling and edge cases

## Test Structure

```
tests/
├── __init__.py                    # Test package initialization
├── conftest.py                    # Shared fixtures and test configuration
├── pytest.ini                    # Pytest configuration
├── test-requirements.txt          # Test dependencies
├── README.md                      # This documentation
├── test_data/                     # Test data and mock generators
│   ├── __init__.py
│   ├── mock_generators.py         # Mock file generators for testing
│   └── sample_data.py             # Sample test data and API responses
├── test_file_methods.py           # Tests for file discovery methods
├── test_video_processing.py       # Tests for video processing methods
├── test_content_generation.py     # Tests for content generation methods
└── test_main_integration.py       # Integration tests for main workflow
```

## Test Categories

Tests are organized using pytest markers:

- **unit**: Unit tests for individual methods
- **integration**: Integration tests for complete workflows
- **slow**: Tests that take longer to execute
- **requires_ffmpeg**: Tests requiring FFmpeg installation
- **requires_api**: Tests requiring API keys (OpenAI, Groq)

## Running Tests

### Quick Start

```bash
# Install test dependencies
python -m pip install -r tests/test-requirements.txt

# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=video_tool --cov=main --cov-report=html
```

### Using the Test Runner

A convenient test runner script is provided:

```bash
# Make the script executable
chmod +x run_tests.py

# Run all tests
./run_tests.py

# Run with coverage
./run_tests.py --coverage

# Run only unit tests
./run_tests.py --unit-only

# Run only fast tests (exclude slow, ffmpeg, api tests)
./run_tests.py --fast-only

# Run tests matching a pattern
./run_tests.py --test-pattern "test_file*"

# Install dependencies and run all checks
./run_tests.py --install-deps --all
```

### Test Runner Options

```bash
# Test execution
-v, --verbose              Verbose test output
-q, --quiet                Quiet test output
--coverage                 Run tests with coverage reporting
--unit-only                Run only unit tests
--integration-only         Run only integration tests
--fast-only                Run only fast tests
--no-external              Exclude tests requiring external dependencies
-k PATTERN                 Run tests matching pattern
-n NUM                     Run tests in parallel
--fail-fast                Stop on first test failure
--capture {auto,no,sys}    Control output capturing
--junit-xml                Generate JUnit XML report

# Utilities
--install-deps             Install test dependencies
--lint                     Run linting checks
--type-check               Run type checking
--coverage-report          Generate coverage report
--clean                    Clean test artifacts
--all                      Run tests, linting, and type checking
```

## Test Configuration

### Environment Variables

For tests requiring API access, set these environment variables:

```bash
export OPENAI_API_KEY="your-openai-api-key"
export GROQ_API_KEY="your-groq-api-key"
```

### Pytest Configuration

The `pytest.ini` file contains default configuration:

```ini
[tool:pytest]
python_files = test_*.py
python_classes = Test*
python_functions = test_*
testpaths = tests
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow running tests
    requires_ffmpeg: Tests requiring FFmpeg
    requires_api: Tests requiring API keys
```

## Test Data and Mocks

### Mock Generators

The `test_data/mock_generators.py` module provides utilities to create mock files:

```python
from tests.test_data.mock_generators import (
    MockVideoGenerator,
    MockAudioGenerator,
    MockTranscriptGenerator,
    create_complete_test_dataset
)

# Create mock MP4 file
MockVideoGenerator.create_mock_mp4("test_video.mp4")

# Create complete test dataset
test_data = create_complete_test_dataset(temp_dir)
```

### Sample Data

The `test_data/sample_data.py` module contains sample API responses and test data:

```python
from tests.test_data.sample_data import (
    SAMPLE_GROQ_RESPONSE,
    SAMPLE_OPENAI_DESCRIPTION_RESPONSE,
    SAMPLE_VIDEO_METADATA
)
```

### Fixtures

Common fixtures are defined in `conftest.py`:

- `temp_dir`: Temporary directory for test files
- `mock_video_processor`: Mocked VideoProcessor with dependencies
- `mock_ffmpeg_success`: Mock successful ffmpeg subprocess calls
- `mock_ffprobe_video_info`: Mock ffprobe video information
- `mock_ffprobe_audio_info`: Mock ffprobe audio information
- `setup_test_env`: Environment setup for tests

For sample data and mock generators, use:
- `tests.test_data.sample_data`: Comprehensive sample API responses and test data
- `tests.test_data.mock_generators`: File generation utilities for testing

## Test Coverage

The test suite aims for comprehensive coverage of:

### VideoProcessor Methods

- ✅ `get_mp4_files()` - File discovery
- ✅ `extract_duration_csv()` - Metadata extraction
- ✅ `remove_silences()` - Silence removal
- ✅ `concatenate_videos()` - Video concatenation
- ✅ `match_video_encoding()` - Encoding matching
- ✅ `compress_video()` - Video compression
- ✅ `generate_timestamps()` - Timestamp generation
- ✅ `generate_transcript()` - Transcription
- ✅ `generate_description()` - Description generation
- ✅ `generate_seo_keywords()` - SEO keyword generation

### Helper Methods

- ✅ `_get_video_metadata()` - FFprobe integration
- ✅ `_process_video_with_concat_filter()` - Video processing
- ✅ `_clean_vtt_transcript()` - VTT cleaning
- ✅ `_merge_vtt_transcripts()` - VTT merging
- ✅ `_groq_verbose_json_to_vtt()` - Groq response conversion
- ✅ Timestamp manipulation utilities

### Main Workflow

- ✅ User input collection
- ✅ Complete processing pipeline
- ✅ Partial workflow execution
- ✅ Error handling and recovery
- ✅ File dependency management

## Writing New Tests

### Test Structure

Follow this structure for new test files:

```python
"""Tests for [component description]."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from video_tool.video_processor import VideoProcessor
from tests.test_data.sample_data import SAMPLE_DATA


class TestComponentName:
    """Test class for specific component."""
    
    def test_method_success(self, mock_video_processor):
        """Test successful method execution."""
        # Arrange
        expected_result = "expected"
        
        # Act
        result = mock_video_processor.method_name()
        
        # Assert
        assert result == expected_result
    
    def test_method_error_handling(self, mock_video_processor):
        """Test method error handling."""
        # Test error scenarios
        pass
    
    @pytest.mark.slow
    def test_method_integration(self, temp_dir):
        """Test method integration with real files."""
        # Integration test with real file operations
        pass
```

### Best Practices

1. **Use descriptive test names** that explain what is being tested
2. **Follow AAA pattern** (Arrange, Act, Assert)
3. **Mock external dependencies** (APIs, file system, subprocess calls)
4. **Test both success and failure scenarios**
5. **Use appropriate markers** for test categorization
6. **Keep tests independent** - each test should be able to run in isolation
7. **Use fixtures** for common setup and teardown
8. **Test edge cases** and boundary conditions

### Adding Test Markers

```python
@pytest.mark.unit
def test_unit_functionality():
    pass

@pytest.mark.integration
def test_integration_workflow():
    pass

@pytest.mark.slow
def test_long_running_operation():
    pass

@pytest.mark.requires_ffmpeg
def test_ffmpeg_operation():
    pass

@pytest.mark.requires_api
def test_api_integration():
    pass
```

## Continuous Integration

For CI/CD pipelines, use these commands:

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r tests/test-requirements.txt

# Run fast tests only (no external dependencies)
python run_tests.py --fast-only --coverage --junit-xml

# Run linting and type checking
python run_tests.py --lint --type-check
```

## Troubleshooting

### Common Issues

1. **FFmpeg not found**: Install FFmpeg or skip tests with `--no-external`
2. **API key missing**: Set environment variables or skip with `--fast-only`
3. **Permission errors**: Ensure test directory is writable
4. **Import errors**: Verify package installation and PYTHONPATH

### Debug Mode

```bash
# Run with verbose output and no capture
python run_tests.py -v --capture=no

# Run specific test with debugging
python -m pytest tests/test_file_methods.py::TestGetMp4Files::test_finds_existing_files -v -s
```

### Coverage Reports

```bash
# Generate HTML coverage report
python run_tests.py --coverage

# View coverage report
open htmlcov/index.html

# Generate terminal coverage report
python run_tests.py --coverage-report
```

## Contributing

When adding new features:

1. Write tests first (TDD approach)
2. Ensure all existing tests pass
3. Add appropriate test markers
4. Update this documentation if needed
5. Maintain test coverage above 90%

For questions or issues with the test suite, please refer to the main project documentation or create an issue in the repository.