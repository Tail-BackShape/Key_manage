from __future__ import annotations

from typing import Tuple

import requests


class DiscordNotifier:
    def __init__(self, webhook_url: str, timeout_seconds: int = 5) -> None:
        self._webhook_url = webhook_url
        self._timeout_seconds = timeout_seconds

    def send_operation(self, operator: str, action_label: str, timestamp: str) -> Tuple[bool, str]:
        if not self._webhook_url:
            return False, "DISCORD_WEBHOOK_URL が未設定のため通知をスキップしました"

        content = f"[{timestamp}] {operator}が {action_label} しました"
        payload = {"content": content}

        try:
            response = requests.post(self._webhook_url, json=payload, timeout=self._timeout_seconds)
            response.raise_for_status()
            return True, "通知を送信しました"
        except requests.RequestException as exc:
            return False, f"通知送信に失敗しました: {exc}"
