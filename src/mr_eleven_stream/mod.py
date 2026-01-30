import os
import asyncio
import io
import subprocess
from typing import AsyncGenerator, Optional, Dict, Any
from elevenlabs.client import ElevenLabs
from lib.providers.services import service, service_manager
from lib.providers.hooks import hook
from lib.providers.commands import command
# use .env for configuration
import dotenv
# Load .env file if present
from .audio_pacer import AudioPacer
dotenv.load_dotenv()

import logging

# Import realtime streaming support
from .realtime_stream import has_active_session, get_session, cleanup_session, is_realtime_streaming_enabled

logger = logging.getLogger(__name__)

# Debug log file
DEBUG_LOG_FILE = "/tmp/tts_debug.log"

def debug_log(msg):
    """Write debug message to dedicated log file."""
    import datetime
    with open(DEBUG_LOG_FILE, 'a') as f:
        f.write(f"{datetime.datetime.now().isoformat()} | {msg}\n")

# Default configuration
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George voice
DEFAULT_MODEL_ID = "eleven_flash_v2_5"  # Ultra-low latency for real-time
DEFAULT_OUTPUT_FORMAT = "ulaw_8000"  # Standard for SIP/telephony
SIMILARITY_BOOST_DEFAULT = os.environ.get('ELEVENLABS_SIMILARITY_BOOST_DEFAULT', 0.75)
SPEECH_SPEED_DEFAULT = os.environ.get('ELEVENLABS_SPEECH_SPEED_DEFAULT', 1.0)
STABILITY_DEFAULT = os.environ.get('ELEVENLABS_STABILITY_DEFAULT', 0.5)
USE_SPEAKER_BOOST_DEFAULT = os.environ.get('ELEVENLABS_USE_SPEAKER_BOOST', 'false').lower() in ('true', '1', 'yes', 'on')

