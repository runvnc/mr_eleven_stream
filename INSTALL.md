# Installation Guide for ElevenLabs Streaming TTS Plugin

## Quick Start

1. **Set your ElevenLabs API key:**
   ```bash
   export ELEVENLABS_API_KEY="your_elevenlabs_api_key_here"
   ```

2. **Install the plugin:**
   ```bash
   cd /xfiles/upd5/mr_eleven_stream
   pip install -e .
   ```

3. **Verify installation:**
   ```bash
   python test_plugin.py
   ```

## Detailed Installation Steps

### 1. Get ElevenLabs API Key

1. Sign up at [ElevenLabs](https://elevenlabs.io/)
2. Go to your profile settings
3. Copy your API key
4. Set the environment variable:
   ```bash
   # Add to your ~/.bashrc or ~/.zshrc for persistence
   export ELEVENLABS_API_KEY="your_key_here"
   ```

### 2. Install Dependencies

The plugin will automatically install the required `elevenlabs` package:

```bash
cd /xfiles/upd5/mr_eleven_stream
pip install -e .
```

### 3. Enable in MindRoot

1. Start MindRoot
2. Go to the admin interface
3. Navigate to Plugin Management
4. Enable the "ElevenLabs Streaming TTS" plugin
5. Enable the "stream_tts" service for your agents

### 4. Test the Installation

Run the test suite:
```bash
python test_plugin.py
```

All tests should pass if everything is installed correctly.

### 5. Usage Example

```python
from lib.providers.services import get_service

# Get the streaming TTS service
stream_tts = get_service('stream_tts')

# Stream audio for SIP phone integration
async def handle_phone_call(text_to_speak):
    async for audio_chunk in stream_tts(text_to_speak):
        # Send audio_chunk to your SIP phone system
        await sip_session.send_audio(audio_chunk)
```

## Troubleshooting

### Common Issues

1. **"No module named 'elevenlabs'"**
   - Run: `pip install elevenlabs`
   - Or reinstall the plugin: `pip install -e .`

2. **"ElevenLabs API key not found"**
   - Set the environment variable: `export ELEVENLABS_API_KEY="your_key"`
   - Check it's set: `echo $ELEVENLABS_API_KEY`

3. **"Service not found"**
   - Enable the plugin in MindRoot admin interface
   - Enable the "stream_tts" service for your agents

4. **Audio quality issues**
   - For SIP phones, use `output_format="ulaw_8000"`
   - For higher quality, use `output_format="pcm_22050"`

5. **High latency**
   - Use `model_id="eleven_flash_v2_5"` for lowest latency
   - Check your internet connection
   - Consider using a closer ElevenLabs server region

### Performance Optimization

1. **For real-time applications:**
   ```python
   async for chunk in stream_tts(
       text="Your message",
       model_id="eleven_flash_v2_5",  # Fastest model
       output_format="ulaw_8000"      # SIP compatible
   ):
       await process_immediately(chunk)
   ```

2. **For higher quality:**
   ```python
   async for chunk in stream_tts(
       text="Your message",
       model_id="eleven_multilingual_v2",  # Best quality
       output_format="pcm_22050"           # Higher quality audio
   ):
       await process_chunk(chunk)
   ```

## Support

For issues with:
- **Plugin installation**: Check this guide and test_plugin.py output
- **ElevenLabs API**: Visit [ElevenLabs Documentation](https://elevenlabs.io/docs)
- **MindRoot integration**: Check MindRoot documentation

## File Structure

```
/xfiles/upd5/mr_eleven_stream/
├── plugin_info.json          # Plugin metadata
├── setup.py                  # Installation configuration
├── pyproject.toml           # Build system configuration
├── README.md                # Main documentation
├── INSTALL.md               # This installation guide
├── .env.example             # Environment variable template
├── test_plugin.py           # Test suite
├── example_usage.py         # Usage examples
└── src/
    └── mr_eleven_stream/
        ├── __init__.py      # Plugin initialization
        └── mod.py           # Main plugin code with stream_tts service
```
