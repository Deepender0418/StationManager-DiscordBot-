#!/usr/bin/env python3
"""
Discord Server Manager Bot - Main Entry Point
"""

import os
import logging
import asyncio
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

def main():
    """Main function to start the bot"""
    try:
        # Import bot after environment is loaded
        from bot import create_bot
        from web_server import create_app, run_web_server
        from threading import Thread
        
        # Validate environment
        if not os.getenv('DISCORD_TOKEN'):
            logger.error("❌ DISCORD_TOKEN environment variable not set!")
            return
        
        if not os.getenv('MONGO_URI'):
            logger.error("❌ MONGO_URI environment variable not set!")
            return
        
        logger.info("🚀 Starting Discord Server Manager Bot...")
        
        # Create bot instance
        bot = create_bot()
        
        # Create web server
        app = create_app(bot)
        
        # Start web server in background thread
        web_thread = Thread(target=run_web_server, args=(app,))
        web_thread.daemon = True
        web_thread.start()
        logger.info("🌐 Web server started on port 8080")
        
        # Start the bot
        logger.info("🤖 Starting Discord bot...")
        bot.run(os.getenv('DISCORD_TOKEN'))
        
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {str(e)}", exc_info=True)

if __name__ == '__main__':
    main()
