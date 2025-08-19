#!/usr/bin/env python3
"""
Config Cog - Server Configuration and Welcome Message Management

This cog handles all server configuration functionality including:
- Setting up channel configurations (welcome, log, announcement)
- Welcome message system with rotating messages
- Bot introduction and feature explanation
- Configuration testing and validation
- Server setup and management tools

The cog provides both configuration commands and welcome message functionality
to help server admins set up their bot properly.
"""

import discord
from discord.ext import commands
import logging
from utils.database import get_guild_config
from utils.timezone import IST
from datetime import datetime

logger = logging.getLogger(__name__)

class ConfigCog(commands.Cog):
    """
    Configuration management cog that handles server setup and welcome messages
    
    This cog provides:
    - Channel configuration commands
    - Welcome message system with rotation
    - Bot introduction functionality
    - Configuration testing tools
    - Server management utilities
    """
    
    def __init__(self, bot):
        """
        Initialize the config cog
        
        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        logger.info("Config cog initialized")
        
        # ============================================================================
        # WELCOME MESSAGE SYSTEM SECTION
        # ============================================================================
        
        # Array of different welcome messages that rotate
        # This provides variety in welcome messages to make them feel more personal
        self.welcome_messages = [
            "We're delighted to have you join our community! Your presence here is truly valued. Welcome aboard, and we hope you have an amazing time with us! 🌟",
            "Welcome to our wonderful community! We're so excited to have you here. Your journey with us begins now, and we can't wait to see what you'll bring to our server! ✨",
            "A warm welcome to our newest member! You've just joined an amazing community filled with wonderful people. We're thrilled to have you here! 🎉",
            "Welcome aboard! You've found your way to our special community, and we're absolutely delighted to have you here. Let's make some amazing memories together! 🌈",
            "Hello and welcome! You've just joined a fantastic community where everyone is valued and appreciated. We're so glad you're here! 🎊",
            "Welcome to our family! You've just become part of something truly special. We're excited to get to know you and share this amazing journey together! 💫",
            "A heartfelt welcome to our newest member! You've joined a community that values friendship, respect, and fun. We're so happy you're here! 🌟",
            "Welcome to our wonderful server! You've just stepped into a community filled with amazing people and great vibes. We're excited to have you here! ✨"
        ]
        self.current_welcome_index = 0  # Track which message to use next
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the cog is ready and loaded"""
        logger.info("Config cog ready")
    
    # ============================================================================
    # CONFIGURATION COMMANDS SECTION
    # ============================================================================
    
    @commands.hybrid_command(name="config", description="Set channel configurations (Admin only)")
    @commands.has_permissions(administrator=True)
    async def config_command(self, ctx, config_type: str, channel: discord.TextChannel):
        """
        Set channel configuration for the server (Admin only)
        
        This command allows admins to configure which channels the bot uses for:
        - welcome: Channel for welcome messages when new members join
        - log: Channel for logging member joins/leaves and other events
        - announcement: Channel for birthday announcements and daily events
        
        Args:
            ctx: Discord context
            config_type: Type of configuration (welcome, log, announcement)
            channel: The Discord channel to use for this configuration
        """
        # Define valid configuration types
        valid_types = ['welcome', 'log', 'announcement']
        
        # Validate the configuration type
        if config_type.lower() not in valid_types:
            await ctx.send(f"❌ Invalid config type. Valid types: {', '.join(valid_types)}", ephemeral=True)
            return
        
        try:
            # Update database with new configuration
            await self.bot.guild_configs.update_one(
                {"guild_id": str(ctx.guild.id)},
                {"$set": {f"{config_type}_channel_id": str(channel.id)}},
                upsert=True  # Create new config if it doesn't exist
            )
            
            # Send confirmation message
            await ctx.send(f"✅ {config_type.title()} channel set to {channel.mention}!", ephemeral=True)
            logger.info(f"Config updated: {config_type} channel set to {channel.name} in {ctx.guild.name}")
            
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error setting config: {str(e)}")
    
    # ============================================================================
    # WELCOME MESSAGE COMMANDS SECTION
    # ============================================================================
    
    @commands.hybrid_command(name="testwelcome", description="Test welcome message (Admin only)")
    @commands.has_permissions(administrator=True)
    async def test_welcome(self, ctx):
        """
        Test the welcome message system (Admin only)
        
        This command sends a test welcome message to verify that:
        1. The welcome channel is configured correctly
        2. The bot has proper permissions
        3. The welcome message formatting works as expected
        
        The test uses the next message in the rotation to preview the variety.
        """
        try:
            # Get guild configuration for welcome channel
            config = await get_guild_config(self.bot.guild_configs, str(ctx.guild.id))
            welcome_channel_id = config.get('welcome_channel_id') if config else None
            
            if not welcome_channel_id:
                await ctx.send("❌ Welcome channel not configured! Set it with `/config welcome #channel`", ephemeral=True)
                return
            
            welcome_channel = self.bot.get_channel(int(welcome_channel_id))
            if not welcome_channel:
                await ctx.send("❌ Welcome channel not found! It might have been deleted.", ephemeral=True)
                return
            
            # ============================================================================
            # WELCOME MESSAGE CREATION SECTION
            # ============================================================================
            
            # Get rotating welcome message (next in sequence)
            welcome_message = self.welcome_messages[self.current_welcome_index]
            self.current_welcome_index = (self.current_welcome_index + 1) % len(self.welcome_messages)
            
            # Create welcome embed with member information
            embed = discord.Embed(
                title=f"🌟 Welcome {ctx.author.display_name}! (TEST)",
                description="We're delighted to have you join our wonderful community! Your presence here is truly valued and we're excited to have you as part of our server family.",
                color=discord.Color.gold(),
                timestamp=ctx.message.created_at
            )
            
            # Set thumbnail to member's avatar
            embed.set_thumbnail(url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            
            # Set footer with server information
            embed.set_footer(
                text=f"Welcome to {ctx.guild.name} • We're glad you're here! ✨ (TEST)",
                icon_url=ctx.guild.icon.url if ctx.guild.icon else None
            )
            
            # Add server banner if available
            if ctx.guild.banner:
                embed.set_image(url=ctx.guild.banner.url)
            
            # Send test welcome message
            await welcome_channel.send(content="@everyone", embed=embed)
            await ctx.send(f"✅ Test welcome message sent to {welcome_channel.mention}!", ephemeral=True)
            
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error testing welcome: {str(e)}")

    # ============================================================================
    # BOT INTRODUCTION SECTION
    # ============================================================================
    
    @commands.hybrid_command(name="botintro", description="Bot introduces itself and explains its features (Admin only)")
    @commands.has_permissions(administrator=True)
    async def introduce_bot(self, ctx):
        """
        Bot introduces itself and explains its features (Admin only)
        
        This command sends a comprehensive introduction message that:
        1. Explains what the bot does
        2. Lists all available features
        3. Provides usage instructions
        4. Creates excitement about the bot's capabilities
        
        The message is designed to be engaging and informative for server members.
        """
        try:
            # Add detailed debug log to track command calls
            logger.info(f"=== BOTINTRO COMMAND CALLED ===")
            logger.info(f"Author: {ctx.author}")
            logger.info(f"Guild: {ctx.guild}")
            logger.info(f"Channel: {ctx.channel}")
            logger.info(f"Message: {ctx.message.content}")
            logger.info(f"Command type: {type(ctx).__name__}")
            logger.info(f"Interaction: {ctx.interaction if hasattr(ctx, 'interaction') else 'None'}")
            
            # Get guild configuration for announcement channel
            config = await get_guild_config(self.bot.guild_configs, str(ctx.guild.id))
            announcement_channel_id = config.get('announcement_channel_id') if config else None
            
            if not announcement_channel_id:
                await ctx.send("❌ Announcement channel not configured! Set it with `/config announcement #channel`", ephemeral=True)
                return
            
            announcement_channel = self.bot.get_channel(int(announcement_channel_id))
            if not announcement_channel:
                await ctx.send("❌ Announcement channel not found! It might have been deleted.", ephemeral=True)
                return
            
            # ============================================================================
            # BOT INTRODUCTION EMBED CREATION SECTION
            # ============================================================================
            
            # Create casual and friendly bot introduction with inspiring quote
            embed = discord.Embed(
                title="🌟 A New Beginning Awaits! 🌟",
                description="*\"Every great journey begins with a single step, and every amazing community starts with a warm welcome.\"* ✨\n\n**Hey everyone! 👋**\n\nI'm your friendly **Server Manager Bot**, and I'm super excited to be here with you all! I'm here to make this server awesome and help create a great community experience. Here's what I can do for you:",
                color=discord.Color.purple(),
                timestamp=ctx.message.created_at
            )
            
            # Add mission statement
            embed.add_field(
                name="💫 Our Mission",
                value="*\"Building connections, celebrating moments, and creating memories together.\"*",
                inline=False
            )
            
            # ============================================================================
            # FEATURE HIGHLIGHTS SECTION
            # ============================================================================
            
            # Birthday celebrations feature
            embed.add_field(
                name="🎂 **Birthday Celebrations**",
                value="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n• 🕛 **Automatic celebrations** at midnight!\n• 📝 **Easy setup** with `/birthday MM-DD`\n• 🎨 **Beautiful announcements** with custom messages\n• 🎁 **Individual birthday cards** for each person\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                inline=False
            )
            
            # Daily events feature
            embed.add_field(
                name="📅 **Daily Events & Fun**",
                value="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n• 🌅 **Morning updates** at 8 AM every day!\n• 🎉 **Holidays & observances** to keep you informed\n• 📚 **Learn about special events** and celebrations\n• ⏰ **Never miss** a special day again!\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                inline=False
            )
            
            # Welcome system feature
            embed.add_field(
                name="🌟 **Welcome New Friends**",
                value="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n• 🤗 **Warm welcomes** for new members\n• 🎨 **Beautiful, respectful** welcome cards\n• 💝 **Makes everyone feel valued** and appreciated\n• 🌈 **Creates a friendly atmosphere** for all\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                inline=False
            )
            
            # Management tools feature
            embed.add_field(
                name="⚙️ **Easy Management**",
                value="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n• 🛠️ **Simple commands** to set up channels\n• 🌐 **Web interface** for easy configuration\n• 🧪 **Admin commands** for testing features\n• 🎯 **Everything designed** to be user-friendly\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                inline=False
            )
            
            # Add closing quote
            embed.add_field(
                name="💝 **Together We Grow**",
                value="*\"The best communities are built on friendship, celebration, and shared moments.\"* 🌟",
                inline=False
            )
            
            # Set footer with casual tone and bot information
            embed.set_footer(
                text=f"🤖 {self.bot.user.name} • Your friendly server assistant! Feel free to ask for help anytime! ✨",
                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url
            )
            
            # Send the bot introduction
            await announcement_channel.send(content="@everyone", embed=embed)
            await ctx.send(f"✅ Bot introduction sent to {announcement_channel.mention}!", ephemeral=True)
            
            logger.info(f"=== BOTINTRO COMMAND COMPLETED SUCCESSFULLY ===")
            
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error sending bot introduction: {str(e)}")

# ============================================================================
# COG SETUP SECTION
# ============================================================================

async def setup(bot):
    """
    Setup function called by Discord.py to load this cog
    
    This function:
    1. Creates an instance of ConfigCog
    2. Adds it to the bot
    3. Logs successful setup
    
    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(ConfigCog(bot))
    logger.info("Config cog setup complete")
