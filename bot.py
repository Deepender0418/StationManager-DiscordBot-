import os
import discord
from discord.ext import commands
import motor.motor_asyncio
import logging
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

def create_bot():
    # Initialize bot
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    intents.presences = False

    bot = commands.Bot(command_prefix='!', intents=intents)
    bot.help_command = None  # Disable default help command

    # Database connection
    MONGO_URI = os.getenv('MONGO_URI')
    if not MONGO_URI:
        logging.error("MONGO_URI environment variable not set!")
        exit(1)
    
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    db = client.discord_bot
    bot.guild_configs = db.guild_configs
    bot.birthdays = db.birthdays
    bot.invite_logs = db.invite_logs

    # Global invite cache
    bot.invite_cache = {}

    # Cog loader
    async def load_cogs():
        cogs = [
            'cogs.config',
            'cogs.birthdays',
            'cogs.help',
            'cogs.sync',
            'cogs.events'
        ]
        for cog in cogs:
            try:
                await bot.load_extension(cog)
                logging.info(f"Loaded cog: {cog}")
            except commands.ExtensionError as e:
                logging.error(f"Failed to load cog {cog}: {str(e)}")
            except Exception as e:
                logging.error(f"Unexpected error loading cog {cog}: {str(e)}")

    # Event handler
    @bot.event
    async def on_ready():
        logging.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
        
        # Load cogs
        await load_cogs()
        logging.info("All cogs loaded")
        
        # Initialize invite cache
        for guild in bot.guilds:
            try:
                invites = await guild.invites()
                bot.invite_cache[guild.id] = {invite.code: invite for invite in invites}
                logging.info(f'Cached {len(invites)} invites for {guild.name}')
            except discord.Forbidden:
                logging.warning(f'Missing permissions to fetch invites in {guild.name}')
        
        # Initialize guild configs
        for guild in bot.guilds:
            await bot.guild_configs.find_one_and_update(
                {"guild_id": str(guild.id)},
                {"$setOnInsert": {
                    "guild_id": str(guild.id),
                    "welcome_channel_id": None,
                    "log_channel_id": None,
                    "announcement_channel_id": None
                }},
                upsert=True
            )

    @bot.event
    async def on_invite_create(invite):
        guild_id = invite.guild.id
        if guild_id not in bot.invite_cache:
            bot.invite_cache[guild_id] = {}
        bot.invite_cache[guild_id][invite.code] = invite

    @bot.event
    async def on_invite_delete(invite):
        guild_id = invite.guild.id
        if guild_id in bot.invite_cache and invite.code in bot.invite_cache[guild_id]:
            del bot.invite_cache[guild_id][invite.code]

    @bot.hybrid_command(name="announce", description="Send an official server announcement")
    @commands.has_permissions(administrator=True)
    async def announce(ctx, *, message: str):
        """Send an announcement as the bot (Admin only)"""
        try:
            # Get guild config
            config = await db.guild_configs.find_one({"guild_id": str(ctx.guild.id)})
            
            # Check if announcement channel is set
            announcement_channel_id = config.get('announcement_channel_id') if config else None
            if not announcement_channel_id:
                await ctx.send("❌ Announcement channel not configured! Set it with `/config announcement #channel`", ephemeral=True)
                return
            
            # Get the announcement channel
            announcement_channel = bot.get_channel(int(announcement_channel_id))
            if not announcement_channel:
                await ctx.send("❌ Announcement channel not found! It might have been deleted.", ephemeral=True)
                return
            
            # Create embed for professional announcement
            embed = discord.Embed(
                title="📢 Server Announcement",
                description=message,
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Announced by {ctx.author.display_name}")
            
            # Send the announcement
            await announcement_channel.send(embed=embed)
            
            # Confirm to admin
            await ctx.send(f"✅ Announcement sent to {announcement_channel.mention}!", ephemeral=True)
            
            # Log the announcement
            log_channel_id = config.get('log_channel_id') if config else None
            if log_channel_id:
                log_channel = bot.get_channel(int(log_channel_id))
                if log_channel:
                    await log_channel.send(f"📢 **Announcement**: {ctx.author.mention} sent an announcement")
            
        except Exception as e:
            await ctx.send(f"❌ Error sending announcement: {str(e)}", ephemeral=True)
            logging.error(f"Announce command error: {str(e)}")

    # Add error handler for announce command
    @announce.error
    async def announce_error(ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("⛔ You need administrator permissions to use this command!", ephemeral=True)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("⚠️ Please provide a message to announce!\nExample: `/announce Server maintenance at 10PM`", ephemeral=True)
        else:
            await ctx.send(f"❌ Unexpected error: {str(error)}", ephemeral=True)

    return bot