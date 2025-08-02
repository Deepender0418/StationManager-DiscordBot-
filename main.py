import os
import logging
from bot import create_bot
from web_server import create_app, run_web_server
from threading import Thread

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Create bot instance
bot = create_bot()

# Create Flask app
app = create_app(bot)

# Start web server in a separate thread
web_thread = Thread(target=run_web_server, args=(app,))
web_thread.daemon = True
web_thread.start()
logging.info("Web server thread started")

# Start the bot
if __name__ == '__main__':
    try:
        token = os.getenv('DISCORD_TOKEN')
        if not token:
            logging.error("DISCORD_TOKEN environment variable not set!")
            exit(1)
            
        logging.info("Starting Discord bot...")
        bot.run(token)
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        exit(1)