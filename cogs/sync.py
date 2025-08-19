#!/usr/bin/env python3
"""
Sync Cog - Command Synchronization System

This cog handles Discord slash command synchronization for the bot.
It provides functionality to:
- Sync slash commands with Discord's API
- Update command definitions and permissions
- Handle command registration and updates
- Provide owner-only sync commands
- Manage command synchronization errors

The cog is essential for ensuring that slash commands are properly
registered and updated with Discord's servers.
"""

import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class SyncCog(commands.Cog):
    """
    Command synchronization cog that handles slash command management
    
    This cog provides:
    - Slash command synchronization with Discord
    - Command registration and updates
    - Owner-only sync functionality
    - Error handling for sync operations
    """
    
    def __init__(self, bot):
        """
        Initialize the sync cog
        
        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        logger.info("Sync cog initialized")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the cog is ready and loaded"""
        logger.info("Sync cog ready")
    
    # ============================================================================
    # SYNCHRONIZATION COMMANDS SECTION
    # ============================================================================
    
    @commands.hybrid_command(name="sync", description="Sync slash commands (Owner only)")
    @commands.is_owner()
    async def sync_commands(self, ctx):
        """
        Sync slash commands with Discord (Owner only)
        
        This command synchronizes all slash commands with Discord's servers.
        It's typically used when:
        - New commands are added to the bot
        - Command descriptions or parameters are changed
        - Commands need to be updated across all servers
        
        This command requires bot owner permissions and should be used
        carefully as it affects all servers where the bot is present.
        """
        try:
            # ============================================================================
            # SYNCHRONIZATION PROCESS SECTION
            # ============================================================================
            
            await ctx.send("🔄 Syncing slash commands with Discord...", ephemeral=True)
            
            # Sync commands with Discord
            # This updates all slash commands across all servers
            synced = await self.bot.tree.sync()
            
            # Log the sync operation
            logger.info(f"Synced {len(synced)} command(s) with Discord")
            
            # Confirm successful sync
            await ctx.send(f"✅ Successfully synced {len(synced)} command(s) with Discord!", ephemeral=True)
            
        except Exception as e:
            await ctx.send(f"❌ Error syncing commands: {str(e)}", ephemeral=True)
            logger.error(f"Error syncing commands: {str(e)}")

# ============================================================================
# COG SETUP SECTION
# ============================================================================

async def setup(bot):
    """
    Setup function called by Discord.py to load this cog
    
    This function:
    1. Creates an instance of SyncCog
    2. Adds it to the bot
    3. Logs successful setup
    
    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(SyncCog(bot))
    logger.info("Sync cog setup complete")
