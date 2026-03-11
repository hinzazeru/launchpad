#!/usr/bin/env python3
"""Run the Telegram bot for remote job matcher control.

This script starts the Telegram bot that allows you to control
your LinkedIn Job Matcher from anywhere using Telegram commands.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

# Prevent tokenizers library deadlock when forking during Google Sheets export
# See: https://github.com/huggingface/tokenizers/issues/993
os.environ["TOKENIZERS_PARALLELISM"] = "false"
from src.bot.telegram_bot import TelegramBot
from src.config import get_config

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)


def main():
    """Run the Telegram bot."""
    print("=" * 80)
    print("LinkedIn Job Matcher - Telegram Bot")
    print("=" * 80)
    print()

    # Load configuration
    config = get_config()

    # Check if bot is enabled
    if not config.get("telegram.enabled", False):
        print("❌ Telegram bot is DISABLED in configuration")
        print()
        print("To enable:")
        print("1. Create a bot with @BotFather on Telegram")
        print("2. Get your bot token")
        print("3. Get your Telegram user ID (use @userinfobot)")
        print("4. Update config.yaml:")
        print("   telegram:")
        print("     enabled: true")
        print("     bot_token: 'YOUR_BOT_TOKEN'")
        print("     allowed_user_id: 'YOUR_USER_ID'")
        print()
        print("See docs/TELEGRAM_BOT.md for detailed setup instructions")
        print()
        return 1

    # Check configuration
    bot_token = config.get("telegram.bot_token")
    user_id = config.get("telegram.allowed_user_id")

    if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
        print("❌ Bot token not configured")
        print()
        print("Please set telegram.bot_token in config.yaml")
        print("Get your token from @BotFather on Telegram")
        print()
        return 1

    if not user_id or user_id == "YOUR_TELEGRAM_USER_ID":
        print("⚠️  Warning: allowed_user_id not set")
        print()
        print("Without this, anyone can control your bot!")
        print("Get your user ID from @userinfobot on Telegram")
        print("and set telegram.allowed_user_id in config.yaml")
        print()
        response = input("Continue anyway? (yes/no): ")
        if response.lower() != "yes":
            return 1

    # Initialize and run bot
    print("✓ Configuration validated")
    print()

    bot = TelegramBot()

    if not bot.enabled:
        print("❌ Failed to initialize bot")
        return 1

    print("=" * 80)
    print("Bot is starting...")
    print("Open Telegram and send /start to your bot to begin!")
    print()
    print("Available commands:")
    print("  /start - Welcome message")
    print("  /help - Show all commands")
    print("  /search - Run immediate job search")
    print("  /status - Check scheduler status")
    print("  /matches - View recent top matches")
    print("  /config - Show current configuration")
    print()
    print("Press Ctrl+C to stop the bot")
    print("=" * 80)
    print()

    try:
        bot.run()
        return 0
    except KeyboardInterrupt:
        print("\n\nStopping bot...")
        print("Bot stopped")
        return 0
    except Exception as e:
        logger.error(f"Error running bot: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
