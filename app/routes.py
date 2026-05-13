from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
import json

from flask import Blueprint, Flask, Response, jsonify, render_template, request, stream_with_context

from .config import AppConfig
from .notifier import DiscordNotifier
from .state import LockState, StateStore

PHASE_INDEX = "phase-1"
PHASE_USER_SELECT = "phase-2"
PHASE_ACTION_SELECT = "phase-3"

ENTRY_ACTIONS = {"unlock", "home", "temp_lock"}

ACTION_LABELS = {
    "unlock": "開錠",
    "temp_lock": "一時施錠",
    "home": "施錠・帰宅",
}

STATE_TRANSITIONS = {
    "unlock": LockState.LOCKED,
    "temp_lock": LockState.TEMP_LOCKED,
    "home": LockState.LOCKED,
}

NEXT_PHASE_BY_ACTION = {
    "unlock": PHASE_ACTION_SELECT,
    "temp_lock": PHASE_USER_SELECT,
    "home": PHASE_INDEX,
}


def _build_payload_from_snapshot(snapshot: dict[str, str | int | None]) -> dict[str, object]:
    current = LockState(str(snapshot["state"]))
    return {
        "state": current.value,
        "show_home_button": current == LockState.TEMP_LOCKED,
        "currentPhase": snapshot["flowPhase"],
        "selectedUser": snapshot["selectedUser"],
        "pendingEntryAction": snapshot["pendingEntryAction"],
        "version": snapshot["version"],
    }


def _build_state_payload(state_store: StateStore) -> dict[str, object]:
    return _build_payload_from_snapshot(state_store.get_snapshot())


def _format_sse_event(event_name: str, event_id: int, payload: dict[str, object]) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"id: {event_id}\nevent: {event_name}\ndata: {data}\n\n"


def _notify_action(
    *,
    notifier: DiscordNotifier,
    config: AppConfig,
    user: str,
    action: str,
) -> tuple[str, str, bool, str]:
    timestamp = datetime.now().strftime(config.time_format)
    action_label = ACTION_LABELS[action]
    sent, detail = notifier.send_operation(operator=user, action_label=action_label, timestamp=timestamp)
    return timestamp, action_label, sent, detail


def _build_action_log(
    *,
    timestamp: str,
    user: str,
    action: str,
    action_label: str,
    sent: bool,
    detail: str,
) -> dict[str, object]:
    return {
        "timestamp": timestamp,
        "user": user,
        "action": action,
        "actionLabel": action_label,
        "notificationStatus": "sent" if sent else "failed",
        "notificationDetail": detail,
    }


