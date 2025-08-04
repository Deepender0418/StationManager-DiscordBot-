#!/usr/bin/env python3
"""
Config cog - Server configuration management
"""

import discord
from discord.ext import commands
import logging
from utils.database import get_guild_config
from utils.timezone import IST
from datetime import datetime

logger = logging.getLogger(__name__)

class ConfigCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("Config cog initialized")
        
        # Array of different welcome messages that rotate
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
        self.current_welcome_index = 0
    
    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Config cog ready")
    
    @commands.hybrid_command(name="config", description="Set channel configurations (Admin only)")
    @commands.has_permissions(administrator=True)
    async def config_command(self, ctx, config_type: str, channel: discord.TextChannel):
        """Set channel configuration"""
        valid_types = ['welcome', 'log', 'announcement']
        
        if config_type.lower() not in valid_types:
            await ctx.send(f"❌ Invalid config type. Valid types: {', '.join(valid_types)}", ephemeral=True)
            return
        
        try:
            # Update database
            await self.bot.guild_configs.update_one(
                {"guild_id": str(ctx.guild.id)},
                {"$set": {f"{config_type}_channel_id": str(channel.id)}},
                upsert=True
            )
            
            await ctx.send(f"✅ {config_type.title()} channel set to {channel.mention}!", ephemeral=True)
            logger.info(f"Config updated: {config_type} channel set to {channel.name} in {ctx.guild.name}")
            
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error setting config: {str(e)}")
    
    @commands.hybrid_command(name="testwelcome", description="Test welcome message (Admin only)")
    @commands.has_permissions(administrator=True)
    async def test_welcome(self, ctx):
        """Test the welcome message"""
        try:
            # Get guild config
            config = await get_guild_config(self.bot.guild_configs, str(ctx.guild.id))
            welcome_channel_id = config.get('welcome_channel_id') if config else None
            
            if not welcome_channel_id:
                await ctx.send("❌ Welcome channel not configured! Set it with `/config welcome #channel`", ephemeral=True)
                return
            
            welcome_channel = self.bot.get_channel(int(welcome_channel_id))
            if not welcome_channel:
                await ctx.send("❌ Welcome channel not found! It might have been deleted.", ephemeral=True)
                return
            
            # Get rotating welcome message
            welcome_message = self.welcome_messages[self.current_welcome_index]
            self.current_welcome_index = (self.current_welcome_index + 1) % len(self.welcome_messages)
            
            # Create simple welcome embed (test version)
            embed = discord.Embed(
                title=f"🌟 Welcome {ctx.author.display_name}! (TEST)",
                description="We're delighted to have you join our wonderful community! Your presence here is truly valued and we're excited to have you as part of our server family.",
                color=discord.Color.gold(),
                timestamp=ctx.message.created_at
            )
            
            # Set thumbnail to member's avatar
            embed.set_thumbnail(url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            
            # Set footer
            embed.set_footer(
                text=f"Welcome to {ctx.guild.name} • We're glad you're here! ✨ (TEST)",
                icon_url=ctx.guild.icon.url if ctx.guild.icon else None
            )
            
            # Add server banner if available
            if ctx.guild.banner:
                embed.set_image(url=ctx.guild.banner.url)
            
            await welcome_channel.send(content="@everyone", embed=embed)
            await ctx.send(f"✅ Test welcome message sent to {welcome_channel.mention}!", ephemeral=True)
            
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error testing welcome: {str(e)}")

    @commands.hybrid_command(name="botintro", description="Bot introduces itself and explains its features (Admin only)")
    @commands.has_permissions(administrator=True)
    async def introduce_bot(self, ctx):
        """Bot introduces itself and explains its features"""
        try:
            # Add detailed debug log to track command calls
            logger.info(f"=== BOTINTRO COMMAND CALLED ===")
            logger.info(f"Author: {ctx.author}")
            logger.info(f"Guild: {ctx.guild}")
            logger.info(f"Channel: {ctx.channel}")
            logger.info(f"Message: {ctx.message.content}")
            logger.info(f"Command type: {type(ctx).__name__}")
            logger.info(f"Interaction: {ctx.interaction if hasattr(ctx, 'interaction') else 'None'}")
            
            # Get guild config
            config = await get_guild_config(self.bot.guild_configs, str(ctx.guild.id))
            announcement_channel_id = config.get('announcement_channel_id') if config else None
            
            if not announcement_channel_id:
                await ctx.send("❌ Announcement channel not configured! Set it with `/config announcement #channel`", ephemeral=True)
                return
            
            announcement_channel = self.bot.get_channel(int(announcement_channel_id))
            if not announcement_channel:
                await ctx.send("❌ Announcement channel not found! It might have been deleted.", ephemeral=True)
                return
            
            # Create casual and friendly bot introduction with new beginning quote
            embed = discord.Embed(
                title="🌟 A New Beginning Awaits! 🌟",
                description="*\"Every great journey begins with a single step, and every amazing community starts with a warm welcome.\"* ✨\n\n**Hey everyone! 👋**\n\nI'm your friendly **Server Manager Bot**, and I'm super excited to be here with you all! I'm here to make this server awesome and help create a great community experience. Here's what I can do for you:",
                color=discord.Color.purple(),
                timestamp=ctx.message.created_at
            )
            
            # Add a beautiful quote section
            embed.add_field(
                name="💫 Our Mission",
                value="*\"Building connections, celebrating moments, and creating memories together.\"*",
                inline=False
            )
            
            # Casual features with bullet points and better formatting
            embed.add_field(
                name="🎂 **Birthday Celebrations**",
                value="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n• 🕛 **Automatic celebrations** at midnight!\n• 📝 **Easy setup** with `/birthday MM-DD`\n• 🎨 **Beautiful announcements** with custom messages\n• 🎁 **Individual birthday cards** for each person\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                inline=False
            )
            
            embed.add_field(
                name="📅 **Daily Events & Fun**",
                value="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n• 🌅 **Morning updates** at 8 AM every day!\n• 🎉 **Holidays & observances** to keep you informed\n• 📚 **Learn about special events** and celebrations\n• ⏰ **Never miss** a special day again!\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                inline=False
            )
            
            embed.add_field(
                name="🌟 **Welcome New Friends**",
                value="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n• 🤗 **Warm welcomes** for new members\n• 🎨 **Beautiful, respectful** welcome cards\n• 💝 **Makes everyone feel valued** and appreciated\n• 🌈 **Creates a friendly atmosphere** for all\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                inline=False
            )
            
            embed.add_field(
                name="⚙️ **Easy Management**",
                value="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n• 🛠️ **Simple commands** to set up channels\n• 🌐 **Web interface** for easy configuration\n• 🧪 **Admin commands** for testing features\n• 🎯 **Everything designed** to be user-friendly\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                inline=False
            )
            
            # Add a closing quote
            embed.add_field(
                name="💝 **Together We Grow**",
                value="*\"The best communities are built on friendship, celebration, and shared moments.\"* 🌟",
                inline=False
            )
            
            # Set footer with casual tone and better formatting
            embed.set_footer(
                text=f"🤖 {self.bot.user.name} • Your friendly server assistant! Feel free to ask for help anytime! ✨",
                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url
            )
            
            await announcement_channel.send(content="@everyone", embed=embed)
            await ctx.send(f"✅ Bot introduction sent to {announcement_channel.mention}!", ephemeral=True)
            
            logger.info(f"=== BOTINTRO COMMAND COMPLETED SUCCESSFULLY ===")
            
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error sending bot introduction: {str(e)}")

    @commands.hybrid_command(name="invites", description="View invite statistics (Admin only)")
    @commands.has_permissions(administrator=True)
    async def view_invites(self, ctx):
        """View invite statistics for the server"""
        try:
            guild = ctx.guild
            
            # Get current invites
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
            
            for i, invite in enumerate(sorted_invites[:10]):  # Show top 10 invites
                inviter_name = invite.inviter.display_name if invite.inviter else "Unknown"
                max_uses = invite.max_uses if invite.max_uses else "∞"
                uses_text = f"{invite.uses}/{max_uses}"
                
                embed.add_field(
                    name=f"#{i+1} {inviter_name}",
                    value=f"**Code:** `{invite.code}`\n**Uses:** {uses_text}\n**Created:** <t:{int(invite.created_at.timestamp())}:R>",
                    inline=True
                )
            
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
        """View detailed invite statistics"""
        try:
            guild = ctx.guild
            
            # Get current invites
            invites = await guild.invites()
            
            if not invites:
                await ctx.send("📋 No active invites found for this server.", ephemeral=True)
                return
            
            # Calculate statistics
            total_uses = sum(invite.uses for invite in invites)
            total_invites = len(invites)
            
            # Group by inviter
            inviter_stats = {}
            for invite in invites:
                inviter_name = invite.inviter.display_name if invite.inviter else "Unknown"
                if inviter_name not in inviter_stats:
                    inviter_stats[inviter_name] = {"invites": 0, "uses": 0}
                inviter_stats[inviter_name]["invites"] += 1
                inviter_stats[inviter_name]["uses"] += invite.uses
            
            # Sort by total uses
            sorted_inviters = sorted(inviter_stats.items(), key=lambda x: x[1]["uses"], reverse=True)
            
            embed = discord.Embed(
                title="📊 Invite Statistics",
                description=f"Detailed invite statistics for **{guild.name}**",
                color=discord.Color.green(),
                timestamp=datetime.now(IST)
            )
            
            embed.add_field(
                name="📈 Overall Stats",
                value=f"**Total Invites:** {total_invites}\n**Total Uses:** {total_uses}\n**Active Inviters:** {len(inviter_stats)}",
                inline=False
            )
            
            # Show top inviters
            for i, (inviter_name, stats) in enumerate(sorted_inviters[:5]):
                embed.add_field(
                    name=f"#{i+1} {inviter_name}",
                    value=f"**Invites:** {stats['invites']}\n**Total Uses:** {stats['uses']}\n**Avg Uses/Invite:** {stats['uses']/stats['invites']:.1f}",
                    inline=True
                )
            
            if len(sorted_inviters) > 5:
                embed.set_footer(text=f"Showing top 5 of {len(sorted_inviters)} inviters")
            else:
                embed.set_footer(text=f"Total: {len(sorted_inviters)} inviters")
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error viewing invite stats: {str(e)}")

async def setup(bot):
    await bot.add_cog(ConfigCog(bot))
    logger.info("Config cog setup complete")
