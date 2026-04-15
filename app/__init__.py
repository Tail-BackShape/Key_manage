from __future__ import annotations

from dotenv import load_dotenv
from flask import Flask

from .config import AppConfig
from .notifier import DiscordNotifier
from .routes import register_routes
from .state import LockState, StateStore


def create_app() -> Flask:
    load_dotenv()
    config = AppConfig.from_env()

    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
        static_url_path="/static",
    )
    app.config["APP_CONFIG"] = config

    state_store = StateStore(initial_state=LockState.LOCKED)
    notifier = DiscordNotifier(config.discord_webhook_url)
    register_routes(app, state_store, notifier, config)

    return app
