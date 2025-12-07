"""Realtime streaming TTS using ElevenLabs' streaming input API.

This module provides the ability to stream text to ElevenLabs as it comes in
from the LLM, rather than waiting for complete sentences.
"""

import os
import asyncio
import logging
import threading
import queue
from typing import Dict, Any, Optional, Iterator
from dataclasses import dataclass, field
from elevenlabs.client import ElevenLabs
from elevenlabs.types import VoiceSettings
from lib.pipelines.pipe import pipe
from .audio_pacer import AudioPacer
from lib.providers.services import service_manager

logger = logging.getLogger(__name__)

# Debug log file
DEBUG_LOG_FILE = "/tmp/tts_debug.log"

def debug_log(msg):
    """Write debug message to dedicated log file."""
    import datetime
    with open(DEBUG_LOG_FILE, 'a') as f:
        f.write(f"{datetime.datetime.now().isoformat()} | {msg}\n")

# Default configuration (same as mod.py)
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George voice
DEFAULT_MODEL_ID = "eleven_flash_v2_5"  # Ultra-low latency for real-time
DEFAULT_OUTPUT_FORMAT = "ulaw_8000"  # Standard for SIP/telephony

# Sentinel value to signal end of text stream
_END_OF_TEXT = object()


class RealtimeSpeakSession:
    """Manages a realtime streaming TTS session.
    
    Tracks text deltas and streams them to ElevenLabs as they arrive,
    while simultaneously streaming audio output to SIP or local playback.
    
    Uses thread-safe queues to bridge async code with ElevenLabs' synchronous API.
    """
    
    def __init__(self, context: Any):
        self.context = context
        self.voice_id = DEFAULT_VOICE_ID
        self.model_id = DEFAULT_MODEL_ID
        self.output_format = DEFAULT_OUTPUT_FORMAT
        
        # State tracking
        self.previous_text = ""
        self.is_active = False
        self.is_finished = False
        
        # Thread-safe queue for text chunks (sync producer from async, sync consumer in thread)
        self._text_queue: queue.Queue = queue.Queue()
        
        # Thread-safe queue for audio chunks (sync producer in thread, async consumer)
        self._audio_queue: queue.Queue = queue.Queue()
        
        # Threading
        self._tts_thread: Optional[threading.Thread] = None
        self._audio_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Audio pacer for proper timing
        self._pacer: Optional[AudioPacer] = None
        
        # ElevenLabs client
        api_key = os.getenv('ELEVENLABS_API_KEY')
        if not api_key:
            raise ValueError("ElevenLabs API key not found")
        self._client = ElevenLabs(api_key=api_key)
    
    def _text_iterator(self) -> Iterator[str]:
        """Synchronous iterator that yields text chunks from the thread-safe queue.
        
        This runs in the TTS thread and blocks waiting for text.
        """
        debug_log("_text_iterator: Starting to consume text queue")
        while True:
            try:
                # Block with timeout to allow checking for shutdown
                text = self._text_queue.get(timeout=0.1)
                if text is _END_OF_TEXT:
                    debug_log("_text_iterator: Received END signal")
                    logger.debug("Text iterator received end signal")
                    break
                if text:
                    debug_log(f"_text_iterator: Yielding text: '{text}'")
                    logger.debug(f"Text iterator yielding: {text[:50]}...")
                    yield text
            except queue.Empty:
                # Check if we should stop
                if self.is_finished:
                    break
                continue
    
    def _run_tts_thread(self, output_format: str, voice_settings: VoiceSettings):
        """Run the TTS conversion in a separate thread.
        
        This thread consumes text from _text_queue and produces audio to _audio_queue.
        """
        try:
            debug_log(f"_run_tts_thread: Starting TTS with voice {self.voice_id}")
            logger.info(f"TTS thread started with voice {self.voice_id}")
            
            # Get the audio iterator from ElevenLabs
            audio_iterator = self._client.text_to_speech.convert_realtime(
                voice_id=self.voice_id,
                text=self._text_iterator(),
                model_id=self.model_id,
                output_format=output_format,
                voice_settings=voice_settings
            )
            
            # Stream audio chunks to the audio queue
            chunk_count = 0
            for audio_chunk in audio_iterator:
                if isinstance(audio_chunk, bytes):
                    chunk_count += 1
                    debug_log(f"_run_tts_thread: Got audio chunk {chunk_count}, size={len(audio_chunk)}")
                    logger.debug(f"TTS thread produced audio chunk {chunk_count}, size: {len(audio_chunk)}")
                    self._audio_queue.put(audio_chunk)
            
            debug_log(f"_run_tts_thread: Completed, total chunks={chunk_count}")
            logger.info(f"TTS thread completed. Total chunks: {chunk_count}")
            
        except Exception as e:
            debug_log(f"_run_tts_thread: ERROR - {e}")
            logger.error(f"Error in TTS thread: {e}")
        finally:
            # Signal end of audio
            self._audio_queue.put(_END_OF_TEXT)
    
    async def _process_audio(self):
        """Async task that consumes audio from the queue and sends to SIP/playback."""
        try:
            debug_log("_process_audio: Starting audio processor")
            # Check if SIP output is available
            sip_available = service_manager.functions.get('sip_audio_out_chunk') is not None
            debug_log(f"_process_audio: SIP available={sip_available}")
            
            if sip_available:
                # Set up AudioPacer for proper timing
                self._pacer = AudioPacer(sample_rate=8000)  # ulaw is 8kHz
                
                async def send_to_sip(chunk, timestamp=None, context=None):
                    """Callback for AudioPacer to send chunks to SIP."""
                    result = await service_manager.sip_audio_out_chunk(chunk, timestamp=timestamp, context=context)
                    debug_log(f"send_to_sip: Sent {len(chunk)} bytes to SIP, result={result}")
                    return result
                
                await self._pacer.start_pacing(send_to_sip, self.context)
                debug_log("_process_audio: AudioPacer started")
            
            chunk_count = 0
            while True:
                # Check queue in a non-blocking way with small sleep
                try:
                    audio_chunk = self._audio_queue.get_nowait()
                except queue.Empty:
                    # Don't print this - too noisy
                    await asyncio.sleep(0.01)
                    continue
                
                if audio_chunk is _END_OF_TEXT:
                    debug_log("_process_audio: Received END signal")
                    logger.debug("Audio processor received end signal")
                    break
                
                if isinstance(audio_chunk, bytes):
                    chunk_count += 1
                    debug_log(f"_process_audio: Processing chunk {chunk_count}, size={len(audio_chunk)}")
                    logger.debug(f"Processing audio chunk {chunk_count}, size: {len(audio_chunk)}")
                    
                    if sip_available:
                        # Add to pacer buffer - it will handle timing and timestamps
                        await self._pacer.add_chunk(audio_chunk)
                        debug_log(f"_process_audio: Added chunk {chunk_count} to pacer, pacer buffer size={len(self._pacer.buffer)}")
                        
                        # Check if pacer was interrupted
                        if self._pacer.interrupted:
                            logger.debug("Pacer interrupted, stopping audio processing")
                            break
                    # TODO: Handle local playback if needed
            
            logger.info(f"Audio processor completed. Total chunks processed: {chunk_count}")
            
        except Exception as e:
            logger.error(f"Error in audio processor: {e}")
    
    async def _finalize_pacer(self):
        """Finalize the audio pacer - mark finished and wait for completion."""
        debug_log("_finalize_pacer: Starting pacer finalization")
        if self._pacer:
            self._pacer.mark_finished()
            debug_log(f"_finalize_pacer: Pacer marked finished, buffer size={len(self._pacer.buffer)}, bytes_sent={self._pacer.bytes_sent}")
            
            if not self._pacer.interrupted:
                logger.debug("Waiting for pacer to finish sending buffered audio...")
                debug_log("_finalize_pacer: Waiting for pacer to drain...")
                await self._pacer.wait_until_done()
            
            await self._pacer.stop()
            debug_log(f"_finalize_pacer: Pacer stopped, total bytes_sent={self._pacer.bytes_sent}")
    
    async def start(self):
        """Start the realtime TTS session."""
        if self.is_active:
            debug_log("RealtimeSpeakSession.start: Session already active")
            logger.warning("Session already active")
            return
        
        self.is_active = True
        self.is_finished = False
        self.previous_text = ""
        self._loop = asyncio.get_event_loop()
        
        # Try to get voice_id from agent persona
        debug_log("RealtimeSpeakSession.start: Getting voice_id from persona")
        try:
            agent_data = await service_manager.get_agent_data(self.context.agent_name)
            persona = agent_data.get("persona", {})
            self.voice_id = persona.get("voice_id", DEFAULT_VOICE_ID)
        except Exception as e:
            logger.warning(f"Could not get agent persona voice_id: {e}")
        
        # Determine output format
        sip_available = service_manager.functions.get('sip_audio_out_chunk') is not None
        output_format = "ulaw_8000" if sip_available else "mp3_22050_32"
        
        # Get voice settings
        stability = float(os.environ.get('ELEVENLABS_STABILITY_DEFAULT', 0.5))
        similarity_boost = float(os.environ.get('ELEVENLABS_SIMILARITY_BOOST_DEFAULT', 0.75))
        voice_settings = VoiceSettings(
            stability=stability,
            similarity_boost=similarity_boost
        )
        
        # Start the TTS thread
        self._tts_thread = threading.Thread(
            target=self._run_tts_thread,
            args=(output_format, voice_settings),
            daemon=True
        )
        self._tts_thread.start()
        
        debug_log(f"RealtimeSpeakSession.start: Started TTS thread and audio task, voice={self.voice_id}")
        # Start the audio processing task
        self._audio_task = asyncio.create_task(self._process_audio())
        
        logger.info(f"Started realtime TTS session with voice {self.voice_id}")
    
    async def feed_text(self, delta: str):
        """Feed a text delta to the TTS stream."""
        if not self.is_active:
            logger.warning("Cannot feed text to inactive session")
            debug_log("feed_text: Session not active!")
            return
        
        if delta:
            self._text_queue.put(delta)
            logger.debug(f"Fed text delta: {delta[:50] if len(delta) > 50 else delta}")
    
    async def finish(self):
        """Signal that no more text will be added and wait for completion."""
        logger.info("Finishing realtime TTS session...")
        self.is_finished = True
        
        # Signal end of text
        self._text_queue.put(_END_OF_TEXT)
        
        # Wait for TTS thread to complete (non-blocking to allow async tasks to run)
        loop = asyncio.get_event_loop()
        # Wait for TTS thread to complete
        if self._tts_thread and self._tts_thread.is_alive():
            # Use run_in_executor to avoid blocking the event loop
            await loop.run_in_executor(None, lambda: self._tts_thread.join(timeout=30.0))
            if self._tts_thread.is_alive():
                logger.warning("TTS thread did not complete in time")
        
        # Wait for audio task to complete
        if self._audio_task:
            try:
                await asyncio.wait_for(self._audio_task, timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning("Audio task timed out")
                self._audio_task.cancel()
            except Exception as e:
                logger.error(f"Error waiting for audio task: {e}")
        
        # NOW finalize the pacer (wait for all buffered audio to be sent)
        await self._finalize_pacer()
        
        self.is_active = False
        logger.info("Realtime TTS session finished")
    
    async def cancel(self):
        """Cancel the session immediately."""
        logger.info("Cancelling realtime TTS session...")
        self.is_finished = True
        self.is_active = False
        
        # Signal end of text to unblock the thread
        self._text_queue.put(_END_OF_TEXT)
        
        # Wait for TTS thread to complete (non-blocking to allow async tasks to run)
        loop = asyncio.get_event_loop()
        # Stop pacer immediately
        if self._pacer:
            await self._pacer.stop()
        
        # Cancel audio task
        if self._audio_task:
            self._audio_task.cancel()
            try:
                await self._audio_task
            except asyncio.CancelledError:
                pass
        
        # Wait briefly for thread
        if self._tts_thread and self._tts_thread.is_alive():
            loop = asyncio.get_event_loop(); await loop.run_in_executor(None, lambda: self._tts_thread.join(timeout=2.0))
        
        logger.info("Realtime TTS session cancelled")


# Global registry of active sessions per log_id
_realtime_sessions: Dict[str, RealtimeSpeakSession] = {}


def get_session(log_id: str) -> Optional[RealtimeSpeakSession]:
    """Get the active session for a log_id, if any."""
    return _realtime_sessions.get(log_id)


def has_active_session(log_id: str) -> bool:
    """Check if there's an active realtime session for this log_id."""
    session = _realtime_sessions.get(log_id)
    return session is not None and session.is_active


async def cleanup_session(log_id: str):
    """Clean up and remove a session."""
    if log_id in _realtime_sessions:
        session = _realtime_sessions[log_id]
        if session.is_active:
            await session.cancel()
        del _realtime_sessions[log_id]


@pipe(name='partial_command', priority=10)
async def handle_speak_partial(data: dict, context=None) -> dict:
    """Intercepts partial_command calls to detect speak commands
    and stream text deltas to ElevenLabs in realtime.
    """
    debug_log(f"handle_speak_partial: data={data}")
    command = data.get('command')
    
    # Only handle speak commands
    if command != 'speak':
        return data
    
    log_id = context.log_id if context else None
    if not log_id:
        debug_log("handle_speak_partial: No log_id in context")
        logger.warning("No log_id in context, cannot track session")
        return data
    
    params = data.get('params', {})
    new_text = params.get('text', '')
    
    if not new_text:
        return data
    
    # Get or create session for this log_id
    debug_log(f"handle_speak_partial: log_id={log_id}, new_text length={len(new_text)}")
    if log_id not in _realtime_sessions:
        debug_log(f"handle_speak_partial: Creating new session for log_id {log_id}")
        session = RealtimeSpeakSession(context=context)
        _realtime_sessions[log_id] = session
        await session.start()
    
    session = _realtime_sessions[log_id]
    
    # Calculate delta (new text since last update)
    debug_log(f"handle_speak_partial: previous_text length={len(session.previous_text)}, new_text length={len(new_text)}")
    if len(new_text) > len(session.previous_text):
        delta = new_text[len(session.previous_text):]
        if delta:
            debug_log(f"handle_speak_partial: Feeding delta: '{delta}'")
            logger.debug(f"Text delta for speak: '{delta}'")
            await session.feed_text(delta)
            session.previous_text = new_text
    
    return data
