#!/usr/bin/env python3
"""
Birthday Cog - Birthday Management System

This cog handles all birthday-related functionality including:
- Setting and managing user birthdays
- Automatic birthday announcements at midnight
- Custom birthday messages
- Birthday testing and management commands
- Database operations for birthday storage

The cog provides both user commands (for setting own birthday) and admin commands
(for managing other users' birthdays).
"""

import discord
from discord.ext import commands
from datetime import datetime
from utils.timezone import IST
from utils.database import get_guild_config
import logging

logger = logging.getLogger(__name__)

class BirthdayCog(commands.Cog):
    """
    Birthday management cog that handles all birthday-related functionality
    
    This cog provides:
    - Commands for setting and managing birthdays
    - Automatic birthday announcements
    - Custom message support
    - Admin tools for birthday management
    """
    
    def __init__(self, bot):
        """
        Initialize the birthday cog
        
        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        logger.info("Birthday cog initialized")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the cog is ready and loaded"""
        logger.info("Birthday cog ready")
    
    # ============================================================================
    # AUTOMATIC BIRTHDAY ANNOUNCEMENTS SECTION
    # ============================================================================
    
    async def send_birthday_announcements(self):
        """
        Send birthday announcements for today
        
        This method:
        1. Checks the current date in IST timezone
        2. Queries the database for all birthdays on today's date
        3. Groups birthdays by guild (server)
        4. Sends personalized birthday announcements to each guild
        5. Handles custom messages and default messages
        6. Includes user avatars and personalized content
        
        This method is called automatically by the background task in bot.py
        every day at midnight.
        """
        try:
            # Get today's date in IST timezone
            today = datetime.now(IST)
            today_str = f"{today.month:02d}-{today.day:02d}"  # Format: MM-DD
            
            logger.info(f"Checking for birthdays on {today_str}")
            
            # Query database for all birthdays on today's date
            cursor = self.bot.birthdays.find({"birthday": today_str})
            birthdays = await cursor.to_list(length=None)
            
            if not birthdays:
                logger.info("No birthdays today")
                return
            
            logger.info(f"Found {len(birthdays)} birthdays today")
            
            # Group birthdays by guild (server) for efficient processing
            guild_birthdays = {}
            for birthday_doc in birthdays:
                guild_id = birthday_doc.get('guild_id')
                # Convert to string for consistent comparison
                guild_id_str = str(guild_id)
                if guild_id_str not in guild_birthdays:
                    guild_birthdays[guild_id_str] = []
                guild_birthdays[guild_id_str].append(birthday_doc)
            
            # Send announcements for each guild
            for guild_id_str, guild_birthday_list in guild_birthdays.items():
                try:
                    # Convert back to int for get_guild
                    guild_id = int(guild_id_str)
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        continue
                    
                    # Get guild configuration for announcement settings
                    config = await get_guild_config(self.bot.guild_configs, str(guild_id))
                    announcement_channel_id = config.get('announcement_channel_id') if config else None
                    default_message = config.get('birthday_message', "🎉 **Happy Birthday {USER_MENTION}!** 🎉\nHope you have an amazing day!")
                    
                    if not announcement_channel_id:
                        logger.warning(f"No announcement channel configured for guild {guild_id}")
                        continue
                    
                    announcement_channel = self.bot.get_channel(int(announcement_channel_id))
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
    
    # ============================================================================
    # BIRTHDAY COMMANDS SECTION
    # ============================================================================
    
    @commands.hybrid_command(name="birthday", description="Set birthday (Admin: @user MM-DD [message] | User: MM-DD)")
    async def set_birthday(self, ctx, user_or_date: str, date_or_message: str = None, *, custom_message: str = None):
        """
        Set birthday - Admins can set for others, users can set their own
        
        This command supports two formats:
        1. Admin format: !birthday @user MM-DD [custom_message]
        2. User format: !birthday MM-DD
        
        Args:
            ctx: Discord context
            user_or_date: Either a user mention (admin) or date (user)
            date_or_message: Date (admin) or None (user)
            custom_message: Optional custom birthday message
        """
        try:
            # Check if user is admin
            is_admin = ctx.author.guild_permissions.administrator
            
            if is_admin:
                # ============================================================================
                # ADMIN BIRTHDAY SETTING SECTION
                # ============================================================================
                
                # Admin format: !birthday @user MM-DD [custom_message]
                if not ctx.message.mentions:
                    await ctx.send("❌ Admin usage: `!birthday @user MM-DD [custom_message]`", ephemeral=True)
                    return
                
                member = ctx.message.mentions[0]
                date = user_or_date
                
                # Validate date format (MM-DD)
                try:
                    month, day = map(int, date.split('-'))
                    datetime.now(IST).replace(year=2020, month=month, day=day)
                    birthday = f"{month:02d}-{day:02d}"
                except (ValueError, AttributeError):
                    await ctx.send("❌ Invalid date format. Use MM-DD (e.g., 12-31)", ephemeral=True)
                    return
                
                # Check if birthday already exists for this user
                existing = await self.bot.birthdays.find_one({"user_id": member.id, "guild_id": ctx.guild.id})
                if existing:
                    await ctx.send(f"❌ Birthday for {member.mention} is already set to {existing.get('birthday')}!", ephemeral=True)
                    return
                
                # Save birthday to database
                await self.bot.birthdays.update_one(
                    {"user_id": member.id, "guild_id": ctx.guild.id},
                    {"$set": {"birthday": birthday, "custom_message": custom_message}},
                    upsert=True
                )
                
                # Send confirmation with preview if custom message provided
                if custom_message:
                    preview = custom_message.replace('{USER_MENTION}', member.mention).replace('{USER_NAME}', member.display_name)
                    await ctx.send(f"🎂 Birthday for {member.mention} set to {date} with custom message!\n\n**Preview:**\n{preview}")
                else:
                    await ctx.send(f"🎂 Birthday for {member.mention} set to {date}!")
                    
            else:
                # ============================================================================
                # USER BIRTHDAY SETTING SECTION
                # ============================================================================
                
                # User format: !birthday MM-DD
                date = user_or_date
                
                # Validate date format (MM-DD)
                try:
                    month, day = map(int, date.split('-'))
                    datetime.now(IST).replace(year=2020, month=month, day=day)
                    birthday = f"{month:02d}-{day:02d}"
                except (ValueError, AttributeError):
                    await ctx.send("❌ Invalid date format. Use MM-DD (e.g., 12-31)", ephemeral=True)
                    return
                
                # Check if user's birthday already exists
                existing = await self.bot.birthdays.find_one({"user_id": ctx.author.id, "guild_id": ctx.guild.id})
                if existing:
                    await ctx.send(f"❌ Your birthday is already set to {existing.get('birthday')}! Contact an admin to change it.", ephemeral=True)
                    return
                
                # Save user's own birthday to database
                await self.bot.birthdays.update_one(
                    {"user_id": ctx.author.id, "guild_id": ctx.guild.id},
                    {"$set": {"birthday": birthday}},
                    upsert=True
                )
                
                await ctx.send(f"🎂 Your birthday has been set to {date}! You'll receive birthday announcements on this date.", ephemeral=True)
                
        except Exception as e:
            # Handle database connection errors gracefully
            error_msg = str(e)
            if "Cannot use MongoClient after close" in error_msg:
                await ctx.send("❌ Database connection temporarily unavailable. Please try again in a moment.", ephemeral=True)
                logger.error(f"MongoDB connection closed while setting birthday. This may be due to a temporary disconnect.")
            else:
                await ctx.send(f"❌ Error: {error_msg}", ephemeral=True)
                logger.error(f"Error setting birthday: {error_msg}")
    
    @commands.hybrid_command(name="deletebirthday", description="Delete a user's birthday")
    @commands.has_permissions(administrator=True)
    async def delete_birthday(self, ctx, member: discord.Member):
        """
        Delete birthday for a user (Admin only)
        
        Args:
            ctx: Discord context
            member: The member whose birthday to delete
        """
        try:
            # Remove birthday from database
            result = await self.bot.birthdays.delete_one(
                {"user_id": member.id, "guild_id": ctx.guild.id}
            )
            if result.deleted_count > 0:
                await ctx.send(f"🎂 Birthday for {member.mention} deleted!")
            else:
                await ctx.send("❌ No birthday record found for this user.")
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error deleting birthday: {str(e)}")
    
    @commands.hybrid_command(name="listbirthdays", description="List all birthdays (Admin only)")
    @commands.has_permissions(administrator=True)
    async def list_birthdays(self, ctx):
        """
        List all birthdays in the server (Admin only)
        
        This command shows all configured birthdays with user names,
        dates, and custom messages in an organized embed.
        """
        try:
            # Query all birthdays for this guild
            cursor = self.bot.birthdays.find({"guild_id": ctx.guild.id})
            birthdays = await cursor.to_list(length=None)
            
            if not birthdays:
                await ctx.send("📋 No birthdays set in this server.", ephemeral=True)
                return
            
            # Create embed to display birthdays
            embed = discord.Embed(
                title="🎂 Server Birthdays",
                description=f"Found {len(birthdays)} birthday(s):",
                color=discord.Color.pink()
            )
            
            # Add each birthday to the embed
            for birthday_doc in birthdays:
                user_id = birthday_doc.get('user_id')
                birthday = birthday_doc.get('birthday')
                custom_message = birthday_doc.get('custom_message', 'No custom message')
                
                # Get user information
                user = ctx.guild.get_member(user_id)
                user_name = user.display_name if user else f"User {user_id}"
                
                embed.add_field(
                    name=f"🎈 {user_name}",
                    value=f"**Date**: {birthday}\n**Custom Message**: {custom_message}",
                    inline=False
                )
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            # Handle database connection errors gracefully
            error_msg = str(e)
            if "Cannot use MongoClient after close" in error_msg:
                await ctx.send("❌ Database connection temporarily unavailable. Please try again in a moment.", ephemeral=True)
                logger.error(f"MongoDB connection closed while listing birthdays for guild {ctx.guild.id}. This may be due to a temporary disconnect.")
            else:
                await ctx.send(f"❌ Error: {error_msg}", ephemeral=True)
                logger.error(f"Error listing birthdays: {error_msg}")

    # ============================================================================
    # TESTING COMMANDS SECTION
    # ============================================================================
    
    @commands.hybrid_command(name="testbirthday", description="Test birthday announcement (Admin only)")
    @commands.has_permissions(administrator=True)
    async def test_birthday(self, ctx, member: discord.Member = None):
        """
        Test birthday announcement for a user (Admin only)
        
        This command sends a test birthday announcement to verify that:
        1. The announcement channel is configured correctly
        2. The bot has proper permissions
        3. Custom messages work as expected
        
        Args:
            ctx: Discord context
            member: The member to test with (defaults to command author)
        """
        try:
            if member is None:
                member = ctx.author
            
            # Get guild configuration for announcement settings
            config = await get_guild_config(self.bot.guild_configs, str(ctx.guild.id))
            
            # Get announcement channel
            announcement_channel_id = config.get('announcement_channel_id') if config else None
            if not announcement_channel_id:
                await ctx.send("❌ Announcement channel not configured! Set it with `/config announcement #channel`", ephemeral=True)
                return
            
            announcement_channel = self.bot.get_channel(int(announcement_channel_id))
            if not announcement_channel:
                await ctx.send("❌ Announcement channel not found! It might have been deleted.", ephemeral=True)
                return
            
            # Get user's custom message if available
            birthday_doc = await self.bot.birthdays.find_one({"user_id": member.id, "guild_id": ctx.guild.id})
            custom_message = birthday_doc.get('custom_message') if birthday_doc else None
            default_message = config.get('birthday_message', "🎉 **Happy Birthday {USER_MENTION}!** 🎉\nThis is a test birthday announcement!")
            
            # Use custom message if available, otherwise use default
            if custom_message:
                message = custom_message.replace('{USER_MENTION}', member.mention).replace('{USER_NAME}', member.display_name)
                message += "\n\n*(This is a test with custom message)*"
            else:
                message = default_message.replace('{USER_MENTION}', member.mention).replace('{USER_NAME}', member.display_name)
                message += "\n\n*(This is a test with default message)*"
            
            # Send test birthday announcement to announcement channel
            embed = discord.Embed(
                title="🎂 Birthday Celebration! (TEST)",
                description=message,
                color=discord.Color.pink()
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            embed.set_footer(text=f"🎈 {member.display_name} is celebrating today! (Test)")
            
            # Send @everyone outside the embed, custom message inside
            await announcement_channel.send(content="@everyone", embed=embed)
            await ctx.send(f"✅ Test birthday announcement sent to {announcement_channel.mention}!", ephemeral=True)
            
        except Exception as e:
            # Handle database connection errors gracefully
            error_msg = str(e)
            if "Cannot use MongoClient after close" in error_msg:
                await ctx.send("❌ Database connection temporarily unavailable. Please try again in a moment.", ephemeral=True)
                logger.error(f"MongoDB connection closed while testing birthday. This may be due to a temporary disconnect.")
            else:
                await ctx.send(f"❌ Error: {error_msg}", ephemeral=True)
                logger.error(f"Error testing birthday: {error_msg}")

    @commands.hybrid_command(name="testautobirthday", description="Test automatic birthday check (Admin only)")
    @commands.has_permissions(administrator=True)
    async def test_auto_birthday(self, ctx):
        """
        Test the automatic birthday check system (Admin only)
        
        This command manually triggers the birthday announcement system
        to test if it works correctly without waiting for midnight.
        """
        try:
            await ctx.send("🎂 Testing automatic birthday check...", ephemeral=True)
            
            # Call the automatic birthday check
            await self.send_birthday_announcements()
            
            await ctx.send("✅ Automatic birthday check completed! Check your announcement channel.", ephemeral=True)
            
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error testing auto birthday: {str(e)}")

# ============================================================================
# COG SETUP SECTION
# ============================================================================

async def setup(bot):
    """
    Setup function called by Discord.py to load this cog
    
    This function:
    1. Creates an instance of BirthdayCog
    2. Adds it to the bot
    3. Logs successful setup
    
    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(BirthdayCog(bot))
    logger.info("Birthday cog setup complete") 
