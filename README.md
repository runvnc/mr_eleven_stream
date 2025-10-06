# ElevenLabs Streaming TTS Plugin for MindRoot

This plugin provides real-time text-to-speech streaming using the ElevenLabs API, specifically designed for backend use with SIP phone systems.

## Features

- Real-time audio streaming (no waiting for full audio generation)
- Optimized for SIP phone integration with ulaw_8000 format
- Uses ElevenLabs Flash v2.5 model for ultra-low latency
- Async generator interface for efficient streaming
- Configurable voice, model, and output format
- Both service and command interfaces available
- **Optional local audio playback** for testing and development

## Installation

### Basic Installation

1. Install the plugin:
```bash
cd /xfiles/upd5/mr_eleven_stream
pip install -e .
```

2. Set your ElevenLabs API key:
```bash
export ELEVENLABS_API_KEY="your_api_key_here"
```

3. Enable the plugin in MindRoot admin interface

### Installation with Local Playback Support

For local audio playback during development/testing:

```bash
cd /xfiles/upd5/mr_eleven_stream
pip install -e ".[playback]"
```

This installs additional audio libraries (pygame, pydub, simpleaudio) for local playback.

## Usage

### Command Interface (for AI Agents)

The plugin provides a `speak` command that AI agents can use:

```json
{ "speak": { "text": "Hello, this is a test message" } }
{ "speak": { "text": "Custom voice test", "voice_id": "pNInz6obpgDQGcFmaJgB" } }
```

The command returns a status message and streams audio in real-time to the backend audio system.

### Service Interface (for Developers)

The plugin also provides a `stream_tts` service for direct use in code:

```python
from lib.providers.services import get_service

# Get the service
stream_tts = get_service('stream_tts')

# Stream TTS audio
async for audio_chunk in stream_tts("Hello, this is a test message"):
    # Send audio_chunk to your SIP phone system
    await send_to_phone_system(audio_chunk)
```

## Local Audio Playback

### Enable Local Playback

Set the environment variable to enable local audio playback:

```bash
export MR_TTS_PLAY_LOCAL=true
# or
export MR_TTS_PLAY_LOCAL=1
```

When enabled, the TTS audio will be played on the local device **in addition to** streaming to backend systems. This is useful for:

- Testing and development
- Debugging audio quality
- Demonstrations
- Local development without SIP systems

### Audio Library Support

The plugin tries multiple audio libraries in order of preference:

1. **elevenlabs.play** (if available with elevenlabs package)
2. **pygame** (cross-platform, good compatibility)
3. **pydub + simpleaudio** (high quality, more dependencies)

Install playback dependencies:
```bash
pip install -e ".[playback]"  # Installs pygame, pydub, simpleaudio
```

### Format Compatibility

- For local playback, the plugin automatically uses MP3 format instead of ulaw_8000
- This ensures compatibility with local audio libraries
- Backend streaming still uses the requested format (e.g., ulaw_8000 for SIP)

## Configuration

### Default Settings
- **Voice ID**: `JBFqnCBsd6RMkjVDRZzb` (George voice)
- **Model**: `eleven_flash_v2_5` (ultra-low latency)
- **Output Format**: `ulaw_8000` (SIP/telephony standard)
- **Local Playback**: Disabled by default

### Environment Variables

```bash
# Required
ELEVENLABS_API_KEY=your_api_key_here

# Optional - Enable local playback
MR_TTS_PLAY_LOCAL=true  # or 1, yes, on

# Optional - Override defaults
DEFAULT_VOICE_ID=JBFqnCBsd6RMkjVDRZzb
DEFAULT_MODEL_ID=eleven_flash_v2_5
DEFAULT_OUTPUT_FORMAT=ulaw_8000
```

### Custom Configuration (Service Only)

You can override defaults when calling the service directly:

```python
async for chunk in stream_tts(
    text="Custom message",
    voice_id="your_voice_id",
    model_id="eleven_multilingual_v2",
    output_format="mp3_44100_128"
):
    # Process chunk
    pass
```

### Voice Options for Command

The `speak` command accepts an optional `voice_id` parameter:

```json
{ "speak": { "text": "Hello with Adam voice", "voice_id": "pNInz6obpgDQGcFmaJgB" } }
```

## Available Voices

To list available voices:

```python
from elevenlabs.client import ElevenLabs

client = ElevenLabs(api_key="your_key")
voices = client.voices.search()
for voice in voices.voices:
    print(f"ID: {voice.voice_id}, Name: {voice.name}")
```

