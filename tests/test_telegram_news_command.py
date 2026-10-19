"""Telegram /news command — routing and fallbacks."""
from __future__ import annotations

from telegram_command_format import normalize_telegram_command


def test_normalize_telegram_command_strips_bot_suffix():
    assert normalize_telegram_command("/news@ForexGodBot") == "/news"
    assert normalize_telegram_command("/NEWS@bot") == "/news"
    assert normalize_telegram_command("/help") == "/help"


def test_handle_news_returns_message_when_cache_missing(monkeypatch, tmp_path):
    missing = tmp_path / "data" / "upcoming_news.json"
    monkeypatch.setattr(
        "news_calendar_utils.UPCOMING_NEWS_FILE",
        missing,
    )

    from telegram_command_center import TelegramCommandCenter

    cc = TelegramCommandCenter.__new__(TelegramCommandCenter)
    cc._refresh_upcoming_news_cache = lambda timeout_sec=22.0: "error:test-offline"

    msg = cc.handle_news_command()
    assert "News HIGH IMPACT" in msg or "NEWS ERROR" in msg
    assert "upcoming_news" in msg.lower() or str(missing.name) in msg
