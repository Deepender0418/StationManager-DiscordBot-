#!/usr/bin/env python3
"""
Announce Cog - Server Announcement System

This cog provides server announcement functionality for the Discord bot.
It includes features to:
- Send official server announcements
- Format announcements with rich embeds
- Target specific channels for announcements
- Provide admin-only announcement commands
- Handle announcement permissions and validation

The cog is designed to help server admins communicate important
information to their community in a professional and organized manner.
"""

import discord
from discord.ext import commands
import logging
from datetime import datetime
from utils.timezone import IST
from utils.database import get_guild_config

logger = logging.getLogger(__name__)

class AnnounceCog(commands.Cog):
    """
    Announcement management cog that handles server announcements
    
    This cog provides:
    - Official server announcement commands
    - Rich embed formatting for announcements
    - Channel targeting and validation
    - Admin permission checking
    - Professional announcement styling
    """
    
    def __init__(self, bot):
        """
        Initialize the announce cog
        
        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        logger.info("Announce cog initialized")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the cog is ready and loaded"""
        logger.info("Announce cog ready")
    
    # ============================================================================
    # ANNOUNCEMENT COMMANDS SECTION
    # ============================================================================
    
    @commands.hybrid_command(name="announce", description="Send server announcement (Admin only)")
    @commands.has_permissions(administrator=True)
    async def announce(self, ctx, *, message: str):
        """
        Send an official server announcement (Admin only)
        
        This command allows server admins to send official announcements
        to the configured announcement channel. The announcement is formatted
        as a rich embed with professional styling and includes the admin's
        information as the author.
        
        Args:
            ctx: Discord context
            message: The announcement message to send
        """
        try:
            # ============================================================================
            # CHANNEL VALIDATION SECTION
            # ============================================================================
            
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
            # ANNOUNCEMENT EMBED CREATION SECTION
            # ============================================================================
            
            # Create professional announcement embed
            embed = discord.Embed(
                title="📢 **Official Server Announcement**",
                description=message,
                color=discord.Color.red(),
                timestamp=datetime.now(IST)
            )
            
            # Add author information
            embed.set_author(
                name=f"Announcement by {ctx.author.display_name}",
                icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
            )
            
            # Add server information
            embed.set_footer(
                text=f"{ctx.guild.name} • Official Announcement",
                icon_url=ctx.guild.icon.url if ctx.guild.icon else None
            )
            
            # Add server banner if available
            if ctx.guild.banner:
                embed.set_image(url=ctx.guild.banner.url)
            
            # Send announcement with @everyone mention
            await announcement_channel.send(embed=embed)
            
            # Confirm to the admin
            await ctx.send(f"✅ Announcement sent to {announcement_channel.mention}!", ephemeral=True)
            
            logger.info(f"Announcement sent by {ctx.author.display_name} in {ctx.guild.name}")
            
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error sending announcement: {str(e)}")

    @announce.error
    async def announce_error(self, ctx, error):
        """Handle announce command errors"""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("⛔ You need administrator permissions to use this command!", ephemeral=True)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("⚠️ Please provide a message to announce!\nExample: `/announce Server maintenance at 10PM`", ephemeral=True)
        else:
            await ctx.send(f"❌ Unexpected error: {str(error)}", ephemeral=True)

# ============================================================================
# COG SETUP SECTION
# ============================================================================

async def setup(bot):
    """
    Setup function called by Discord.py to load this cog
    
    This function:
    1. Creates an instance of AnnounceCog
    2. Adds it to the bot
    3. Logs successful setup
    
    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(AnnounceCog(bot))
    logger.info("Announce cog setup complete")

