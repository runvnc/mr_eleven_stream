#!/usr/bin/env python3
"""
Example usage of the ElevenLabs Streaming TTS plugin.

This demonstrates how to use the stream_tts service in various scenarios,
including the new local playback feature.
"""

import asyncio
import logging
import os
from typing import AsyncGenerator

# Configure logging to see streaming details
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock SIP session for demonstration
class MockSipSession:
    """Mock SIP session for demonstration purposes."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.audio_chunks_received = 0
    
    async def send_audio(self, audio_chunk: bytes):
        """Simulate sending audio to SIP phone."""
        self.audio_chunks_received += 1
        logger.info(f"SIP {self.session_id}: Sent audio chunk {self.audio_chunks_received} ({len(audio_chunk)} bytes)")
        
        # Simulate network delay
        await asyncio.sleep(0.01)
    
    async def listen_for_response(self):
        """Simulate listening for user response."""
        logger.info(f"SIP {self.session_id}: Listening for user response...")
        await asyncio.sleep(2)  # Simulate user thinking time
        return "User said: Hello, I need help with my account."

async def basic_tts_example():
    """Basic example of streaming TTS."""
    print("\n=== Basic TTS Streaming Example ===")
    
    try:
        # Import the service (this would be available in MindRoot)
        from lib.providers.services import get_service
        stream_tts = get_service('stream_tts')
        
        text = "Hello! Welcome to our automated phone system. How can I assist you today?"
        
        chunk_count = 0
        total_bytes = 0
        
        async for audio_chunk in stream_tts(text):
            chunk_count += 1
            total_bytes += len(audio_chunk)
            print(f"Received chunk {chunk_count}: {len(audio_chunk)} bytes")
            
            # In a real scenario, you'd send this to your audio system
            # await audio_system.play(audio_chunk)
        
        print(f"Streaming complete! Total: {chunk_count} chunks, {total_bytes} bytes")
        
    except ImportError:
        print("Note: This example requires the MindRoot framework to run.")
        print("The service would be available as: get_service('stream_tts')")

async def local_playback_example():
    """Example demonstrating local playback feature."""
    print("\n=== Local Playback Example ===")
    
    # Check if local playback is enabled
    local_playback = os.getenv('MR_TTS_PLAY_LOCAL', '').lower() in ('1', 'true', 'yes', 'on')
    
    if local_playback:
        print("✓ Local playback is ENABLED (MR_TTS_PLAY_LOCAL=true)")
        print("Audio will be played locally AND streamed to backend systems")
    else:
        print("ℹ Local playback is DISABLED")
        print("To enable: export MR_TTS_PLAY_LOCAL=true")
        print("Audio will only be streamed to backend systems")
    
    try:
        # This would be the actual service call in MindRoot
        # from lib.providers.services import get_service
        # stream_tts = get_service('stream_tts')
        
        text = "This is a test of the local playback feature. You should hear this audio if playback is enabled."
        
        print(f"\nStreaming text: '{text}'")
        
        if local_playback:
            print("🔊 You should hear audio playing locally...")
        
        # Simulate streaming
        for i in range(8):  # Simulate 8 audio chunks
            fake_chunk = b'\x00' * 160  # Simulate 160 bytes of audio
            print(f"Chunk {i+1}: {len(fake_chunk)} bytes")
            await asyncio.sleep(0.1)  # Simulate streaming delay
        
        print("Streaming complete!")
        
        if local_playback:
            print("🎵 Local playback should have finished")
        
    except Exception as e:
        print(f"Error: {e}")

async def sip_phone_example():
    """Example of using TTS with a SIP phone system."""
    print("\n=== SIP Phone Integration Example ===")
    
    # Simulate incoming call
    sip_session = MockSipSession("call_001")
    
    try:
        # This would be the actual service call in MindRoot
        # from lib.providers.services import get_service
        # stream_tts = get_service('stream_tts')
        
        # Simulate the TTS streaming
        messages = [
            "Thank you for calling our support line.",
            "Please hold while I connect you to an agent.",
            "Your call is important to us."
        ]
        
        for message in messages:
            print(f"\nStreaming: '{message}'")
            
            # In real usage:
            # async for audio_chunk in stream_tts(message):
            #     await sip_session.send_audio(audio_chunk)
            
            # Simulate streaming chunks
            for i in range(5):  # Simulate 5 audio chunks per message
                fake_chunk = b'\x00' * 160  # Simulate 160 bytes of ulaw audio
                await sip_session.send_audio(fake_chunk)
        
        # Listen for user response
        user_response = await sip_session.listen_for_response()
        print(f"User response: {user_response}")
        
    except Exception as e:
        print(f"Error in SIP call: {e}")

async def custom_voice_example():
    """Example using custom voice and model settings."""
    print("\n=== Custom Voice Configuration Example ===")
    
    try:
        # from lib.providers.services import get_service
        # stream_tts = get_service('stream_tts')
        
        # Example with custom settings
        custom_config = {
            'text': "This message uses a custom voice and high-quality model.",
            'voice_id': 'pNInz6obpgDQGcFmaJgB',  # Adam voice
            'model_id': 'eleven_multilingual_v2',  # Higher quality
            'output_format': 'pcm_22050'  # Higher quality audio
        }
        
        print(f"Configuration: {custom_config}")
        print("In MindRoot, you would call:")
        print(f"async for chunk in stream_tts(**custom_config):")
        print("    await process_audio_chunk(chunk)")
        
        local_playback = os.getenv('MR_TTS_PLAY_LOCAL', '').lower() in ('1', 'true', 'yes', 'on')
        if local_playback:
            print("\n🔊 With local playback enabled, you would hear:")
            print("- High-quality audio using Adam's voice")
            print("- Audio played locally AND streamed to backend")
        
    except Exception as e:
        print(f"Error: {e}")

async def speak_command_example():
    """Example of the speak command for AI agents."""
    print("\n=== Speak Command Example (AI Agents) ===")
    
    try:
        print("AI agents can use the 'speak' command like this:")
        
        examples = [
            '{"speak": {"text": "Welcome to our automated system"}}',
            '{"speak": {"text": "Hello, I\'m Adam", "voice_id": "pNInz6obpgDQGcFmaJgB"}}',
            '{"speak": {"text": "Thank you for calling. Please hold while I connect you to an agent."}}'
        ]
        
        for i, example in enumerate(examples, 1):
            print(f"\nExample {i}:")
            print(f"Command: {example}")
            
            # Simulate command execution
            print("Response: Speech streaming completed: 45 characters, 12 audio chunks")
            
            local_playback = os.getenv('MR_TTS_PLAY_LOCAL', '').lower() in ('1', 'true', 'yes', 'on')
            if local_playback:
                print("          (also played locally)")
        
        print("\nThe speak command:")
        print("✓ Streams audio in real-time to backend systems")
        print("✓ Returns a status message when complete")
        print("✓ Optionally plays locally if MR_TTS_PLAY_LOCAL=true")
        print("✓ Supports custom voice_id parameter")
        
    except Exception as e:
        print(f"Error: {e}")

async def error_handling_example():
    """Example of proper error handling."""
    print("\n=== Error Handling Example ===")
    
    try:
        # from lib.providers.services import get_service
        # stream_tts = get_service('stream_tts')
        
        print("Proper error handling pattern:")
        print("""
