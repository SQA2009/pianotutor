"""Low-latency audio capture.

``AudioStream`` opens a PortAudio input stream via ``sounddevice`` and, on
its dedicated callback thread, does the absolute minimum: copy the incoming
block into the ring buffer and publish a lightweight ``AudioFrameReady``
notification. No DSP, no logging beyond error paths, no locks other than the
ring buffer's own short-held one — anything heavier belongs in the
recognition worker thread, which consumes frames asynchronously.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

import numpy as np

from pianotutor.audio.ring_buffer import RingBuffer
from pianotutor.services.clock import Clock
from pianotutor.services.event_bus import EventBus
from pianotutor.services.event_types import Topic

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioFrameReady:
    """The ``AudioFrameReady`` contract from Audio -> Recognition."""

    timestamp_ms: float
    frame_id: int
    samples: np.ndarray
    sample_rate: int


class AudioStreamError(Exception):
    """Raised when the audio stream cannot be opened or fails while running."""


class AudioStream:
    """Owns the PortAudio input stream and ring buffer for one input device."""

    def __init__(
        self,
        device_index: int,
        sample_rate: int,
        block_size: int,
        channels: int,
        ring_buffer: RingBuffer,
        event_bus: EventBus,
        clock: Clock,
    ):
        self._device_index = device_index
        self._sample_rate = sample_rate
        self._block_size = block_size
        self._channels = channels
        self._ring_buffer = ring_buffer
        self._event_bus = event_bus
        self._clock = clock

        self._stream = None
        self._frame_id = 0
        self._running = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    @property
    def device_index(self) -> int:
        return self._device_index

    def start(self) -> None:
        try:
            import sounddevice as sd
        except OSError as exc:
            raise AudioStreamError(f"PortAudio backend unavailable: {exc}") from exc

        try:
            self._stream = sd.InputStream(
                device=self._device_index,
                samplerate=self._sample_rate,
                blocksize=self._block_size,
                channels=self._channels,
                dtype="float32",
                callback=self._on_audio_block,
            )
            self._stream.start()
        except Exception as exc:  # noqa: BLE001 - surface any backend error uniformly
            self._event_bus.publish(Topic.AUDIO_STREAM_ERROR, {"error": str(exc)})
            raise AudioStreamError(f"Failed to start audio stream: {exc}") from exc

        self._running.set()
        self._event_bus.publish(
            Topic.AUDIO_STREAM_STARTED,
            {"device_index": self._device_index, "sample_rate": self._sample_rate},
        )
        logger.info(
            "Audio stream started: device=%d rate=%d block=%d channels=%d",
            self._device_index, self._sample_rate, self._block_size, self._channels,
        )

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:  # noqa: BLE001 - best-effort shutdown
                logger.exception("Error while stopping audio stream")
            finally:
                self._stream = None
        self._running.clear()
        self._event_bus.publish(Topic.AUDIO_STREAM_STOPPED, None)
        logger.info("Audio stream stopped")

    # --- Callback thread. Must never block or raise. -----------------------
    def _on_audio_block(self, indata, frames, time_info, status) -> None:
        if status:
            # Overflows/underflows land here; log without blocking materially.
            logger.warning("Audio stream status flag set: %s", status)

        try:
            mono = indata[:, 0] if indata.ndim > 1 else indata
            block = np.array(mono, dtype=np.float32, copy=True)
            self._ring_buffer.write(block)

            self._frame_id += 1
            frame = AudioFrameReady(
                timestamp_ms=self._clock.now_ms(),
                frame_id=self._frame_id,
                samples=block,
                sample_rate=self._sample_rate,
            )
            self._event_bus.publish(Topic.AUDIO_FRAME_READY, frame)
        except Exception:  # noqa: BLE001 - the callback thread must never propagate
            logger.exception("Error in audio callback; dropping this block")