Common voice IDs:
- `JBFqnCBsd6RMkjVDRZzb` - George (default)
- `pNInz6obpgDQGcFmaJgB` - Adam
- `21m00Tcm4TlvDq8ikWAM` - Rachel
- `AZnzlk1XvdvUeBnXmlld` - Domi

## Available Models

- `eleven_flash_v2_5` - Ultra-low latency (recommended for real-time)
- `eleven_turbo_v2_5` - Good balance of quality and latency
- `eleven_multilingual_v2` - Best quality, supports 29 languages

## Output Formats

- `ulaw_8000` - Standard for SIP/telephony (recommended)
- `mp3_44100_128` - Standard MP3
- `pcm_16000` - Raw PCM audio
- `pcm_22050` - Higher quality PCM
- `pcm_24000` - Even higher quality PCM
- `pcm_44100` - CD quality PCM

## Error Handling

The service includes comprehensive error handling and logging:

```python
import logging

# Enable debug logging to see streaming details
logging.getLogger('mr_eleven_stream').setLevel(logging.DEBUG)

try:
    async for chunk in stream_tts("Test message"):
        # Process chunk
        pass
except Exception as e:
    print(f"TTS streaming error: {e}")
```

## Development and Testing

### Local Testing

1. Enable local playback:
   ```bash
   export MR_TTS_PLAY_LOCAL=true
   ```

2. Install playback dependencies:
   ```bash
   pip install -e ".[playback]"
   ```

3. Test the speak command:
   ```json
   { "speak": { "text": "This is a test message" } }
   ```

4. You should hear the audio locally AND see streaming status

### SIP Integration Example

Here's a basic example of how you might integrate this with a SIP phone system:

```python
import asyncio
from lib.providers.services import get_service

async def handle_phone_call(sip_session):
    """Handle incoming phone call with TTS response."""
    stream_tts = get_service('stream_tts')
    
    # Generate response text
    response_text = "Hello! Thank you for calling. How can I help you today?"
    
    # Stream TTS audio to phone
    async for audio_chunk in stream_tts(response_text):
        # Send audio chunk to SIP session
        await sip_session.send_audio(audio_chunk)
    
    # Wait for user response
    await sip_session.listen_for_response()
```

## AI Agent Integration

AI agents can use the `speak` command to generate speech:

```python
# In an AI agent's command processing
commands = [
    {"speak": {"text": "Welcome to our service!"}},
    {"speak": {"text": "How can I help you today?", "voice_id": "pNInz6obpgDQGcFmaJgB"}}
]
```

The audio will be streamed to the backend audio system automatically, and optionally played locally if `MR_TTS_PLAY_LOCAL` is enabled.

## Performance Notes

- The plugin uses `eleven_flash_v2_5` by default for minimal latency
- Audio chunks are yielded as soon as they're available
- The service includes `asyncio.sleep(0)` calls to prevent blocking
- Memory usage is minimal as audio is streamed, not buffered
- The `speak` command processes all chunks but returns a summary
- Local playback runs in a thread pool to avoid blocking streaming

## Plugin Structure

- **Service**: `stream_tts` - Returns async generator of audio chunks
- **Command**: `speak` - Processes streaming and returns status message
- **Backend**: Designed for SIP phones and audio pipelines
- **Real-time**: No buffering, immediate streaming
- **Local playback**: Optional for development and testing

## Troubleshooting

### Local Playback Issues

1. **No audio playback libraries available**:
   ```bash
   pip install -e ".[playback]"
   ```

2. **Audio format not supported**:
   - The plugin automatically uses MP3 for local playback
   - ulaw_8000 is converted to mp3_44100_128 for local playback

3. **Permission errors on audio device**:
   - Check system audio permissions
   - Try different audio libraries (pygame vs pydub)

### General Issues

1. **"No module named 'elevenlabs'"**:
   ```bash
   pip install elevenlabs
   ```

2. **"ElevenLabs API key not found"**:
   ```bash
   export ELEVENLABS_API_KEY="your_key"
   ```

3. **High latency**:
   - Use `model_id="eleven_flash_v2_5"`
   - Check internet connection

## Requirements

- Python 3.8+
- ElevenLabs API key
- `elevenlabs` Python SDK
- MindRoot framework
- Optional: pygame, pydub, simpleaudio (for local playback)

## License

MIT License
