from __future__ import annotations

from datetime import datetime
from http import HTTPStatus

from flask import Blueprint, Flask, jsonify, render_template, request

from .config import AppConfig
from .notifier import DiscordNotifier
from .state import LockState, StateStore

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
    "unlock": "phase-2",
    "temp_lock": "phase-2",
    "home": "phase-1",
}


def _build_state_payload(state_store: StateStore) -> dict[str, object]:
    current = state_store.get_state()
    return {
        "state": current.value,
        "show_home_button": current == LockState.TEMP_LOCKED,
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

    @api.post("/api/action")
    def perform_action() -> tuple:
        payload = request.get_json(silent=True) or {}
        user = str(payload.get("user", "")).strip()
        action = str(payload.get("action", "")).strip()

        if not user:
            return jsonify({"error": "user は必須です"}), HTTPStatus.BAD_REQUEST

        if action not in ACTION_LABELS:
            return jsonify({"error": "action が不正です"}), HTTPStatus.BAD_REQUEST

        next_state = STATE_TRANSITIONS[action]
        state_store.set_state(next_state)

        timestamp = datetime.now().strftime(config.time_format)
        action_label = ACTION_LABELS[action]
        sent, detail = notifier.send_operation(operator=user, action_label=action_label, timestamp=timestamp)

        response_payload = {
            "timestamp": timestamp,
            "user": user,
            "action": action,
            "actionLabel": action_label,
            "nextPhase": NEXT_PHASE_BY_ACTION[action],
            "notificationStatus": "sent" if sent else "failed",
            "notificationDetail": detail,
            **_build_state_payload(state_store),
        }

        status_code = HTTPStatus.OK if sent else HTTPStatus.ACCEPTED
        return jsonify(response_payload), status_code

    app.register_blueprint(api)
