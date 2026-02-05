#!/usr/bin/env python3
"""
Discord Server Manager Bot - Main Entry Point

This is the main entry point for the Discord bot application.
It handles:
- Environment variable loading
- Logging setup
- Bot initialization
- Web server startup
- Error handling and graceful shutdown

The bot runs both a Discord bot and a web interface simultaneously.
"""

import os
import logging
import asyncio
import time
import discord
from dotenv import load_dotenv

# ============================================================================
# ENVIRONMENT SETUP SECTION
# ============================================================================

# Load environment variables from .env file first
# This must be done before importing any other modules that use env vars
load_dotenv()

# ============================================================================
# LOGGING CONFIGURATION SECTION
# ============================================================================

# Configure logging for the entire application
# This sets up how log messages are formatted and displayed
logging.basicConfig(
    level=logging.INFO,  # Log level: INFO shows important messages, DEBUG shows everything
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Format: timestamp - module - level - message
    handlers=[logging.StreamHandler()]  # Output logs to console
)

# Create a logger for this specific module
logger = logging.getLogger(__name__)

# ============================================================================
# MAIN FUNCTION SECTION
# ============================================================================

def main():
    """
    Main function that starts the Discord bot and web server
    
    This function:
    1. Validates required environment variables
    2. Creates the Discord bot instance
    3. Starts the web server in a background thread
    4. Starts the Discord bot
    5. Handles shutdown gracefully
    
    The bot runs both a Discord bot and a web interface simultaneously.
    The web interface provides a user-friendly way to configure the bot.
    """
    try:
        # Import bot and web server modules after environment is loaded
        # This ensures environment variables are available when modules are imported
        from bot import create_bot
        from web_server import create_app, run_web_server
        from threading import Thread
        
        # ============================================================================
        # ENVIRONMENT VALIDATION SECTION
        # ============================================================================
        
        # Check for required environment variables
        # These are essential for the bot to function properly
        if not os.getenv('DISCORD_TOKEN'):
            logger.error("❌ DISCORD_TOKEN environment variable not set!")
            logger.error("Please add your Discord bot token to the .env file")
            return
        
        if not os.getenv('MONGO_URI'):
            logger.error("❌ MONGO_URI environment variable not set!")
            logger.error("Please add your MongoDB connection string to the .env file")
            return
        
        logger.info("🚀 Starting Discord Server Manager Bot...")
        
        # ============================================================================
        # BOT INITIALIZATION SECTION
        # ============================================================================
        
        # Create the Discord bot instance
        # This sets up all the bot configuration, database connections, and cogs
        bot = create_bot()
        
        # ============================================================================
        # WEB SERVER SETUP SECTION
        # ============================================================================
        
        # Create the Flask web application
        # The web interface allows users to configure the bot through a browser
        app = create_app(bot)
        
        # Start the web server in a background thread
        # This allows the web interface to run alongside the Discord bot
        web_thread = Thread(target=run_web_server, args=(app,))
        web_thread.daemon = True  # Daemon threads are killed when main program exits
        web_thread.start()
        logger.info("🌐 Web server started on port 8080")
        logger.info("🌐 Web interface available at: http://localhost:8080")
        
        # ============================================================================
        # BOT STARTUP SECTION
        # ============================================================================
        
        # Start the Discord bot
        # This connects to Discord and begins processing events
        logger.info("🤖 Starting Discord bot...")
        bot.run(os.getenv('DISCORD_TOKEN'))
        
    # ============================================================================
    # ERROR HANDLING SECTION
    # ============================================================================
    
    except discord.errors.HTTPException as e:
        """
        Handle Discord HTTP errors (including rate limiting)
        """
        if e.status == 429:
            logger.error("=" * 80)
            logger.error("🚫 DISCORD RATE LIMIT ERROR (429)")
            logger.error("=" * 80)
            logger.error("")
            logger.error("Your bot is being rate-limited by Discord. Common causes:")
            logger.error("")
            logger.error("1. ⚠️  INVALID OR COMPROMISED TOKEN")
            logger.error("   → Your Discord token may be revoked or flagged")
            logger.error("   → Go to: https://discord.com/developers/applications")
            logger.error("   → Select your bot → 'Bot' → Click 'Reset Token'")
            logger.error("   → Update DISCORD_TOKEN in your .env or Render environment")
            logger.error("")
            logger.error("2. 🔄 RAPID RESTART LOOP")
            logger.error("   → Bot keeps crashing and restarting too quickly")
            logger.error("   → Discord blocks IPs that reconnect too frequently")
            logger.error("   → Wait 10-15 minutes before trying again")
            logger.error("")
            logger.error("3. 📝 TOKEN EXPOSED IN GIT")
            logger.error("   → If your token was committed to GitHub, Discord auto-revokes it")
            logger.error("   → Check git history: git log -p | grep -i discord_token")
            logger.error("   → Always use .env files and add them to .gitignore")
            logger.error("")
            logger.error("4. 🌐 SHARED IP FLAGGED (Render/Heroku)")
            logger.error("   → Hosting providers' shared IPs may be temporarily blocked")
            logger.error("   → Reset your token and try deploying again")
            logger.error("")
            logger.error("=" * 80)
            logger.error("⏱️  Waiting 60 seconds before retry to avoid further rate limiting...")
            logger.error("=" * 80)
            
            # Wait before retrying to avoid making the rate limit worse
            time.sleep(60)
        else:
            logger.error(f"❌ Discord HTTP error ({e.status}): {str(e)}")
            logger.error(f"Full error details: {e.text if hasattr(e, 'text') else 'No additional details'}")
    
    except discord.errors.LoginFailure:
        """
        Handle invalid token error
        """
        logger.error("=" * 80)
        logger.error("🔑 INVALID DISCORD TOKEN")
        logger.error("=" * 80)
        logger.error("")
        logger.error("The Discord token in your environment variables is invalid.")
        logger.error("")
        logger.error("Steps to fix:")
        logger.error("1. Go to https://discord.com/developers/applications")
        logger.error("2. Select your bot application")
        logger.error("3. Go to the 'Bot' section")
        logger.error("4. Click 'Reset Token' to generate a new one")
        logger.error("5. Update DISCORD_TOKEN in your .env file or Render environment")
        logger.error("")
        logger.error("⚠️  NEVER share your token or commit it to Git!")
        logger.error("=" * 80)
    
    except KeyboardInterrupt:
        """
        Handle Ctrl+C gracefully
        This allows users to stop the bot cleanly with Ctrl+C
        """
        logger.info("👋 Bot stopped by user (Ctrl+C)")
        
    except SystemExit:
        """
        Handle system exit gracefully
        This occurs when the bot is shut down programmatically
        """
        logger.info("🔄 Bot shutting down")
        
    except Exception as e:
        """
        Handle any unexpected errors
        This catches any errors that weren't handled elsewhere
        """
        logger.error(f"❌ Fatal error: {str(e)}", exc_info=True)
        logger.error("The bot has encountered an unexpected error and needs to shut down")
        raise

# ============================================================================
# ENTRY POINT SECTION
# ============================================================================

if __name__ == '__main__':
    """
    Entry point when this file is run directly
    
    This ensures the main function is only called when this file is executed,
    not when it's imported as a module.
    """
    main()
