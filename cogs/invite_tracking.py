#!/usr/bin/env python3
"""
Invite Tracking Cog - Member Join/Leave Tracking and Invite Statistics

This cog handles all invite-related functionality including:
- Tracking member joins and identifying who invited them
- Logging member leaves with role information
- Managing invite cache for accurate tracking
- Providing invite statistics and analytics
- Welcome message system for new members

The cog provides comprehensive invite tracking that helps server admins
understand their server growth and member acquisition patterns.
"""

import discord
from discord.ext import commands
import logging
from datetime import datetime
from utils.timezone import IST

logger = logging.getLogger(__name__)

class InviteTrackingCog(commands.Cog):
    """
    Invite tracking cog that handles member join/leave events and invite statistics
    
    This cog provides:
    - Automatic tracking of who invited each new member
    - Member join/leave logging
    - Invite statistics and analytics
    - Welcome message system
    - Invite cache management
    """
    
    def __init__(self, bot):
        """
        Initialize the invite tracking cog
        
        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        logger.info("Invite tracking cog initialized")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the cog is ready and loaded"""
        logger.info("Invite tracking cog ready")
    
    # ============================================================================
    # MEMBER JOIN TRACKING SECTION
    # ============================================================================
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """
        Handle member join events and track who invited them
        
        This event handler:
        1. Detects when a new member joins the server
        2. Compares current invites with cached invites to find who invited them
        3. Logs the join event with inviter information
        4. Sends a welcome message if configured
        5. Updates the invite cache for future tracking
        
        Args:
            member: The Discord member who joined
        """
        try:
            guild = member.guild
            invite_used = None
            inviter = None
            
            # ============================================================================
            # INVITE DETECTION SECTION
            # ============================================================================
            
            # Check invites to find who invited the user
            try:
                # Get current invites from Discord
                current_invites = await guild.invites()
                
                # Compare with cached invites to find which one was used
                if guild.id in self.bot.invite_cache:
                    for invite in current_invites:
                        cached_invite = self.bot.invite_cache[guild.id].get(invite.code)
                        if cached_invite and invite.uses > cached_invite.uses:
                            # This invite was used (usage count increased)
                            invite_used = invite
                            inviter = invite.inviter
                            break
                
                # Update invite cache with current invites
                self.bot.invite_cache[guild.id] = {invite.code: invite for invite in current_invites}
                
            except Exception as e:
                logger.warning(f"Could not track invite for {member.display_name}: {str(e)}")
            
            # ============================================================================
            # LOG CHANNEL SECTION
            # ============================================================================
            
            # Get log channel from guild configuration
            config = await self.bot.guild_configs.find_one({"guild_id": str(guild.id)})
            log_channel_id = config.get('log_channel_id') if config else None
            
            if log_channel_id:
                log_channel = self.bot.get_channel(int(log_channel_id))
                if log_channel:
                    # Create log message with mentions
                    if inviter:
                        msg = f"{member.mention} joined (invited by {inviter.mention})"
                    else:
                        msg = f"{member.mention} joined (inviter unknown)"
                    
                    await log_channel.send(msg)
                    logger.info(f'📝 Logged member join: {msg}')

            # ============================================================================
            # WELCOME MESSAGE SECTION
            # ============================================================================
            
            # Get welcome channel from guild configuration
            welcome_channel_id = config.get('welcome_channel_id') if config else None
            if welcome_channel_id:
                welcome_channel = self.bot.get_channel(int(welcome_channel_id))
                if welcome_channel:
                    # Create welcome embed with member information
                    embed = discord.Embed(
                        title="🌟 Welcome!",
                        description=f"{member.mention}, we're delighted to have you join our wonderful community! Your presence here is truly valued and we're excited to have you as part of our server family.",
                        color=discord.Color.gold(),
                        timestamp=datetime.now(IST)
                    )
                    
                    # Set member's avatar as thumbnail
                    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
                    
                    # Set footer with server information
                    embed.set_footer(
                        text=f"Welcome to {guild.name} • We're glad you're here! ✨",
                        icon_url=guild.icon.url if guild.icon else None
                    )
                    
                    # Add server banner if available
                    if guild.banner:
                        embed.set_image(url=guild.banner.url)
                    
                    # Send welcome message with @everyone mention
                    await welcome_channel.send(content="@everyone", embed=embed)
                    logger.info(f'👋 Sent welcome message for {member.display_name} in {guild.name}')
                    
        except Exception as e:
            logger.error(f'❌ Error handling member join: {str(e)}')

    # ============================================================================
    # MEMBER LEAVE TRACKING SECTION
    # ============================================================================
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """
        Handle member leave events and log them
        
        This event handler:
        1. Detects when a member leaves the server
        2. Logs the leave event in the configured log channel
        3. Provides information about the member who left
        
        Args:
            member: The Discord member who left
        """
        try:
            guild = member.guild
            
            # Get log channel from guild configuration
            config = await self.bot.guild_configs.find_one({"guild_id": str(guild.id)})
            log_channel_id = config.get('log_channel_id') if config else None
            
            if log_channel_id:
                log_channel = self.bot.get_channel(int(log_channel_id))
                if log_channel:
                    # Create simple leave log message
                    msg = f"{member.mention} left"
                    await log_channel.send(msg)
                    logger.info(f'👋 Logged member leave: {msg}')
                    
        except Exception as e:
            logger.error(f'❌ Error logging member leave: {str(e)}')

    # ============================================================================
    # INVITE CACHE MANAGEMENT SECTION
    # ============================================================================
    
    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        """
        Track new invites when they are created
        
        This event handler:
        1. Detects when a new invite is created
        2. Adds it to the invite cache
        3. Logs the creation for monitoring
        
        Args:
            invite: The Discord invite that was created
        """
        guild_id = invite.guild.id
        
        # Initialize cache for guild if it doesn't exist
        if guild_id not in self.bot.invite_cache:
            self.bot.invite_cache[guild_id] = {}
        
        # Add new invite to cache
        self.bot.invite_cache[guild_id][invite.code] = invite
        logger.info(f'📝 New invite created: {invite.code} for {invite.guild.name}')

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        """
        Track deleted invites when they are removed
        
        This event handler:
        1. Detects when an invite is deleted
        2. Removes it from the invite cache
        3. Logs the deletion for monitoring
        
        Args:
            invite: The Discord invite that was deleted
        """
        guild_id = invite.guild.id
        
        # Remove invite from cache if it exists
        if guild_id in self.bot.invite_cache and invite.code in self.bot.invite_cache[guild_id]:
            del self.bot.invite_cache[guild_id][invite.code]
            logger.info(f'🗑️ Invite deleted: {invite.code} from {invite.guild.name}')

    # ============================================================================
    # INVITE STATISTICS COMMANDS SECTION
    # ============================================================================
    
    @commands.hybrid_command(name="invites", description="View invite statistics (Admin only)")
    @commands.has_permissions(administrator=True)
    async def view_invites(self, ctx):
        """
        View invite statistics for the server (Admin only)
        
        This command shows:
        - All active invites in the server
        - Who created each invite
        - Usage statistics for each invite
        - Creation dates and usage limits
        
        The invites are sorted by most used first.
        """
        try:
            guild = ctx.guild
            
            # Get current invites from Discord
            invites = await guild.invites()
            
            if not invites:
                await ctx.send("📋 No active invites found for this server.", ephemeral=True)
                return
            
            # Create embed with invite statistics
            embed = discord.Embed(
                title="🎫 Server Invites",
                description=f"Active invites for **{guild.name}**",
                color=discord.Color.blue(),
                timestamp=datetime.now(IST)
            )
            
            # Sort invites by uses (most used first)
            sorted_invites = sorted(invites, key=lambda x: x.uses, reverse=True)
            
            # Add top 10 invites to embed
            for i, invite in enumerate(sorted_invites[:10]):
                inviter_name = invite.inviter.display_name if invite.inviter else "Unknown"
                max_uses = invite.max_uses if invite.max_uses else "∞"
                uses_text = f"{invite.uses}/{max_uses}"
                
                embed.add_field(
                    name=f"#{i+1} {inviter_name}",
                    value=f"**Code:** `{invite.code}`\n**Uses:** {uses_text}\n**Created:** <t:{int(invite.created_at.timestamp())}:R>",
                    inline=True
                )
            
            # Set footer with summary information
            if len(sorted_invites) > 10:
                embed.set_footer(text=f"Showing top 10 of {len(sorted_invites)} invites")
            else:
                embed.set_footer(text=f"Total: {len(sorted_invites)} invites")
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error viewing invites: {str(e)}")

    @commands.hybrid_command(name="invitestats", description="View detailed invite statistics (Admin only)")
    @commands.has_permissions(administrator=True)
    async def invite_stats(self, ctx):
        """
        View detailed invite statistics (Admin only)
        
        This command provides comprehensive analytics including:
        - Overall server statistics (total invites, uses, inviters)
        - Per-inviter breakdown with usage statistics
        - Average uses per invite for each inviter
        - Top inviters ranking
        
        This helps identify the most effective inviters in the server.
        """
        try:
            guild = ctx.guild
            
            # Get current invites from Discord
            invites = await guild.invites()
            
            if not invites:
                await ctx.send("📋 No active invites found for this server.", ephemeral=True)
                return
            
            # ============================================================================
            # STATISTICS CALCULATION SECTION
            # ============================================================================
            
            # Calculate overall statistics
            total_uses = sum(invite.uses for invite in invites)
            total_invites = len(invites)
            
            # Group statistics by inviter
            inviter_stats = {}
            for invite in invites:
                inviter_name = invite.inviter.display_name if invite.inviter else "Unknown"
                if inviter_name not in inviter_stats:
                    inviter_stats[inviter_name] = {"invites": 0, "uses": 0}
                inviter_stats[inviter_name]["invites"] += 1
                inviter_stats[inviter_name]["uses"] += invite.uses
            
            # Sort inviters by total uses (most effective first)
            sorted_inviters = sorted(inviter_stats.items(), key=lambda x: x[1]["uses"], reverse=True)
            
            # ============================================================================
            # EMBED CREATION SECTION
            # ============================================================================
            
            # Create detailed statistics embed
            embed = discord.Embed(
                title="📊 Invite Statistics",
                description=f"Detailed invite statistics for **{guild.name}**",
                color=discord.Color.green(),
                timestamp=datetime.now(IST)
            )
            
            # Add overall statistics
            embed.add_field(
                name="📈 Overall Stats",
                value=f"**Total Invites:** {total_invites}\n**Total Uses:** {total_uses}\n**Active Inviters:** {len(inviter_stats)}",
                inline=False
            )
            
            # Add top 5 inviters with detailed statistics
            for i, (inviter_name, stats) in enumerate(sorted_inviters[:5]):
                embed.add_field(
                    name=f"#{i+1} {inviter_name}",
                    value=f"**Invites:** {stats['invites']}\n**Total Uses:** {stats['uses']}\n**Avg Uses/Invite:** {stats['uses']/stats['invites']:.1f}",
                    inline=True
                )
            
            # Set footer with summary information
            if len(sorted_inviters) > 5:
                embed.set_footer(text=f"Showing top 5 of {len(sorted_inviters)} inviters")
            else:
                embed.set_footer(text=f"Total: {len(sorted_inviters)} inviters")
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error viewing invite stats: {str(e)}")

# ============================================================================
# COG SETUP SECTION
# ============================================================================

async def setup(bot):
    """
    Setup function called by Discord.py to load this cog
    
    This function:
    1. Creates an instance of InviteTrackingCog
    2. Adds it to the bot
    3. Logs successful setup
    
    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(InviteTrackingCog(bot))
    logger.info("Invite tracking cog setup complete")
