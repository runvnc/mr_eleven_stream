import os
import asyncio
import io
import subprocess
from typing import AsyncGenerator, Optional, Dict, Any
from elevenlabs.client import ElevenLabs
from lib.providers.services import service, service_manager
from lib.providers.commands import command
import logging

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George voice
DEFAULT_MODEL_ID = "eleven_flash_v2_5"  # Ultra-low latency for real-time
DEFAULT_OUTPUT_FORMAT = "ulaw_8000"  # Standard for SIP/telephony
SIMILARITY_BOOST_DEFAULT = os.environ.get('ELEVENLABS_SIMILARITY_BOOST_DEFAULT', 0.75)
SPEECH_SPEED_DEFAULT = os.environ.get('ELEVENLABS_SPEECH_SPEED_DEFAULT', 1.0)
STABILITY_DEFAULT = os.environ.get('ELEVENLABS_STABILITY_DEFAULT', 0.5)


# Local playback support
def _get_local_playback_enabled() -> bool:
    """Check if local playback is enabled via environment variable."""
    return service_manager.functions.get('sip_audio_out_chunk', None) is None
    #return os.getenv('MR_TTS_PLAY_LOCAL', '').lower() in ('1', 'true', 'yes', 'on')

def _play_audio_locally(audio_data: bytes, output_format: str) -> None:
    """Play audio data locally using available audio libraries."""
    try:
        # Try to use elevenlabs.play first (if available)
        try:
            from elevenlabs.play import play
            logger.debug("Trying to play audio locally.")
            play(audio_data)
            logger.debug("Played audio using elevenlabs.play")
            return
        except ImportError:
            pass
 
        # Try ffplay first for direct streaming (most efficient)
        try:
            logger.debug("Trying to play audio directly with ffplay")
            
            # Determine ffplay parameters based on format
            if 'ulaw' in output_format.lower():
                # For ulaw, specify format and audio parameters
                cmd = [
                    'ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet',
                    '-f', 'mulaw', '-ar', '8000', '-ac', '1', '-i', 'pipe:0'
                ]
            elif 'mp3' in output_format.lower():
                cmd = [
                    'ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet',
                    '-f', 'mp3', '-i', 'pipe:0'
                ]
            elif 'pcm' in output_format.lower():
                # Determine sample rate from format
                sample_rate = 22050
                if '16000' in output_format:
                    sample_rate = 16000
                elif '44100' in output_format:
                    sample_rate = 44100
                elif '24000' in output_format:
                    sample_rate = 24000
                
                cmd = [
                    'ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet',
                    '-f', 's16le', '-ar', str(sample_rate), '-ac', '1', '-i', 'pipe:0'
                ]
            else:
                # Try generic format
                cmd = [
                    'ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet',
                    '-i', 'pipe:0'
                ]
            
            # Pipe audio data directly to ffplay
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            process.communicate(input=audio_data)
            
            if process.returncode == 0:
                logger.debug("Played audio using ffplay")
                return
            else:
                logger.warning(f"ffplay failed with return code {process.returncode}")
        except FileNotFoundError:
            logger.debug("ffplay not available")
        except Exception as e:
            logger.warning(f"ffplay error: {str(e)}")
        
       
        # Fallback to pygame if available
        try:
            import pygame
            pygame.mixer.init()
            logger.debug("Trying to play locally with pygame") 
            # Convert audio data to a format pygame can handle
            audio_io = io.BytesIO(audio_data)
            pygame.mixer.music.load(audio_io)
            pygame.mixer.music.play()
            
            # Wait for playback to complete
            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)
            
            logger.debug("Played audio using pygame")
            return
        except ImportError:
            pass
        
        # Fallback to pydub + simpleaudio if available
        try:
            from pydub import AudioSegment
            from pydub.playback import play as pydub_play
            
            # Determine audio format for pydub
            if 'mp3' in output_format.lower():
                audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
            elif 'pcm' in output_format.lower():
                # Assume 16-bit PCM
                sample_rate = 22050  # Default
                if '16000' in output_format:
                    sample_rate = 16000
                elif '44100' in output_format:
                    sample_rate = 44100
                elif '24000' in output_format:
                    sample_rate = 24000
                
                audio = AudioSegment(
                    audio_data,
                    frame_rate=sample_rate,
                    sample_width=2,  # 16-bit
                    channels=1  # Mono
                )
            else:
                # For other formats (including ulaw), try to convert
                logger.warning(f"Unsupported format for local playback: {output_format}")
                return
            
            pydub_play(audio)
            logger.debug("Played audio using pydub")
            return
        except ImportError:
            pass
        
        logger.warning("No audio playback library available. Install ffplay, elevenlabs[play], pygame, or pydub+simpleaudio for local playback.")
        
    except Exception as e:
        logger.error(f"Error playing audio locally: {str(e)}")

