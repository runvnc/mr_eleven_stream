"""
Audio Pacer for ElevenLabs Streaming TTS

Handles buffering and pacing of audio chunks to match real-time playback speed.
Adapted from the OpenAI S2S AudioPacer.
"""
import asyncio
import time
import logging
from collections import deque
from typing import Callable, Optional, Any

logger = logging.getLogger(__name__)


class AudioPacer:
    """Paces audio chunks to real-time speed with small buffer.
    
    Buffers incoming audio chunks and sends them at the correct rate
    with precise timestamps for proper playback timing.
    """

    def __init__(self, sample_rate: int = 8000):
        """
        Args:
            sample_rate: Audio sample rate in Hz (default 8000 for ulaw telephony)
        """
        self.sample_rate = sample_rate
        self.buffer = deque()
        self.pacer_task: Optional[asyncio.Task] = None
        self.on_audio_chunk: Optional[Callable] = None
        self.context: Any = None
        self._running = False
        
        # Absolute timing for precise pacing
        self.start_time: Optional[float] = None
        self.bytes_sent = 0
        self.audio_start_time: Optional[float] = None
        self._finished_adding = False  # Flag to indicate no more chunks coming
        self._interrupted = False  # Flag to indicate interruption occurred

    async def add_chunk(self, audio_bytes: bytes):
        """Add audio chunk to buffer."""
        if self._running:
            self.buffer.append(audio_bytes)
            
            # Track when first audio chunk arrives
            if self.audio_start_time is None:
                self.audio_start_time = time.perf_counter()

    @property
    def interrupted(self) -> bool:
        """Check if pacer was interrupted."""
        return self._interrupted

    def _set_interrupted(self):
        """Mark pacer as interrupted."""
        self._interrupted = True

    def mark_finished(self):
        """Mark that all chunks have been added."""
        self._finished_adding = True

    async def clear(self):
        """Clear buffer and reset state for interruption."""
        self.buffer.clear()
        self.audio_start_time = None
        self.bytes_sent = 0
        self.start_time = time.perf_counter()
        self._interrupted = False
        self._finished_adding = False
        logger.debug("AudioPacer cleared and reset")

    async def start_pacing(self, on_audio_chunk: Callable, context: Any):
        """Start real-time pacing task.
        
        Args:
            on_audio_chunk: Async callback function(chunk, timestamp, context)
            context: Context to pass to callback
        """
        self.on_audio_chunk = on_audio_chunk
        self.context = context
        self._running = True
        self._finished_adding = False
        self._interrupted = False
        
        # Record absolute start time
        self.start_time = time.perf_counter()
        self.bytes_sent = 0
        self.audio_start_time = None
        
        self.pacer_task = asyncio.create_task(self._pace_loop())

    async def _pace_loop(self):
        """Send buffered chunks at real-time intervals using absolute timing."""
        while self._running:
            if len(self.buffer) > 0:
                chunk = self.buffer.popleft()
                
                # Calculate timestamp for this chunk (DISABLED - causing timing issues)
                if self.audio_start_time:
                     chunk_timestamp = self.audio_start_time + (self.bytes_sent / self.sample_rate)
                else:
                     chunk_timestamp = None
                #chunk_timestamp = None
                
                try:
                    result = await self.on_audio_chunk(chunk, timestamp=chunk_timestamp, context=self.context)
                    if result is False:
                        # Callback requested stop
                        logger.debug("AudioPacer: callback requested stop")
                        self._set_interrupted()
                        break
                except Exception as e:
                    logger.error(f"AudioPacer: error in callback: {e}")
                    break
                
                # Update bytes sent counter
                self.bytes_sent += len(chunk)
                
                # Calculate target time based on total bytes sent
                # Use audio_start_time (when first audio arrived) for accurate pacing
                base_time = self.audio_start_time if self.audio_start_time else self.start_time
                target_time = base_time + (self.bytes_sent / self.sample_rate)
                
                # Calculate how long to sleep to hit target time
                current_time = time.perf_counter()
                sleep_duration = target_time - current_time
                
                # Sleep if we're ahead of schedule
                if sleep_duration > 0:
                    await asyncio.sleep(sleep_duration)
                # If behind schedule, don't sleep - catch up
                
            else:
                # No data in buffer
                if self._finished_adding:
                    # All chunks processed, exit loop
                    break
                # Wait for more data
                await asyncio.sleep(0.005)
        
        logger.debug(f"AudioPacer: finished, sent {self.bytes_sent} bytes")

    async def stop(self):
        """Stop pacing and clear buffer."""
        self._running = False
        if self.pacer_task:
            self.pacer_task.cancel()
            try:
                await self.pacer_task
            except asyncio.CancelledError:
                pass
        self.buffer.clear()

    async def wait_until_done(self):
        """Wait for all buffered audio to be sent."""
        if self.pacer_task:
            try:
                await self.pacer_task
            except asyncio.CancelledError:
                pass
