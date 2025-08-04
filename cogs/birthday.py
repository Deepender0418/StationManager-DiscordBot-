#!/usr/bin/env python3
"""
Birthday cog - Simple birthday management
"""

import discord
from discord.ext import commands
from datetime import datetime
from utils.timezone import IST
from utils.database import get_guild_config
import logging

logger = logging.getLogger(__name__)

class BirthdayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("Birthday cog initialized")
    
    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Birthday cog ready")
    
    @commands.hybrid_command(name="birthday", description="Set birthday (Admin: @user MM-DD [message] | User: MM-DD)")
    async def set_birthday(self, ctx, user_or_date: str, date_or_message: str = None, *, custom_message: str = None):
        """Set birthday - Admins can set for others, users can set their own"""
        try:
            # Check if user is admin
            is_admin = ctx.author.guild_permissions.administrator
            
            if is_admin:
                # Admin format: !birthday @user MM-DD [custom_message]
                if not ctx.message.mentions:
                    await ctx.send("❌ Admin usage: `!birthday @user MM-DD [custom_message]`", ephemeral=True)
                    return
                
                member = ctx.message.mentions[0]
                date = user_or_date
                
                # Validate date format
                try:
                    month, day = map(int, date.split('-'))
                    datetime.now(IST).replace(year=2020, month=month, day=day)
                    birthday = f"{month:02d}-{day:02d}"
                except (ValueError, AttributeError):
                    await ctx.send("❌ Invalid date format. Use MM-DD (e.g., 12-31)", ephemeral=True)
                    return
                
                # Check if birthday already exists
                existing = await self.bot.birthdays.find_one({"user_id": member.id, "guild_id": ctx.guild.id})
                if existing:
                    await ctx.send(f"❌ Birthday for {member.mention} is already set to {existing.get('birthday')}!", ephemeral=True)
                    return
                
                # Save birthday
                await self.bot.birthdays.update_one(
                    {"user_id": member.id, "guild_id": ctx.guild.id},
                    {"$set": {"birthday": birthday, "custom_message": custom_message}},
                    upsert=True
                )
                
                if custom_message:
                    preview = custom_message.replace('{USER_MENTION}', member.mention).replace('{USER_NAME}', member.display_name)
                    await ctx.send(f"🎂 Birthday for {member.mention} set to {date} with custom message!\n\n**Preview:**\n{preview}")
                else:
                    await ctx.send(f"🎂 Birthday for {member.mention} set to {date}!")
                    
            else:
                # User format: !birthday MM-DD
                date = user_or_date
                
                # Validate date format
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
                
                # Save user's own birthday
                await self.bot.birthdays.update_one(
                    {"user_id": ctx.author.id, "guild_id": ctx.guild.id},
                    {"$set": {"birthday": birthday}},
                    upsert=True
                )
                
                await ctx.send(f"🎂 Your birthday has been set to {date}! You'll receive birthday announcements on this date.", ephemeral=True)
                
        except Exception as e:
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
        """Delete birthday for a user"""
        try:
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
        """List all birthdays in the server"""
        try:
            cursor = self.bot.birthdays.find({"guild_id": ctx.guild.id})
            birthdays = await cursor.to_list(length=None)
            
            if not birthdays:
                await ctx.send("📋 No birthdays set in this server.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🎂 Server Birthdays",
                description=f"Found {len(birthdays)} birthday(s):",
                color=discord.Color.pink()
            )
            
            for birthday_doc in birthdays:
                user_id = birthday_doc.get('user_id')
                birthday = birthday_doc.get('birthday')
                custom_message = birthday_doc.get('custom_message', 'No custom message')
                
                user = ctx.guild.get_member(user_id)
                user_name = user.display_name if user else f"User {user_id}"
                
                embed.add_field(
                    name=f"🎈 {user_name}",
                    value=f"**Date**: {birthday}\n**Custom Message**: {custom_message}",
                    inline=False
                )
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            error_msg = str(e)
            if "Cannot use MongoClient after close" in error_msg:
                await ctx.send("❌ Database connection temporarily unavailable. Please try again in a moment.", ephemeral=True)
                logger.error(f"MongoDB connection closed while listing birthdays for guild {ctx.guild.id}. This may be due to a temporary disconnect.")
            else:
                await ctx.send(f"❌ Error: {error_msg}", ephemeral=True)
                logger.error(f"Error listing birthdays: {error_msg}")

    @commands.hybrid_command(name="testbirthday", description="Test birthday announcement (Admin only)")
    @commands.has_permissions(administrator=True)
    async def test_birthday(self, ctx, member: discord.Member = None):
        """Test birthday announcement for a user"""
        try:
            if member is None:
                member = ctx.author
            
            # Get guild config
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
        """Test the automatic birthday check system"""
        try:
            await ctx.send("🎂 Testing automatic birthday check...", ephemeral=True)
            
            # Import the function from bot.py
            from bot import send_birthday_announcements
            
            # Call the automatic birthday check
            await send_birthday_announcements(self.bot)
            
            await ctx.send("✅ Automatic birthday check completed! Check your announcement channel.", ephemeral=True)
            
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error testing auto birthday: {str(e)}")

async def setup(bot):
    await bot.add_cog(BirthdayCog(bot))
    logger.info("Birthday cog setup complete") 
