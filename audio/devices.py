"""Audio input device enumeration and selection.

Wraps ``sounddevice`` (PortAudio) so the rest of the app depends on a small,
typed interface instead of the raw PortAudio device-info dictionaries, and
so device enumeration can be unit-tested by injecting a fake ``query_func``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class NoAudioBackendError(Exception):
    """Raised when the PortAudio backend (sounddevice) is unavailable."""


@dataclass(frozen=True)
class InputDevice:
    index: int
    name: str
    host_api_name: str
    max_input_channels: int
    default_sample_rate: float
    is_default: bool


def _sounddevice_query() -> tuple[list[dict], list[dict], int | None]:
    """Live query against the installed PortAudio backend.

    Isolated into its own function so tests can monkeypatch/replace it
    without needing real audio hardware or the ``sounddevice`` package.
    """
    try:
        import sounddevice as sd
    except OSError as exc:  # PortAudio native lib missing
        raise NoAudioBackendError(f"PortAudio backend unavailable: {exc}") from exc

    devices = list(sd.query_devices())
    host_apis = list(sd.query_hostapis())
    try:
        default_input = sd.default.device[0]
    except Exception:  # noqa: BLE001 - default device lookup is best-effort
        default_input = None
    return devices, host_apis, default_input


class DeviceManager:
    """Enumerates and tracks the selected audio input device."""

    def __init__(self, query_func: Callable[[], tuple[list[dict], list[dict], int | None]] | None = None):
        self._query_func = query_func or _sounddevice_query
        self._selected_index: Optional[int] = None

    def list_input_devices(self) -> List[InputDevice]:
        devices, host_apis, default_input = self._query_func()
        result: List[InputDevice] = []
        for idx, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) <= 0:
                continue
            host_api_index = dev.get("hostapi", 0)
            host_api_name = (
                host_apis[host_api_index]["name"]
                if 0 <= host_api_index < len(host_apis)
                else "unknown"
            )
            result.append(
                InputDevice(
                    index=idx,
                    name=dev.get("name", f"Device {idx}"),
                    host_api_name=host_api_name,
                    max_input_channels=dev.get("max_input_channels", 0),
                    default_sample_rate=float(dev.get("default_samplerate", 44100.0)),
                    is_default=(idx == default_input),
                )
            )
        return result

    def select_device(self, index: int) -> None:
        self._selected_index = index
        logger.info("Selected audio input device index=%d", index)

    def selected_device_index(self) -> Optional[int]:
        return self._selected_index

    def get_default_input_index(self) -> Optional[int]:
        devices = self.list_input_devices()
        for d in devices:
            if d.is_default:
                return d.index
        return devices[0].index if devices else None
