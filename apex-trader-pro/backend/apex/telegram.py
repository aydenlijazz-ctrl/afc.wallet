"""Telegram Bot API sender."""
from __future__ import annotations

import logging

import httpx

from . import config

log = logging.getLogger(__name__)


class Telegram:
    def __init__(self, token: str | None = None, chat_id: str | None = None, http: httpx.Client | None = None):
        self.token = token if token is not None else config.secret("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id if chat_id is not None else config.secret("TELEGRAM_CHAT_ID")
        self.http = http or httpx.Client(timeout=10.0)

    def call(self, method: str, payload: dict) -> dict | None:
        if not self.token:
            return None
        try:
            r = self.http.post(f"https://api.telegram.org/bot{self.token}/{method}", json=payload)
            return r.json()
        except httpx.HTTPError as exc:
            log.warning("telegram %s failed: %s", method, exc)
            return None

    def send(self, text: str, keyboard: list[list[dict]] | None = None, chat_id: str | None = None) -> dict | None:
        payload: dict = {"chat_id": chat_id or self.chat_id, "text": text, "parse_mode": "HTML",
                         "disable_web_page_preview": True}
        if keyboard:
            payload["reply_markup"] = {"inline_keyboard": keyboard}
        return self.call("sendMessage", payload)

    def edit(self, chat_id, message_id, text: str, keyboard: list[list[dict]] | None = None) -> dict | None:
        payload: dict = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
        if keyboard:
            payload["reply_markup"] = {"inline_keyboard": keyboard}
        return self.call("editMessageText", payload)

    def answer_callback(self, callback_id: str, text: str = "") -> None:
        self.call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})
