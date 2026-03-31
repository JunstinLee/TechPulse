import hashlib
import json
import logging
import os

import requests

from utils.config import Config


logger = logging.getLogger("TelegramNotifier")


class TelegramNotifier:
    """Send generated reports to Telegram and skip unchanged files."""

    def __init__(self):
        self.token = Config.TG_BOT_TOKEN
        self.chat_id = Config.TG_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.state_file = Config.TG_PUSH_STATE_FILE

    def is_enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def _ensure_state_dir(self):
        state_dir = os.path.dirname(self.state_file)
        if state_dir:
            os.makedirs(state_dir, exist_ok=True)

    def _load_state(self) -> dict:
        if not os.path.exists(self.state_file):
            return {}

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read Telegram push state file: %s", exc)
            return {}

    def _save_state(self, state: dict):
        self._ensure_state_dir()
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def _file_hash(self, file_path: str) -> str:
        digest = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def has_changed(self, file_path: str) -> bool:
        if not os.path.exists(file_path):
            logger.error("Report file does not exist: %s", file_path)
            return False

        current_hash = self._file_hash(file_path)
        state = self._load_state()
        previous_hash = state.get(os.path.abspath(file_path))
        return current_hash != previous_hash

    def mark_as_pushed(self, file_path: str):
        state = self._load_state()
        state[os.path.abspath(file_path)] = self._file_hash(file_path)
        self._save_state(state)

    def send_message(self, text: str):
        if not self.is_enabled():
            logger.warning("Telegram config is incomplete, skipping message push.")
            return None

        try:
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=30,
            )
            response.raise_for_status()
            logger.info("Telegram message pushed successfully.")
            return response.json()
        except Exception as exc:
            logger.error("Telegram message push failed: %s", exc)
            return None

    def send_document(self, file_path: str, caption: str = None):
        if not self.is_enabled():
            logger.warning("Telegram config is incomplete, skipping document push.")
            return None

        if not os.path.exists(file_path):
            logger.error("Document does not exist: %s", file_path)
            return None

        data = {"chat_id": self.chat_id}
        if caption:
            data["caption"] = caption
            data["parse_mode"] = "Markdown"

        try:
            with open(file_path, "rb") as f:
                response = requests.post(
                    f"{self.base_url}/sendDocument",
                    data=data,
                    files={"document": f},
                    timeout=60,
                )
            response.raise_for_status()
            logger.info("Telegram document pushed successfully: %s", os.path.basename(file_path))
            return response.json()
        except Exception as exc:
            logger.error("Telegram document push failed: %s", exc)
            return None

    def build_report_message(self, file_path: str) -> str:
        filename = os.path.basename(file_path)
        return (
            "TechDistill Report Notification\n\n"
            f"File: `{filename}`\n"
            "Detailed report has been sent as an attachment."
        )

    def push_report(self, file_path: str) -> str:
        """
        Push report to Telegram.
        Returns status code: 'sent' (sent), 'skipped' (content unchanged), 'failed' (send failed), 'disabled' (not enabled)
        """
        if not self.is_enabled():
            logger.warning("Telegram config is incomplete, skipping report push.")
            return "disabled"

        if not os.path.exists(file_path):
            logger.error("Report file does not exist, cannot push: %s", file_path)
            return "failed"

        if not self.has_changed(file_path):
            logger.info("Report content unchanged, skipping Telegram push: %s", os.path.basename(file_path))
            return "skipped"

        logger.info("Detected updated report, pushing to Telegram: %s", file_path)
        summary = self.build_report_message(file_path)
        message_result = self.send_message(summary)
        document_result = self.send_document(file_path)

        if message_result and document_result:
            self.mark_as_pushed(file_path)
            logger.info("Report push completed and state recorded: %s", os.path.basename(file_path))
            return "sent"
        else:
            logger.warning("Report push did not fully succeed, state was not updated: %s", os.path.basename(file_path))
            return "failed"


notifier = TelegramNotifier()