def register_routes(
    app: Flask,
    state_store: StateStore,
    notifier: DiscordNotifier,
    config: AppConfig,
) -> None:
    api = Blueprint("api", __name__)

    @api.get("/")
    def index() -> str:
        return render_template("index.html")

    @api.get("/api/bootstrap")
    def bootstrap() -> tuple:
        payload = {
            **_build_state_payload(state_store),
            "users": config.users,
        }
        return jsonify(payload), HTTPStatus.OK

    @api.get("/api/state")
    def get_state() -> tuple:
        return jsonify(_build_state_payload(state_store)), HTTPStatus.OK

    @api.get("/api/events")
    def events() -> Response:
        def event_stream() -> object:
            snapshot = state_store.get_snapshot()
            payload = _build_payload_from_snapshot(snapshot)
            version = int(payload["version"])
            yield _format_sse_event("state", version, payload)

            while True:
                updated_snapshot = state_store.wait_for_update(version, timeout=20.0)
                if updated_snapshot is None:
                    yield ": keep-alive\n\n"
                    continue

                payload = _build_payload_from_snapshot(updated_snapshot)
                version = int(payload["version"])
                yield _format_sse_event("state", version, payload)

        response = Response(stream_with_context(event_stream()), mimetype="text/event-stream")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Accel-Buffering"] = "no"
        return response

    @api.post("/api/flow/start")
    def start_flow() -> tuple:
        payload = request.get_json(silent=True) or {}
        entry_action = str(payload.get("entryAction", "")).strip()

        if entry_action not in ENTRY_ACTIONS:
            return jsonify({"error": "entryAction が不正です"}), HTTPStatus.BAD_REQUEST

        state_store.set_pending_entry_action(entry_action)
        if entry_action in {"unlock", "home"}:
            state_store.clear_selected_user()
        state_store.set_flow_phase(PHASE_USER_SELECT)

        return jsonify(_build_state_payload(state_store)), HTTPStatus.OK

    @api.post("/api/flow/select-user")
    def select_user() -> tuple:
        payload = request.get_json(silent=True) or {}
        user = str(payload.get("user", "")).strip()

        if not user:
            return jsonify({"error": "user は必須です"}), HTTPStatus.BAD_REQUEST

        if user not in config.users:
            return jsonify({"error": "user が不正です"}), HTTPStatus.BAD_REQUEST

        pending_entry_action = state_store.get_pending_entry_action()
        response_payload: dict[str, object]

        if pending_entry_action == "unlock":
            state_store.set_selected_user(user)
            state_store.set_flow_phase(PHASE_ACTION_SELECT)
            timestamp, action_label, sent, detail = _notify_action(
                notifier=notifier,
                config=config,
                user=user,
                action="unlock",
            )
            state_store.set_pending_entry_action(None)
            response_payload = {
                **_build_state_payload(state_store),
                "entryActionLog": _build_action_log(
                    timestamp=timestamp,
                    user=user,
                    action="unlock",
                    action_label=action_label,
                    sent=sent,
                    detail=detail,
                ),
            }
        elif pending_entry_action == "temp_lock":
            state_store.set_selected_user(user)
            state_store.set_state(LockState.TEMP_LOCKED)
            state_store.set_flow_phase(PHASE_INDEX)
            timestamp, action_label, sent, detail = _notify_action(
                notifier=notifier,
                config=config,
                user=user,
                action="temp_lock",
            )
            state_store.clear_selected_user()
            state_store.set_pending_entry_action(None)
            response_payload = {
                **_build_state_payload(state_store),
                "entryActionLog": _build_action_log(
                    timestamp=timestamp,
                    user=user,
                    action="temp_lock",
                    action_label=action_label,
                    sent=sent,
                    detail=detail,
                ),
            }
        elif pending_entry_action == "home":
            state_store.set_selected_user(user)
            state_store.set_state(LockState.LOCKED)
            state_store.set_flow_phase(PHASE_INDEX)
            timestamp, action_label, sent, detail = _notify_action(
                notifier=notifier,
                config=config,
                user=user,
                action="home",
            )
            state_store.clear_selected_user()
            state_store.set_pending_entry_action(None)
            response_payload = {
                **_build_state_payload(state_store),
                "entryActionLog": _build_action_log(
                    timestamp=timestamp,
                    user=user,
                    action="home",
                    action_label=action_label,
                    sent=sent,
                    detail=detail,
                ),
            }
        else:
            state_store.set_selected_user(user)
            state_store.set_flow_phase(PHASE_ACTION_SELECT)
            state_store.set_pending_entry_action(None)
            response_payload = {
                **_build_state_payload(state_store),
            }

        if pending_entry_action == "unlock":
            response_payload.update(
                {
                    "unlockLog": {
                        **response_payload["entryActionLog"],
                    }
                }
            )

        return jsonify(response_payload), HTTPStatus.OK

    @api.post("/api/flow/reset")
    def reset_flow() -> tuple:
        state_store.set_flow_phase(PHASE_INDEX)
        state_store.clear_selected_user()
        state_store.set_pending_entry_action(None)
        return jsonify(_build_state_payload(state_store)), HTTPStatus.OK

    @api.post("/api/flow/back")
    def back_from_user_select() -> tuple:
        pending_entry_action = state_store.get_pending_entry_action()

        if pending_entry_action in {"unlock", "home"}:
            state_store.set_flow_phase(PHASE_INDEX)
            state_store.clear_selected_user()
        else:
            state_store.set_flow_phase(PHASE_ACTION_SELECT)

        state_store.set_pending_entry_action(None)
        return jsonify(_build_state_payload(state_store)), HTTPStatus.OK

    @api.post("/api/flow/change-user")
    def change_user() -> tuple:
        state_store.clear_selected_user()
        state_store.set_flow_phase(PHASE_USER_SELECT)
        return jsonify(_build_state_payload(state_store)), HTTPStatus.OK

    @api.post("/api/action")
    def perform_action() -> tuple:
        payload = request.get_json(silent=True) or {}
        user = str(payload.get("user", "")).strip() or state_store.get_selected_user().strip()
        action = str(payload.get("action", "")).strip()

        if not user:
            return jsonify({"error": "user は必須です"}), HTTPStatus.BAD_REQUEST

        if action not in ACTION_LABELS:
            return jsonify({"error": "action が不正です"}), HTTPStatus.BAD_REQUEST

        next_state = STATE_TRANSITIONS[action]
        state_store.set_state(next_state)
        next_phase = NEXT_PHASE_BY_ACTION[action]
        state_store.set_flow_phase(next_phase)
        state_store.set_pending_entry_action(None)

        if next_phase == PHASE_INDEX:
            state_store.clear_selected_user()
        else:
            state_store.set_selected_user(user)

        timestamp, action_label, sent, detail = _notify_action(
            notifier=notifier,
            config=config,
            user=user,
            action=action,
        )

        response_payload = {
            "timestamp": timestamp,
            "user": user,
            "action": action,
            "actionLabel": action_label,
            "nextPhase": next_phase,
            "notificationStatus": "sent" if sent else "failed",
            "notificationDetail": detail,
            **_build_state_payload(state_store),
        }

        status_code = HTTPStatus.OK if sent else HTTPStatus.ACCEPTED
        return jsonify(response_payload), status_code

    app.register_blueprint(api)