# Global dictionary to track active speak() calls per log_id
_active_speak_locks: Dict[str, asyncio.Lock] = {}
# Global dictionary to track active AudioPacer instances per log_id (for interrupt support)
_active_pacers: Dict[str, Any] = {}



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
        use_speaker_boost: bool = USE_SPEAKER_BOOST_DEFAULT,
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
                              "speed": speed,
                              "use_speaker_boost": use_speaker_boost}
            audio_stream = self.client.text_to_speech.stream(
                text=text,
                voice_id=voice_id,
                model_id=model_id,
                output_format=output_format,
                voice_settings=voice_settings,
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
        # Get log_id from context for lock management
        log_id = None
        if context and hasattr(context, 'log_id'):
            log_id = context.log_id
        
        # If we have a log_id, check if speak() is already running for it
        if log_id:
            # Get or create lock for this log_id
            if log_id not in _active_speak_locks:
                _active_speak_locks[log_id] = asyncio.Lock()
            
            lock = _active_speak_locks[log_id]
            
            # Check if already locked (another speak() is running)
            if lock.locked():
                logger.warning(f"speak() already running for log_id {log_id}, rejecting concurrent call")
                return "ERROR: Speech already in progress for this conversation. Please wait for it to complete."
            
            # Acquire the lock
            await lock.acquire()
        
        # Check if there's an active realtime streaming session
        # If so, finalize it instead of starting a new TTS call
        realtime_enabled = is_realtime_streaming_enabled()
        debug_log(f"speak(): Checking for active session, log_id={log_id}, realtime_enabled={realtime_enabled}")
        debug_log(f"speak(): has_active_session={has_active_session(log_id) if log_id else 'no log_id'}")
        if realtime_enabled and log_id and has_active_session(log_id):
            debug_log(f"speak(): Found active session, finalizing...")
            logger.info(f"Finalizing active realtime TTS session for log_id {log_id}")
            session = get_session(log_id)
            if session:
                await session.finish()
                await cleanup_session(log_id)
            debug_log(f"speak(): Session finalized and cleaned up")
            # Release lock before returning
            if log_id and log_id in _active_speak_locks and _active_speak_locks[log_id].locked():
                _active_speak_locks[log_id].release()
            return None
        debug_log(f"speak(): No active session, falling back to normal TTS")
        
        chunk_count = 0
        local_playback = _get_local_playback_enabled()
        try:
            agent_data = await service_manager.get_agent_data(context.agent_name)
            persona = agent_data["persona"]
            persona_voice = persona.get("voice_id", DEFAULT_VOICE_ID)
            
            # Check if voice_id looks like a file path (not a valid ElevenLabs voice ID)
            if persona_voice and (persona_voice.startswith('/') or persona_voice.startswith('.') or 
                                  persona_voice.endswith('.mp3') or persona_voice.endswith('.wav')):
                logger.warning(f"Persona voice_id '{persona_voice}' appears to be a file path, not an ElevenLabs voice ID. Using default voice.")
                voiceid = DEFAULT_VOICE_ID
            else:
                voiceid = persona_voice
        except Exception as e:
            logger.warning(f"Could not get agent persona voice_id, using default. Error: {str(e)}")
            voiceid = voice_id or DEFAULT_VOICE_ID

        total_sleep = 0
        chunk_length = 0
        
        # Check if audio is halted (we're in an interrupted state)
        # If so, return immediately - don't clear the halt flag
        if not local_playback:
            try:
                # Check halt status via service - returns True if halted
                is_halted = await service_manager.sip_is_audio_halted(context=context)
                if is_halted:
                    logger.info("SPEAK_DEBUG: Audio halted, skipping speak command")
                    return None  # Return silently - interrupt in progress
            except Exception as e:
                # If we can't check, proceed anyway
                logger.debug(f"Could not check halt status: {e}")
        
        # Use AudioPacer for proper timing when sending to SIP
        if not local_playback:
            pacer = AudioPacer(sample_rate=8000)  # ulaw is 8kHz
            
            # Track this pacer for interrupt support
            if log_id:
                _active_pacers[log_id] = pacer
            
            async def send_to_sip(chunk, timestamp=None, context=None):
                """Callback for AudioPacer to send chunks to SIP."""
                try:
                    result = await service_manager.sip_audio_out_chunk(chunk, timestamp=timestamp, context=context)
                    return result
                except Exception as e:
                    logger.error(f"Error sending to SIP: {e}")
                    return False
            
            # Start the pacer
            await pacer.start_pacing(send_to_sip, context)
        
        async for chunk in stream_tts(text=text, voice_id=voiceid, context=context):
            chunk_count += 1

            try:
                if not local_playback:
                    # Check if pacer was interrupted before adding more chunks
                    if pacer.interrupted:
                        logger.debug("SPEAK_DEBUG: Pacer interrupted, stopping chunk buffering")
                        break
                    
                    # Add chunk to pacer buffer (non-blocking)
                    await pacer.add_chunk(chunk)
                    chunk_length = len(chunk)
                    logger.debug(f"SPEAK_DEBUG: Buffered chunk {chunk_count}, size: {chunk_length} bytes")
            except Exception as e:
                logger.warning(f"Error sending audio chunk to SIP output: {str(e)}. Is SIP enabled?")
                await asyncio.sleep(1)
                return "Error sending audio chunk to SIP output: {str(e)}"

        if not local_playback:
            # Mark that all chunks have been added
            pacer.mark_finished()
            
            # Wait for pacer to finish sending all buffered audio
            if not pacer.interrupted:
                logger.debug(f"SPEAK_DEBUG: All {chunk_count} chunks buffered, waiting for pacer to finish...")
                await pacer.wait_until_done()
            
            # Stop the pacer
            await pacer.stop()
            
            # Remove from active pacers
            if log_id and log_id in _active_pacers:
                del _active_pacers[log_id]
            
            if pacer.interrupted:
                logger.info(f"SPEAK_DEBUG: Interrupted after {chunk_count} chunks, {pacer.bytes_sent} bytes sent")
                if chunk_count < 2:
                    return "SYSTEM: WARNING - Command interrupted!\n\n"
                return None
            else:
                logger.info(f"SPEAK_DEBUG: Completed {chunk_count} chunks, {pacer.bytes_sent} bytes sent")
        
        logger.info(f"Speech streaming completed: {len(text)} characters, {chunk_count} audio chunks")
        return None
        
    except Exception as e:
        logger.error(f"Error in speak command: {str(e)}")
        return None

    finally:
        # Always release the lock if we acquired it
        if log_id and log_id in _active_speak_locks:
            lock = _active_speak_locks[log_id]
            if lock.locked():
                lock.release()


@hook()
async def on_interrupt(context=None):
    """
    Handle interruption signal from the system.
    This is called when the user interrupts the AI (e.g., starts speaking during TTS).
    Cancels any active TTS streams for the current session.
    """
    log_id = None
    if context and hasattr(context, 'log_id'):
        log_id = context.log_id
    
    if not log_id:
        logger.debug("on_interrupt called without log_id, cannot cancel specific stream")
        return
    
    # Cancel active pacer for this session
    if log_id in _active_pacers:
        pacer = _active_pacers[log_id]
        logger.info(f"on_interrupt: Interrupting TTS stream for session {log_id}")
        pacer.interrupt()
    
    # Also cleanup any realtime streaming session
    if is_realtime_streaming_enabled() and has_active_session(log_id):
        logger.info(f"on_interrupt: Cleaning up realtime session for {log_id}")
        session = get_session(log_id)
        if session:
            await cleanup_session(log_id)
