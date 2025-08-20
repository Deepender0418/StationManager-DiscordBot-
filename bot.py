#!/usr/bin/env python3
"""
Discord Bot Core - Main bot file that handles Discord events and cog management

This file contains:
- Bot creation and configuration
- Database connection setup
- Background task scheduling (birthdays, events)
- Core event handlers (ready, disconnect, resume, close)
- Command error handling and autocomplete
- Cog loading system

The bot is designed to be modular with separate cogs handling specific features.
"""

import os
import discord
from discord.ext import commands
import motor.motor_asyncio
import logging
import asyncio
from datetime import datetime, timedelta
from utils.timezone import IST
from utils.database import get_guild_config

logger = logging.getLogger(__name__)

def create_bot():
    """
    Create and configure the Discord bot instance
    
    This function:
    1. Sets up bot intents and configuration
    2. Establishes MongoDB connection
    3. Configures command templates for autocomplete
    4. Sets up background tasks for scheduled events
    5. Defines core event handlers
    """
    
    # ============================================================================
    # BOT CONFIGURATION SECTION
    # ============================================================================
    
    # Configure Discord bot intents (permissions)
    intents = discord.Intents.default()
    intents.members = True          # Required for member join/leave events
    intents.message_content = True  # Required for reading message content
    intents.presences = False       # Not needed, saves resources

    # Create the bot instance with prefix and intents
    bot = commands.Bot(
        command_prefix=os.getenv('COMMAND_PREFIX', '!'),  # Default prefix is '!'
        intents=intents,
        help_command=None  # We'll use our custom help system
    )

    # ============================================================================
    # DATABASE CONNECTION SECTION
    # ============================================================================
    
    # Get database configuration from environment variables
    mongo_uri = os.getenv('MONGO_URI')
    db_name = os.getenv('DATABASE_NAME', 'discord_bot')

    # Establish MongoDB connection with optimized settings for Atlas
    try:
        client = motor.motor_asyncio.AsyncIOMotorClient(
            mongo_uri,
            serverSelectionTimeoutMS=5000,    # 5 second timeout for server selection
            connectTimeoutMS=10000,           # 10 second timeout for initial connection
            socketTimeoutMS=10000,            # 10 second timeout for operations
            maxPoolSize=10,                   # Maximum 10 connections in pool
            retryWrites=True,                 # Automatically retry failed writes
            retryReads=True,                  # Automatically retry failed reads
            w='majority'                      # Wait for majority of replicas
        )
        db = client[db_name]
        
        logger.info("🔌 MongoDB connection established")
        
        # Attach database collections to bot for easy access in cogs
        bot.guild_configs = db.guild_configs    # Server configuration settings
        bot.birthdays = db.birthdays           # User birthday records
        bot.invite_logs = db.invite_logs       # Member join/leave tracking
        bot.invite_cache = {}                  # Cache for invite tracking
        bot.mongo_client = client              # Store client for cleanup
        
        # Flag to prevent duplicate background task creation
        bot.tasks_started = False
        
        logger.info("✅ MongoDB collections configured successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to connect to MongoDB: {str(e)}")
        logger.error("Please check your MONGO_URI and MongoDB Atlas configuration")
        raise

    # ============================================================================
    # COMMAND TEMPLATES SECTION
    # ============================================================================
    
    # Define command templates for autocomplete and help system
    # These provide helpful information when users type incomplete commands
    bot.command_templates = {
        "birthday": {
            "description": "Set birthday (Admin: @user MM-DD [message] | User: MM-DD)",
            "usage": "!birthday @user MM-DD [message] (Admin) | !birthday MM-DD (User)",
            "examples": ["!birthday @John 05-15", "!birthday 08-03"],
            "bot_info": "🎂 Birthday Manager Bot"
        },
        "testbirthday": {
            "description": "Test birthday announcement (Admin only)",
            "usage": "!testbirthday [@user]",
            "examples": ["!testbirthday", "!testbirthday @John"],
            "bot_info": "🎂 Birthday Manager Bot"
        },
        "testevents": {
            "description": "Test daily events announcement (Admin only)",
            "usage": "!testevents",
            "examples": ["!testevents"],
            "bot_info": "📅 Daily Events Bot"
        },
        "testwelcome": {
            "description": "Test welcome message (Admin only)",
            "usage": "!testwelcome",
            "examples": ["!testwelcome"],
            "bot_info": "🌟 Welcome Manager Bot"
        },
        "botintro": {
            "description": "Bot introduces itself (Admin only)",
            "usage": "!botintro",
            "examples": ["!botintro"],
            "bot_info": "🤖 Server Manager Bot"
        },
        "config": {
            "description": "Set channel configurations (Admin only)",
            "usage": "!config <type> <channel>",
            "examples": ["!config welcome #welcome", "!config announcement #announcements"],
            "bot_info": "⚙️ Configuration Manager Bot"
        },
        "announce": {
            "description": "Send server announcement (Admin only)",
            "usage": "!announce [message]",
            "examples": ["!announce Server maintenance at 10PM"],
            "bot_info": "📢 Announcement Bot"
        },
        "help": {
            "description": "Show command help information",
            "usage": "!help [command]",
            "examples": ["!help", "!help birthday"],
            "bot_info": "❓ Help System Bot"
        },
        "templates": {
            "description": "Show all command templates",
            "usage": "!templates",
            "examples": ["!templates"],
            "bot_info": "📋 Template Manager Bot"
        },
        "show": {
            "description": "Show command template",
            "usage": "!show <command>",
            "examples": ["!show birthday", "!show config"],
            "bot_info": "📋 Template Manager Bot"
        },
        "invites": {
            "description": "View invite statistics (Admin only)",
            "usage": "!invites",
            "examples": ["!invites"],
            "bot_info": "🎫 Invite Tracker Bot"
        },
        "invitestats": {
            "description": "View detailed invite statistics (Admin only)",
            "usage": "!invitestats",
            "examples": ["!invitestats"],
            "bot_info": "📊 Invite Statistics Bot"
        }
    }

    # ============================================================================
    # BACKGROUND TASKS SECTION
    # ============================================================================
    
    async def check_birthdays_at_midnight():
        """
        Background task that runs every day at midnight to check for birthdays
        
        This task:
        1. Calculates time until next midnight
        2. Sleeps until midnight
        3. Calls the birthday cog to send announcements
        4. Handles errors gracefully with retry logic
        """
        await bot.wait_until_ready()  # Wait for bot to be fully connected
        
        while not bot.is_closed():
            try:
                # Calculate time until next midnight in IST timezone
                now = datetime.now(IST)
                next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                seconds_until_midnight = (next_midnight - now).total_seconds()
                
                logger.info(f"Waiting {seconds_until_midnight} seconds until next midnight birthday check")
                await asyncio.sleep(seconds_until_midnight)
                
                # Check for birthdays using the birthday cog
                birthday_cog = bot.get_cog('BirthdayCog')
                if birthday_cog:
                    await birthday_cog.send_birthday_announcements()
                
            except asyncio.CancelledError:
                logger.info("Birthday check task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in midnight birthday check: {str(e)}")
                await asyncio.sleep(3600)  # Wait 1 hour if error occurs

    async def check_daily_events_at_8am():
        """
        Background task that runs every day at 8 AM to send daily events
        
        This task:
        1. Calculates time until next 8 AM
        2. Sleeps until 8 AM
        3. Calls the events cog to send daily announcements
        4. Handles errors gracefully with retry logic
        """
        await bot.wait_until_ready()  # Wait for bot to be fully connected
        
        while not bot.is_closed():
            try:
                # Calculate time until next 8 AM in IST timezone
                now = datetime.now(IST)
                next_8am = (now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
                
                # If it's already past 8 AM today, schedule for tomorrow
                if now.hour >= 8:
                    next_8am = next_8am + timedelta(days=1)
                
                seconds_until_8am = (next_8am - now).total_seconds()
                
                logger.info(f"Waiting {seconds_until_8am} seconds until next 8 AM events check")
                await asyncio.sleep(seconds_until_8am)
                
                # Send daily events announcement using the events cog
                events_cog = bot.get_cog('EventsCog')
                if events_cog:
                    await events_cog.send_daily_events_announcement()
                
            except asyncio.CancelledError:
                logger.info("Daily events check task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in 8 AM events check: {str(e)}")
                await asyncio.sleep(3600)  # Wait 1 hour if error occurs

    # ============================================================================
    # CORE EVENT HANDLERS SECTION
    # ============================================================================
    
    @bot.event
    async def on_ready():
        """
        Called when the bot successfully connects to Discord
        
        This event handler:
        1. Logs successful connection
        2. Loads all cogs (feature modules)
        3. Caches invites for tracking
        4. Initializes guild configurations
        5. Starts background tasks
        """
        logger.info(f"🤖 Bot is ready! Logged in as {bot.user}")
        logger.info(f"📊 Connected to {len(bot.guilds)} guilds")
        
        # Load all cogs (feature modules)
        await load_cogs(bot)
        
        # Cache invites for all guilds (needed for invite tracking)
        for guild in bot.guilds:
            try:
                invites = await guild.invites()
                # Store as mapping for O(1) lookup by invite code
                bot.invite_cache[guild.id] = {invite.code: invite for invite in invites}
                logger.info(f"📋 Cached {len(invites)} invites for {guild.name}")
            except Exception as e:
                logger.warning(f"Could not cache invites for {guild.name}: {str(e)}")
        
        # Initialize guild configurations (create default configs if they don't exist)
        for guild in bot.guilds:
            try:
                config = await get_guild_config(bot.guild_configs, str(guild.id))
                if not config:
                    # Create default config for new guilds
                    await bot.guild_configs.insert_one({
                        "guild_id": str(guild.id),
                        "guild_name": guild.name,
                        "welcome_channel_id": None,
                        "announcement_channel_id": None,
                        "birthday_message": "🎉 **Happy Birthday {USER_MENTION}!** 🎉\nHope you have an amazing day!"
                    })
                    logger.info(f"✅ Initialized config for {guild.name}")
            except Exception as e:
                logger.error(f"❌ Error initializing config for {guild.name}: {str(e)}")
        
        # Start background tasks only once (prevent duplicates)
        if not bot.tasks_started:
            bot.loop.create_task(check_birthdays_at_midnight())
            bot.loop.create_task(check_daily_events_at_8am())
            
            logger.info("🎂 Birthday check task started")
            logger.info("📅 Daily events check task started (8 AM)")
            
            # Calculate and log timing information
            now = datetime.now(IST)
            next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            seconds_until_midnight = (next_midnight - now).total_seconds()
            logger.info(f"Waiting {seconds_until_midnight:.6f} seconds until next midnight birthday check")
            
            # Calculate time until next 8 AM
            next_8am = (now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
            if now.hour >= 8:
                next_8am = (now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
            else:
                next_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
            
            seconds_until_8am = (next_8am - now).total_seconds()
            logger.info(f"Waiting {seconds_until_8am:.6f} seconds until next 8 AM events check")
            
            bot.tasks_started = True
        else:
            logger.info("🔄 Background tasks already running, skipping duplicate creation")

    @bot.event
    async def on_disconnect():
        """
        Called when the bot disconnects from Discord
        
        This handler keeps MongoDB connection alive during temporary disconnects
        to avoid connection overhead when the bot reconnects.
        """
        logger.warning("🔌 Bot disconnected from Discord")
        
        # Don't close MongoDB connection on disconnect - only on shutdown
        # The connection will be reused when the bot reconnects
        logger.info("🔄 Keeping MongoDB connection alive for reconnection")

    @bot.event
    async def on_resumed():
        """
        Called when the bot resumes connection after a disconnect
        
        This handler verifies the MongoDB connection is still alive and
        reconnects if necessary.
        """
        logger.info("🔄 Bot resumed connection to Discord")
        
        # Verify MongoDB connection is still alive
        try:
            if hasattr(bot, 'mongo_client') and bot.mongo_client:
                await bot.mongo_client.admin.command('ping')
                logger.info("✅ MongoDB connection verified after resume")
            else:
                logger.warning("⚠️ MongoDB client not available, attempting reconnection")
                raise Exception("MongoDB client not available")
        except Exception as e:
            logger.error(f"❌ MongoDB connection lost during disconnect: {str(e)}")
            # Reconnect to MongoDB
            try:
                mongo_uri = os.getenv('MONGO_URI')
                db_name = os.getenv('DATABASE_NAME', 'discord_bot')
                
                # Close old client if it exists
                if hasattr(bot, 'mongo_client') and bot.mongo_client:
                    bot.mongo_client.close()
                
                # Create new client with same settings
                client = motor.motor_asyncio.AsyncIOMotorClient(
                    mongo_uri,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=10000,
                    socketTimeoutMS=10000,
                    maxPoolSize=10,
                    retryWrites=True,
                    retryReads=True,
                    w='majority'
                )
                db = client[db_name]
                
                # Reattach collections to bot
                bot.guild_configs = db.guild_configs
                bot.birthdays = db.birthdays
                bot.invite_logs = db.invite_logs
                bot.mongo_client = client
                
                logger.info("✅ MongoDB connection re-established")
            except Exception as reconnect_error:
                logger.error(f"❌ Failed to reconnect to MongoDB: {str(reconnect_error)}")

    @bot.event
    async def on_close():
        """
        Called when the bot is shutting down
        
        This handler properly closes the MongoDB connection to prevent
        resource leaks and ensure clean shutdown.
        """
        logger.info("🔄 Bot is shutting down...")
        
        # Close MongoDB connection only on actual shutdown
        if hasattr(bot, 'mongo_client') and bot.mongo_client:
            try:
                bot.mongo_client.close()
                logger.info("🔌 MongoDB connection closed")
            except Exception as e:
                logger.error(f"Error closing MongoDB connection: {str(e)}")

    # ============================================================================
    # COMMAND ERROR HANDLING SECTION
    # ============================================================================
    
    @bot.event
    async def on_command_error(ctx, error):
        """
        Handle command errors and provide helpful feedback
        
        This handler:
        1. Detects when users type incorrect commands
        2. Suggests correct commands for common typos
        3. Shows command templates for incomplete commands
        4. Provides helpful error messages
        """
        if isinstance(error, commands.CommandNotFound):
            # Check if the command exists in our templates
            command = ctx.message.content.split()[0][1:].lower()  # Remove '!' and get command name
            
            # Check for common typos and suggest corrections
            typo_suggestions = {
                "introbot": "botintro",
                "botintro": "botintro",
                "birthday": "birthday",
                "config": "config",
                "help": "help"
            }
            
            if command in typo_suggestions:
                suggested_command = typo_suggestions[command]
                if suggested_command in bot.command_templates:
                    template = bot.command_templates[suggested_command]
                    
                    # Create helpful error embed
                    embed = discord.Embed(
                        title="🤖 Command Not Found",
                        description=f"Did you mean **`!{suggested_command}`**?",
                        color=discord.Color.blue()
                    )
                    
                    embed.add_field(
                        name="📋 Usage",
                        value=f"`{template['usage']}`",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="💭 Description",
                        value=template['description'],
                        inline=False
                    )
                    
                    if template['examples']:
                        examples = "\n".join([f"`{ex}`" for ex in template['examples']])
                        embed.add_field(
                            name="💡 Examples",
                            value=examples,
                            inline=False
                        )
                    
                    embed.set_footer(text=f"💡 Common typo: '{command}' → '{suggested_command}'")
                    await ctx.send(embed=embed, delete_after=15)
                    return
            
            # Show template for incomplete commands
            existing_command = bot.get_command(command)
            if command in bot.command_templates and not existing_command:
                template = bot.command_templates[command]
                
                # Send command template info
                embed = discord.Embed(
                    title=f"🤖 {template['bot_info']}",
                    description=f"**Command:** `{ctx.message.content}`\n**Description:** {template['description']}",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="📋 Usage",
                    value=f"`{template['usage']}`",
                    inline=False
                )
                
                if template['examples']:
                    examples = "\n".join([f"`{ex}`" for ex in template['examples']])
                    embed.add_field(
                        name="💡 Examples",
                        value=examples,
                        inline=False
                    )
                
                embed.set_footer(text="💡 This info appears when commands are incomplete!")
                
                await ctx.send(embed=embed, delete_after=15)
                return
        
        # For other errors, log them for debugging
        logger.error(f"Command error: {error}")

    @bot.event
    async def on_message(message):
        """
        Handle message events for autocomplete functionality
        
        This handler:
        1. Processes commands normally
        2. Checks for incomplete command-like messages
        3. Shows helpful command templates
        4. Provides autocomplete suggestions
        """
        # Process commands first (required for command handling)
        await bot.process_commands(message)
        
        # Check for autocomplete on incomplete command-like messages only
        if message.content.startswith('!') and len(message.content.split()) == 1:
            command = message.content[1:].lower()  # Remove '!' and get command name
            
            # Only show template for incomplete commands (not exact matches)
            # Check if this is a complete command that exists
            existing_command = bot.get_command(command)
            if command in bot.command_templates and not existing_command:
                template = bot.command_templates[command]
                
                # Send command template info
                embed = discord.Embed(
                    title=f"🤖 {template['bot_info']}",
                    description=f"**Command:** `{message.content}`\n**Description:** {template['description']}",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="📋 Usage",
                    value=f"`{template['usage']}`",
                    inline=False
                )
                
                if template['examples']:
                    examples = "\n".join([f"`{ex}`" for ex in template['examples']])
                    embed.add_field(
                        name="💡 Examples",
                        value=examples,
                        inline=False
                    )
                
                embed.set_footer(text="💡 Type the full command to execute it!")
                
                # Send the template info (ignore errors if we can't send)
                try:
                    await message.channel.send(embed=embed, delete_after=10)
                except:
                    pass  # Ignore if we can't send the message

    return bot

# ============================================================================
# COG LOADING SECTION
# ============================================================================

async def load_cogs(bot):
    """
    Load all cogs (feature modules) into the bot
    
    This function:
    1. Defines the list of cogs to load
    2. Attempts to load each cog
    3. Continues loading even if some cogs fail
    4. Provides detailed logging of the loading process
    
    Cogs are modular components that handle specific bot features:
    - config: Server configuration and welcome messages
    - birthday: Birthday management and announcements
    - events: Daily events and holiday announcements
    - help: Help system and command documentation
    - sync: Command synchronization with Discord
    - announce: Server announcement commands
    - invite_tracking: Member join/leave tracking and invite statistics
    """
    cogs = [
        'cogs.config',           # Server configuration and welcome messages
        'cogs.birthday',         # Birthday management and announcements
        'cogs.events',           # Daily events and holiday announcements
        'cogs.help',             # Help system and command documentation
        'cogs.sync',             # Command synchronization with Discord
        'cogs.announce',         # Server announcement commands
        'cogs.invite_tracking',  # Member join/leave tracking and invite statistics
        'cogs.ai_chat'           # AI chat functionality
    ]
    
    loaded_cogs = 0
    total_cogs = len(cogs)
    
    # Load each cog individually
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            logger.info(f'✅ Loaded cog: {cog}')
            loaded_cogs += 1
        except Exception as e:
            logger.error(f'❌ Failed to load cog {cog}: {str(e)}')
            # Continue loading other cogs even if one fails
    
    logger.info(f'📦 Loaded {loaded_cogs}/{total_cogs} cogs successfully')
    
    if loaded_cogs < total_cogs:
        logger.warning(f'⚠️ {total_cogs - loaded_cogs} cog(s) failed to load')