class ElevenLabsStreamer:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('ELEVENLABS_API_KEY')
        if not self.api_key:
            raise ValueError("ElevenLabs API key not found. Set ELEVENLABS_API_KEY environment variable.")
        
        self.client = ElevenLabs(api_key=self.api_key)
        self.local_playback_enabled = _get_local_playback_enabled()
        
        if self.local_playback_enabled:
            logger.info("Local audio playback enabled (MR_TTS_PLAY_LOCAL=true)")
    
    async def stream_text_to_speech(
        self,
        text: str,
        voice_id: str = DEFAULT_VOICE_ID,
        model_id: str = DEFAULT_MODEL_ID,
        output_format: str = DEFAULT_OUTPUT_FORMAT,
        speed: float = SPEECH_SPEED_DEFAULT,
        stability: float = STABILITY_DEFAULT,
        similarity_boost: float = SIMILARITY_BOOST_DEFAULT,
        **kwargs
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream text-to-speech audio in real-time.
        
        Args:
            text: Text to convert to speech
            voice_id: ElevenLabs voice ID
            model_id: Model to use (eleven_flash_v2_5 for low latency)
            output_format: Audio format (ulaw_8000 for SIP compatibility)
            **kwargs: Additional parameters for the TTS API
        
        Yields:
            bytes: Audio chunks as they are generated
        """
        try:
            logger.info(f"Starting TTS stream for text: {text[:50]}...")

            # functions is a dict
            # check if 'sip_audio_out_chunk' is available in service_manager
            if service_manager.functions.get('sip_audio_out_chunk'):
                self.local_playback_enabled = False
            else:
                self.local_playback_enabled = True
            
            # Always use the requested format for streaming (ulaw_8000 for SIP)
            # Local playback will handle format conversion if needed
            if self.local_playback_enabled:
                output_format = "mp3_22050_32"
            # Create the streaming request
            voice_settings = {"stability": stability,
                              "similarity_boost": similarity_boost,
                              "speed": speed }
            audio_stream = self.client.text_to_speech.stream(
                text=text,
                voice_id=voice_id,
                model_id=model_id,
                output_format=output_format,
                **kwargs
            )
            local_audio_buffer = b"" if self.local_playback_enabled else None
             
            chunk_count = 0
            for chunk in audio_stream:
                if isinstance(chunk, bytes):
                    chunk_count += 1
                    logger.debug(f"Yielding audio chunk {chunk_count}, size: {len(chunk)} bytes")
                    
                    # Collect for local playback
                    if self.local_playback_enabled:
                        local_audio_buffer += chunk
                    
                    yield chunk
                    
                    # Allow other coroutines to run
                    await asyncio.sleep(0)
            
            logger.info(f"TTS streaming completed. Total chunks: {chunk_count}")
            
            # Play locally if enabled
            if self.local_playback_enabled and local_audio_buffer:
                logger.info("Playing audio locally...")
                # Run in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, 
                    _play_audio_locally, 
                    local_audio_buffer, 
                    output_format
                )
            
        except Exception as e:
            logger.error(f"Error in TTS streaming: {str(e)}")
            raise

# Global streamer instance
_streamer = None

def get_streamer() -> ElevenLabsStreamer:
    """Get or create the global ElevenLabs streamer instance."""
    global _streamer
    if _streamer is None:
        _streamer = ElevenLabsStreamer()
    return _streamer

@service()
async def stream_tts(
    text: str,
    voice_id: Optional[str] = None,
    model_id: Optional[str] = None,
    output_format: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    **kwargs
) -> AsyncGenerator[bytes, None]:
    """
    Service to stream text-to-speech audio in real-time using ElevenLabs.
    
    This service is designed for backend use with SIP phone calls and returns
    raw audio bytes that can be streamed directly to audio systems.
    
    If MR_TTS_PLAY_LOCAL environment variable is set to true/1/yes/on,
    the audio will also be played locally in addition to streaming.
    
    Args:
        text: Text to convert to speech
        voice_id: ElevenLabs voice ID (optional, uses default if not provided)
        model_id: Model to use (optional, uses eleven_flash_v2_5 for low latency)
        output_format: Audio format (optional, uses ulaw_8000 for SIP compatibility)
        context: MindRoot context (optional)
        **kwargs: Additional parameters for the TTS API
    
    Yields:
        bytes: Audio chunks as they are generated
    
    Example usage:
        async for audio_chunk in stream_tts("Hello, this is a test message"):
            # Send audio_chunk to SIP phone system
            await send_to_phone(audio_chunk)
    
    Environment Variables:
        MR_TTS_PLAY_LOCAL: Set to '1', 'true', 'yes', or 'on' to enable local playback
    """
    try:
        streamer = get_streamer()
        
        # Use provided parameters or defaults
        voice_id = voice_id or DEFAULT_VOICE_ID
        model_id = model_id or DEFAULT_MODEL_ID
        output_format = output_format or DEFAULT_OUTPUT_FORMAT
        
        logger.info(f"Starting TTS service for text: {text[:50]}...")
        
        async for chunk in streamer.stream_text_to_speech(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            output_format=output_format,
            **kwargs
        ):
            yield chunk
            
    except Exception as e:
        logger.error(f"Error in stream_tts service: {str(e)}")
        raise

@command()
async def speak(
    text: str,
    voice_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Convert text to speech using ElevenLabs streaming TTS.
    
    This command streams the audio in real-time and is designed for backend
    integration with phone systems, audio pipelines, or other streaming audio consumers.
    
    If MR_TTS_PLAY_LOCAL environment variable is set, the audio will also be
    played locally in addition to streaming to backend systems.
    
    Args:
        text: Text to convert to speech
        voice_id: ElevenLabs voice ID (optional, uses default George voice if not provided)
        context: MindRoot context (optional)
    
    Returns:
        None
    
    Example:
        { "speak": { "text": "Hello, this is a test message" } }
        { "speak": { "text": "Custom voice test", "voice_id": "pNInz6obpgDQGcFmaJgB" } }
    
    Environment Variables:
        MR_TTS_PLAY_LOCAL: Set to '1', 'true', 'yes', or 'on' to enable local playback
    """
    voiceid = voice_id or DEFAULT_VOICE_ID
    try:
        chunk_count = 0
        local_playback = _get_local_playback_enabled()
        try:
            agent_data = await service_manager.get_agent_data(context.agent_name)
            persona = agent_data["persona"]
            voiceid = persona.get("voice_id", DEFAULT_VOICE_ID)
        except Exception as e:
            logger.warning(f"Could not get agent persona voice_id, using default. Error: {str(e)}")
            voiceid = voice_id or DEFAULT_VOICE_ID

        total_sleep = 0
        chunk_length = 0
        async for chunk in stream_tts(text=text, voice_id=voiceid, context=context):
            chunk_count += 1

            try:
                if not local_playback:
                    should_continue = await service_manager.sip_audio_out_chunk(chunk)
                    chunk_length = len(chunk)
                    chunk_duration = len(chunk) / 8000.0  # seconds of audio
                    to_wait = chunk_duration * 0.98
                    await asyncio.sleep(to_wait)
                    total_sleep += to_wait
                    logger.debug(f"SPEAK_DEBUG: Sent {chunk_count} audio chunks, chunk size: {chunk_length} bytes, total sleep time: {total_sleep:.2f} seconds")
 
                    if not should_continue:
                        logger.debug("SPEAK_DEBUG: SIP output requested to stop streaming.")
                        await asyncio.sleep(1.0)
                        if chunk_count < 3:
                            return "SYSTEM: WARNING - Command interrupted!\n\n"
                        return None
            except Exception as e:
                should_continue = True
                logger.warning(f"Error sending audio chunk to SIP output: {str(e)}. Is SIP enabled?")

        if not local_playback:
            # show chunk len and total sleep time

            logger.info(f"SPEAK_DEBUG: Sent {chunk_count} audio chunks, chunk size: {chunk_length} bytes, total sleep time: {total_sleep:.2f} seconds")
            await asyncio.sleep(0.25)
         
        logger.info(f"Speech streaming completed: {len(text)} characters, {chunk_count} audio chunks{' (also played locally)' if local_playback else ''}")
        return None
        
    except Exception as e:
        logger.error(f"Error in speak command: {str(e)}")
        return None

