"""Single place that talks to the Telegram Bot API.

The raw aiohttp POST was duplicated in `_send_notification` and
`_send_failure_notification` in backend/services/webapp_scheduler.py; the score
canary would have been a third copy. Notably neither existing copy looked at
the response, so a Telegram-side rejection — bad parse_mode, over-long message,
revoked token — was logged as a success.

Sending a notification must never break the thing being notified about, so every
failure here is logged and reported as False rather than raised.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

TELEGRAM_MAX_MESSAGE_CHARS = 4096


def telegram_configured(config: Optional[Any] = None) -> bool:
    """True when both a bot token and a chat id are available."""
    if config is None:
        from src.config import get_config
        config = get_config()
    return bool(config.get("telegram.bot_token") and config.get("telegram.chat_id"))


async def send_telegram_message(
    text: str,
    config: Optional[Any] = None,
    parse_mode: str = "HTML",
    context: str = "message",
) -> bool:
    """Send `text` to the configured Telegram chat.

    Args:
        text: Message body, already escaped for `parse_mode`.
        config: Config instance; loaded if omitted.
        parse_mode: "HTML", "Markdown", or "" for plain text.
        context: Short label for log lines, e.g. "score canary alert".

    Returns:
        True only if Telegram accepted the message.
    """
    if config is None:
        from src.config import get_config
        config = get_config()

    bot_token = config.get("telegram.bot_token")
    chat_id = config.get("telegram.chat_id")

    if not bot_token or not chat_id:
        logger.debug("Telegram not configured; skipping %s", context)
        return False
    if not text:
        logger.warning("Refusing to send an empty %s", context)
        return False
    if len(text) > TELEGRAM_MAX_MESSAGE_CHARS:
        # Truncating would split mid-tag and fail the parse anyway.
        logger.warning("%s is %d chars, over Telegram's %d limit; not sending",
                       context, len(text), TELEGRAM_MAX_MESSAGE_CHARS)
        return False

    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    body = (await response.text())[:300]
                    logger.warning("Telegram rejected %s (HTTP %s): %s",
                                   context, response.status, body)
                    return False
        logger.info("Sent %s via Telegram", context)
        return True
    except Exception as e:
        logger.warning("Failed to send %s via Telegram: %s", context, e)
        return False
