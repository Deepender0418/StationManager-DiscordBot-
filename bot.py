#!/usr/bin/env python3
"""
Discord Bot Core - Handles Discord events and cog management
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

async def send_birthday_announcements(bot):
    """Send birthday announcements for today"""
    try:
        today = datetime.now(IST)
        today_str = f"{today.month:02d}-{today.day:02d}"
        
        logger.info(f"Checking for birthdays on {today_str}")
        
        # Get all birthdays for today
        cursor = bot.birthdays.find({"birthday": today_str})
        birthdays = await cursor.to_list(length=None)
        
        if not birthdays:
            logger.info("No birthdays today")
            return
        
        logger.info(f"Found {len(birthdays)} birthdays today")
        
        # Group birthdays by guild
        guild_birthdays = {}
        for birthday_doc in birthdays:
            guild_id = birthday_doc.get('guild_id')
            if guild_id not in guild_birthdays:
                guild_birthdays[guild_id] = []
            guild_birthdays[guild_id].append(birthday_doc)
        
        # Send announcements for each guild
        for guild_id, guild_birthday_list in guild_birthdays.items():
            try:
                guild = bot.get_guild(guild_id)
                if not guild:
                    continue
                
                # Get guild config
                config = await get_guild_config(bot.guild_configs, str(guild_id))
                announcement_channel_id = config.get('announcement_channel_id') if config else None
                default_message = config.get('birthday_message', "🎉 **Happy Birthday {USER_MENTION}!** 🎉\nHope you have an amazing day!")
                
                if not announcement_channel_id:
                    logger.warning(f"No announcement channel configured for guild {guild_id}")
                    continue
                
                announcement_channel = bot.get_channel(int(announcement_channel_id))
                if not announcement_channel:
                    logger.warning(f"Announcement channel not found for guild {guild_id}")
                    continue
                
                # Create birthday announcement for all members
                birthday_members = []
                for birthday_doc in guild_birthday_list:
                    user_id = birthday_doc.get('user_id')
                    member = guild.get_member(user_id)
                    if member:
                        birthday_members.append({
                            'member': member,
                            'custom_message': birthday_doc.get('custom_message')
                        })
                
                if not birthday_members:
                    continue
                
                # Send individual birthday announcement for each member
                for member_data in birthday_members:
                    member = member_data['member']
                    custom_message = member_data['custom_message']
                    
                    # Use custom message if available, otherwise use default
                    if custom_message:
                        message = custom_message.replace('{USER_MENTION}', member.mention).replace('{USER_NAME}', member.display_name)
                    else:
                        message = default_message.replace('{USER_MENTION}', member.mention).replace('{USER_NAME}', member.display_name)
                    
                    # Create embed with profile picture and custom text
                    embed = discord.Embed(
                        title="🎂 Birthday Celebration!",
                        description=message,
                        color=discord.Color.pink()
                    )
                    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
                    embed.set_footer(text=f"🎈 {member.display_name} is celebrating today!")
                    
                    # Send @everyone outside the embed, custom message inside
                    await announcement_channel.send(content="@everyone", embed=embed)
                    logger.info(f"Sent birthday announcement for {member.display_name} in {guild.name}")
                
            except Exception as e:
                logger.error(f"Error sending birthday announcements for guild {guild_id}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error checking today's birthdays: {str(e)}")

async def send_daily_events_announcement(bot):
    """Send daily events announcement at 8 AM"""
    try:
        # Import the function from events cog
        from cogs.events import EventsCog
        events_cog = EventsCog(bot)
        await events_cog.send_daily_events_announcement()
    except Exception as e:
        logger.error(f"Error sending daily events announcement: {str(e)}")

def create_bot():
    """Create and configure the Discord bot"""

    # Bot configuration
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    intents.presences = False

    bot = commands.Bot(
        command_prefix=os.getenv('COMMAND_PREFIX', '!'),
        intents=intents,
        help_command=None
    )

    # Database setup
    mongo_uri = os.getenv('MONGO_URI')
    db_name = os.getenv('DATABASE_NAME', 'discord_bot')

    # MongoDB connection with proper options for Atlas
    try:
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
        
        logger.info("🔌 MongoDB connection established")
        
        bot.guild_configs = db.guild_configs
        bot.birthdays = db.birthdays
        bot.invite_logs = db.invite_logs
        bot.invite_cache = {}
        bot.mongo_client = client  # Store client for cleanup
        
        # Flag to prevent duplicate task creation
        bot.tasks_started = False
        
        logger.info("✅ MongoDB collections configured successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to connect to MongoDB: {str(e)}")
        logger.error("Please check your MONGO_URI and MongoDB Atlas configuration")
        raise

    # Command templates for autocomplete
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
        }
    }

    async def check_birthdays_at_midnight():
        """Check for birthdays at midnight every day"""
        await bot.wait_until_ready()
        
        while not bot.is_closed():
            try:
                # Calculate time until next midnight
                now = datetime.now(IST)
                next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                seconds_until_midnight = (next_midnight - now).total_seconds()
                
                logger.info(f"Waiting {seconds_until_midnight} seconds until next midnight birthday check")
                await asyncio.sleep(seconds_until_midnight)
                
                # Check for birthdays
                await send_birthday_announcements(bot)
                
            except Exception as e:
                logger.error(f"Error in midnight birthday check: {str(e)}")
                await asyncio.sleep(3600)  # Wait 1 hour if error occurs

    async def check_daily_events_at_8am():
        """Check for daily events at 8 AM every day"""
        await bot.wait_until_ready()
        
        while not bot.is_closed():
            try:
                # Calculate time until next 8 AM
                now = datetime.now(IST)
                next_8am = (now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
                
                # If it's already past 8 AM today, schedule for tomorrow
                if now.hour >= 8:
                    next_8am = next_8am + timedelta(days=1)
                
                seconds_until_8am = (next_8am - now).total_seconds()
                
                logger.info(f"Waiting {seconds_until_8am} seconds until next 8 AM events check")
                await asyncio.sleep(seconds_until_8am)
                
                # Send daily events announcement
                await send_daily_events_announcement(bot)
                
            except Exception as e:
                logger.error(f"Error in 8 AM events check: {str(e)}")
                await asyncio.sleep(3600)  # Wait 1 hour if error occurs

    # Array of different welcome messages that rotate
    welcome_messages = [
        "We're delighted to have you join our community! Your presence here is truly valued. Welcome aboard, and we hope you have an amazing time with us! 🌟",
        "Welcome to our wonderful community! We're so excited to have you here. Your journey with us begins now, and we can't wait to see what you'll bring to our server! ✨",
        "A warm welcome to our newest member! You've just joined an amazing community filled with wonderful people. We're thrilled to have you here! 🎉",
        "Welcome aboard! You've found your way to our special community, and we're absolutely delighted to have you here. Let's make some amazing memories together! 🌈",
        "Hello and welcome! You've just joined a fantastic community where everyone is valued and appreciated. We're so glad you're here! 🎊",
        "Welcome to our family! You've just become part of something truly special. We're excited to get to know you and share this amazing journey together! 💫",
        "A heartfelt welcome to our newest member! You've joined a community that values friendship, respect, and fun. We're so happy you're here! 🌟",
        "Welcome to our wonderful server! You've just stepped into a community filled with amazing people and great vibes. We're excited to have you here! ✨"
    ]
    current_welcome_index = 0

    @bot.event
    async def on_ready():
        """Called when the bot is ready"""
        logger.info(f"🤖 Bot is ready! Logged in as {bot.user}")
        logger.info(f"📊 Connected to {len(bot.guilds)} guilds")
        
        # Load cogs
        await load_cogs(bot)
        
        # Cache invites for all guilds
        for guild in bot.guilds:
            try:
                invites = await guild.invites()
                bot.invite_cache[guild.id] = invites
                logger.info(f"📋 Cached {len(invites)} invites for {guild.name}")
            except Exception as e:
                logger.warning(f"Could not cache invites for {guild.name}: {str(e)}")
        
        # Initialize guild configs
        for guild in bot.guilds:
            try:
                config = await get_guild_config(bot.guild_configs, str(guild.id))
                if not config:
                    # Create default config
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
        
        # Start background tasks only once
        if not bot.tasks_started:
            bot.loop.create_task(check_birthdays_at_midnight())
            bot.loop.create_task(check_daily_events_at_8am())
            
            logger.info("🎂 Birthday check task started")
            logger.info("📅 Daily events check task started (8 AM)")
            
            # Calculate time until next midnight
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
        """Called when the bot disconnects"""
        logger.warning("🔌 Bot disconnected from Discord")
        
        # Close MongoDB connection
        if hasattr(bot, 'mongo_client'):
            try:
                bot.mongo_client.close()
                logger.info("🔌 MongoDB connection closed")
            except Exception as e:
                logger.error(f"Error closing MongoDB connection: {str(e)}")

    @bot.event
    async def on_member_join(member):
        """Handle member join with beautiful welcome message"""
        try:
            guild = member.guild
            
            # Get guild config
            config = await bot.guild_configs.find_one({"guild_id": str(guild.id)})
            if not config or not config.get('welcome_channel_id'):
                return
            
            welcome_channel = bot.get_channel(int(config['welcome_channel_id']))
            if not welcome_channel:
                return
            
            # Create simple and respectful welcome embed
            embed = discord.Embed(
                title=f"🌟 Welcome {member.display_name}!",
                description=f"We're delighted to have you join our wonderful community! Your presence here is truly valued and we're excited to have you as part of our server family.",
                color=discord.Color.gold(),
                timestamp=datetime.now(IST)
            )
            
            # Set thumbnail to member's avatar
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            
            # Set footer
            embed.set_footer(
                text=f"Welcome to {guild.name} • We're glad you're here! ✨",
                icon_url=guild.icon.url if guild.icon else None
            )
            
            # Add server banner if available
            if guild.banner:
                embed.set_image(url=guild.banner.url)
            
            await welcome_channel.send(content="@everyone", embed=embed)
            logger.info(f'👋 Sent welcome message for {member.display_name} in {guild.name}')
            
        except Exception as e:
            logger.error(f'❌ Error sending welcome message: {str(e)}')

    @bot.event
    async def on_member_remove(member):
        """Handle member leave with logging"""
        try:
            guild = member.guild
            
            # Get guild config
            config = await bot.guild_configs.find_one({"guild_id": str(guild.id)})
            if not config or not config.get('log_channel_id'):
                return
            
            log_channel = bot.get_channel(int(config['log_channel_id']))
            if not log_channel:
                return
            
            # Create leave embed
            embed = discord.Embed(
                title="👋 Member Left",
                description=f"**{member.display_name}** has left **{guild.name}**",
                color=discord.Color.red(),
                timestamp=datetime.now(IST)
            )
            
            embed.add_field(
                name="👤 Member Info",
                value=f"**Name:** {member.display_name}\n**Joined:** <t:{int(member.joined_at.timestamp()) if member.joined_at else 0}:R>\n**Account Created:** <t:{int(member.created_at.timestamp())}:R>",
                inline=True
            )
            
            embed.add_field(
                name="📊 Server Stats",
                value=f"**Remaining Members:** {guild.member_count}\n**Left At:** <t:{int(datetime.now(IST).timestamp())}:F>",
                inline=True
            )
            
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            embed.set_footer(text=f"Member left • {guild.name}")
            
            await log_channel.send(embed=embed)
            logger.info(f'👋 Logged member leave: {member.display_name} from {guild.name}')
            
        except Exception as e:
            logger.error(f'❌ Error logging member leave: {str(e)}')

    @bot.event
    async def on_invite_create(invite):
        """Track new invites"""
        guild_id = invite.guild.id
        if guild_id not in bot.invite_cache:
            bot.invite_cache[guild_id] = {}
        bot.invite_cache[guild_id][invite.code] = invite
        logger.info(f'📝 New invite created: {invite.code} for {invite.guild.name}')

    @bot.event
    async def on_invite_delete(invite):
        """Track deleted invites"""
        guild_id = invite.guild.id
        if guild_id in bot.invite_cache and invite.code in bot.invite_cache[guild_id]:
            del bot.invite_cache[guild_id][invite.code]
            logger.info(f'🗑️ Invite deleted: {invite.code} from {invite.guild.name}')

    @bot.event
    async def on_command_error(ctx, error):
        """Handle command errors and show helpful templates"""
        if isinstance(error, commands.CommandNotFound):
            # Check if the command exists in our templates
            command = ctx.message.content.split()[0][1:].lower()  # Remove '!' and get command name
            
            # Only show template if this is an incomplete command
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
        
        # For other errors, log them
        logger.error(f"Command error: {error}")

    @bot.event
    async def on_message(message):
        """Handle message events for autocomplete"""
        # Process commands first
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
                
                # Send the template info
                try:
                    await message.channel.send(embed=embed, delete_after=10)
                except:
                    pass  # Ignore if we can't send the message

    return bot

async def load_cogs(bot):
    """Load all cogs"""
    cogs = [
        'cogs.config',
        'cogs.birthday',
        'cogs.events',
        'cogs.help',
        'cogs.sync',
        'cogs.announce'
    ]
    
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            logger.info(f'✅ Loaded cog: {cog}')
        except Exception as e:
            logger.error(f'❌ Failed to load cog {cog}: {str(e)}')
    
    logger.info('�� All cogs loaded')
