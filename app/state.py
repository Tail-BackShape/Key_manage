from __future__ import annotations

from enum import Enum
from threading import Condition, Lock


class LockState(str, Enum):
    LOCKED = "LOCKED"
    TEMP_LOCKED = "TEMP_LOCKED"


class StateStore:
    def __init__(self, initial_state: LockState = LockState.LOCKED) -> None:
        self._state = initial_state
        self._flow_phase = "phase-1"
        self._selected_user = ""
        self._pending_entry_action: str | None = None
        self._lock = Lock()
        self._condition = Condition(self._lock)
        self._version = 0

    def _touch(self) -> None:
        self._version += 1
        self._condition.notify_all()

    def _snapshot_locked(self) -> dict[str, str | int | None]:
        return {
            "state": self._state.value,
            "flowPhase": self._flow_phase,
            "selectedUser": self._selected_user,
            "pendingEntryAction": self._pending_entry_action,
            "version": self._version,
        }

    def get_state(self) -> LockState:
        with self._lock:
            return self._state

    def set_state(self, next_state: LockState) -> LockState:
        with self._lock:
            self._state = next_state
            self._touch()
            return self._state

    def get_flow_phase(self) -> str:
        with self._lock:
            return self._flow_phase

    def set_flow_phase(self, phase: str) -> str:
        with self._lock:
            self._flow_phase = phase
            self._touch()
            return self._flow_phase

    def get_selected_user(self) -> str:
        with self._lock:
            return self._selected_user

    def set_selected_user(self, user: str) -> str:
        with self._lock:
            self._selected_user = user
            self._touch()
            return self._selected_user

    def clear_selected_user(self) -> None:
        with self._lock:
            self._selected_user = ""
            self._touch()

    def get_pending_entry_action(self) -> str | None:
        with self._lock:
            return self._pending_entry_action

    def set_pending_entry_action(self, action: str | None) -> str | None:
        with self._lock:
            self._pending_entry_action = action
            self._touch()
            return self._pending_entry_action

    def get_snapshot(self) -> dict[str, str | int | None]:
        with self._lock:
            return self._snapshot_locked()

    def wait_for_update(self, last_version: int, timeout: float = 20.0) -> dict[str, str | int | None] | None:
        with self._condition:
            updated = self._condition.wait_for(lambda: self._version != last_version, timeout=timeout)
            if not updated:
                return None
            return self._snapshot_locked()