try:
    async for audio_chunk in stream_tts("Your message here"):
        # Process each chunk
        await send_to_audio_system(audio_chunk)
        
except ValueError as e:
    # Handle configuration errors (missing API key, etc.)
    logger.error(f"Configuration error: {e}")
    
except Exception as e:
    # Handle streaming errors
    logger.error(f"Streaming error: {e}")
    # Implement fallback (e.g., text-only response)
""")
        
        print("\nLocal playback error handling:")
        print("- Missing audio libraries: Install with pip install -e '.[playback]'")
        print("- Audio device issues: Check system permissions")
        print("- Format compatibility: Plugin auto-converts ulaw to MP3 for local playback")
        
    except Exception as e:
        print(f"Error: {e}")

async def performance_monitoring_example():
    """Example of monitoring streaming performance."""
    print("\n=== Performance Monitoring Example ===")
    
    import time
    
    try:
        start_time = time.time()
        chunk_count = 0
        total_bytes = 0
        first_chunk_time = None
        
        text = "This is a performance test message to measure streaming latency and throughput."
        
        print(f"Starting TTS for: '{text}'")
        
        local_playback = os.getenv('MR_TTS_PLAY_LOCAL', '').lower() in ('1', 'true', 'yes', 'on')
        if local_playback:
            print("🔊 Local playback enabled - audio will play during streaming")
        
        # In real usage:
        # async for audio_chunk in stream_tts(text):
        
        # Simulate streaming performance
        for i in range(10):  # Simulate 10 chunks
            if first_chunk_time is None:
                first_chunk_time = time.time()
                print(f"Time to first chunk: {first_chunk_time - start_time:.3f}s")
            
            chunk_count += 1
            chunk_size = 160  # Typical ulaw chunk size
            total_bytes += chunk_size
            
            print(f"Chunk {chunk_count}: {chunk_size} bytes")
            await asyncio.sleep(0.02)  # Simulate processing time
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\nPerformance Summary:")
        print(f"Total time: {total_time:.3f}s")
        print(f"Total chunks: {chunk_count}")
        print(f"Total bytes: {total_bytes}")
        print(f"Average chunk rate: {chunk_count / total_time:.1f} chunks/sec")
        print(f"Average throughput: {total_bytes / total_time:.1f} bytes/sec")
        
        if local_playback:
            print(f"Local playback: Enabled (adds minimal overhead)")
        
    except Exception as e:
        print(f"Error: {e}")

async def environment_setup_example():
    """Example showing environment variable setup."""
    print("\n=== Environment Setup Example ===")
    
    # Check current environment
    api_key = os.getenv('ELEVENLABS_API_KEY')
    local_playback = os.getenv('MR_TTS_PLAY_LOCAL', '').lower() in ('1', 'true', 'yes', 'on')
    
    print("Current Environment:")
    print(f"ELEVENLABS_API_KEY: {'✓ Set' if api_key else '✗ Not set'}")
    print(f"MR_TTS_PLAY_LOCAL: {'✓ Enabled' if local_playback else '✗ Disabled'}")
    
    print("\nTo set up the environment:")
    print("")
    print("# Required - ElevenLabs API key")
    print("export ELEVENLABS_API_KEY='your_api_key_here'")
    print("")
    print("# Optional - Enable local playback for testing")
    print("export MR_TTS_PLAY_LOCAL=true")
    print("")
    print("# Install with playback support")
    print("pip install -e '.[playback]'")
    print("")
    
    if not api_key:
        print("⚠️  Warning: ELEVENLABS_API_KEY not set - plugin will not work")
    
    if not local_playback:
        print("ℹ️  Info: Local playback disabled - audio will only stream to backend")
        print("   To test locally: export MR_TTS_PLAY_LOCAL=true")

async def main():
    """Run all examples."""
    print("ElevenLabs Streaming TTS Plugin - Usage Examples")
    print("=" * 60)
    
    await environment_setup_example()
    await basic_tts_example()
    await local_playback_example()
    await speak_command_example()
    await sip_phone_example()
    await custom_voice_example()
    await error_handling_example()
    await performance_monitoring_example()
    
    print("\n=== Installation Instructions ===")
    print("1. Set your ElevenLabs API key:")
    print("   export ELEVENLABS_API_KEY='your_key_here'")
    print("\n2. Install the plugin:")
    print("   cd /xfiles/upd5/mr_eleven_stream")
    print("   pip install -e .")
    print("\n3. Optional - Enable local playback:")
    print("   export MR_TTS_PLAY_LOCAL=true")
    print("   pip install -e '.[playback]'  # Install audio libraries")
    print("\n4. Use in MindRoot:")
    print("   from lib.providers.services import get_service")
    print("   stream_tts = get_service('stream_tts')")
    print("\n5. AI agents can use the speak command:")
    print('   {"speak": {"text": "Hello world"}}')

if __name__ == "__main__":
    asyncio.run(main())
