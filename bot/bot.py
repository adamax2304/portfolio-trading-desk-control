"""Thin Telegram bot: opens the Mini App + emergency actions + push alerts.

NO business logic here — it is a launcher + notifier. The control API does the work.
Run: TELEGRAM_BOT_TOKEN=... MINI_APP_URL=https://... ALLOWED_TELEGRAM_USER_IDS=123 python bot/bot.py
"""

from __future__ import annotations

import asyncio
import os

try:
    from aiogram import Bot, Dispatcher, F
    from aiogram.client.session.aiohttp import AiohttpSession
    from aiogram.filters import Command
    from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup, Message,
                                WebAppInfo)
    from aiohttp import ThreadedResolver
except ImportError:  # pragma: no cover
    raise SystemExit("pip install aiogram>=3.4")

import httpx


def _make_bot() -> "Bot":
    """Build the Bot with aiohttp's OS resolver (ThreadedResolver).

    If aiodns/c-ares is installed, aiohttp defaults to it; on Windows that often fails with
    'Could not contact DNS servers'. The OS getaddrinfo resolver (same one curl uses) works.
    """
    session = AiohttpSession()
    try:
        session._connector_init["resolver"] = ThreadedResolver()
    except Exception:  # pragma: no cover - version-robust fallback
        pass
    return Bot(TOKEN, session=session)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
MINI_APP_URL = os.getenv("MINI_APP_URL", "https://example.com")
CONTROL_API = os.getenv("CONTROL_API_BASE", os.getenv("API_BASE_URL", "http://127.0.0.1:8010"))
# Server-to-server token so the bot can use the safe emergency-pause path (the bot cannot mint
# Telegram initData). Must match CONTROL_BOT_TOKEN on the backend. Optional in dev.
CONTROL_BOT_TOKEN = os.getenv("CONTROL_BOT_TOKEN", "")
ALLOWED = {int(x) for x in os.getenv("ALLOWED_TELEGRAM_USER_IDS", "").replace(";", ",").split(",") if x.strip().lstrip("-").isdigit()}

dp = Dispatcher()

HELP = (
    "AI Trading Desk — Control Plane\n\n"
    "/start — open the Mini App + quick actions\n"
    "/help — this message\n\n"
    "What you can do inside the Mini App:\n"
    "• View signals, trades, charts, market & system health\n"
    "• Manage paper risk settings (audited command queue)\n"
    "• Submit / close / cancel paper orders\n"
    "• Record notes, run a sanity check, emergency-pause\n\n"
    "Live trading and auto-live are LOCKED. The bot carries no trading logic."
)


def _allowed(uid: int) -> bool:
    return not ALLOWED or uid in ALLOWED


def _menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📟 Open Trading Desk", web_app=WebAppInfo(url=MINI_APP_URL))],
        [InlineKeyboardButton(text="⏸ Emergency Pause", callback_data="pause")],
    ])


@dp.message(Command("start"))
async def start(m: Message):
    if not _allowed(m.from_user.id):
        return await m.answer("Not authorized.")
    await m.answer("AI Trading Desk — Control Plane\nRead-only + paper. Live is locked.", reply_markup=_menu())


@dp.message(Command("help"))
async def help_cmd(m: Message):
    if not _allowed(m.from_user.id):
        return await m.answer("Not authorized.")
    await m.answer(HELP, reply_markup=_menu())


@dp.callback_query(F.data == "pause")
async def pause(cq):
    if not _allowed(cq.from_user.id):
        return await cq.answer("Not authorized", show_alert=True)
    # the bot cannot itself stop processes — it asks the control API to enqueue the command,
    # authenticating with the server-to-server bot token (server still enforces auth).
    headers = {"X-Telegram-Init-Data": ""}
    if CONTROL_BOT_TOKEN:
        headers["X-Control-Bot-Token"] = CONTROL_BOT_TOKEN
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{CONTROL_API}/api/emergency-pause", headers=headers)
        if r.status_code != 200:
            return await cq.answer(f"rejected ({r.status_code}) — set CONTROL_BOT_TOKEN", show_alert=True)
    except Exception as e:  # pragma: no cover
        return await cq.answer(f"failed: {e}", show_alert=True)
    await cq.answer("Emergency pause command queued.", show_alert=True)


async def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN required")
    await Dispatcher.start_polling(dp, _make_bot())


if __name__ == "__main__":
    asyncio.run(main())
