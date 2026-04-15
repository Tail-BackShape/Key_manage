from __future__ import annotations

from enum import Enum
from threading import Lock


class LockState(str, Enum):
    LOCKED = "LOCKED"
    TEMP_LOCKED = "TEMP_LOCKED"


class StateStore:
    def __init__(self, initial_state: LockState = LockState.LOCKED) -> None:
        self._state = initial_state
        self._lock = Lock()

    def get_state(self) -> LockState:
        with self._lock:
            return self._state

    def set_state(self, next_state: LockState) -> LockState:
        with self._lock:
            self._state = next_state
            return self._state
