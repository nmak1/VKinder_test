from bot.vkinder_bot import VKinderBot
from config.settings import settings
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == "__main__":
    try:
        settings.validate()
        bot = VKinderBot()
        bot.run()
    except Exception as e:
        logging.critical(f"Failed to start bot: {e}")
        raise
