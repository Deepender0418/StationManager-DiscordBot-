import discord
from discord.ext import commands, tasks
from datetime import datetime, time
from utils.timezone import IST
from utils import database
import logging

logger = logging.getLogger(__name__)

class BirthdayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.birthday_task.start()
        logger.info("Birthday cog initialized")
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = await database.get_guild_config(
            self.bot.guild_configs,
            str(member.guild.id)
        )
        
        # Welcome message
        welcome_channel_id = config.get('welcome_channel_id') if config else None
        if welcome_channel_id:
            welcome_channel = self.bot.get_channel(int(welcome_channel_id))
            if welcome_channel:
                avatar = member.avatar.url if member.avatar else member.default_avatar.url
                embed = discord.Embed(
                    title=f"Welcome {member.name}!",
                    description=f"Thanks for joining {member.guild.name}!",
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url=avatar)
                await welcome_channel.send(f"Hello {member.mention}! 👋")
                await welcome_channel.send(embed=embed)
        
        # Join logging
        log_channel_id = config.get('log_channel_id') if config else None
        if log_channel_id:
            log_channel = self.bot.get_channel(int(log_channel_id))
            if log_channel:
                try:
                    new_invites = await member.guild.invites()
                    inviter = None
                    
                    guild_cache = self.bot.invite_cache.get(member.guild.id, {})
                    for code, invite in guild_cache.items():
                        for new_invite in new_invites:
                            if new_invite.code == code and new_invite.uses > invite.uses:
                                inviter = invite.inviter
                                self.bot.invite_cache[member.guild.id][code] = new_invite
                                await self.bot.invite_logs.insert_one({
                                    "user_id": member.id,
                                    "inviter_id": inviter.id if inviter else None,
                                    "guild_id": member.guild.id,
                                    "action": "join",
                                    "timestamp": datetime.now(IST)
                                })
                                break
                    
                    if inviter:
                        msg = f"✅ **Joined**: {member.mention} (Invited by {inviter.mention})"
                    else:
                        msg = f"✅ **Joined**: {member.mention} (Invite source unknown)"
                    await log_channel.send(msg)
                except Exception as e:
                    logger.error(f"Error logging join: {str(e)}")
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        config = await database.get_guild_config(
            self.bot.guild_configs,
            str(member.guild.id)
        )
        
        log_channel_id = config.get('log_channel_id') if config else None
        if log_channel_id:
            log_channel = self.bot.get_channel(int(log_channel_id))
            if log_channel:
                try:
                    await self.bot.invite_logs.insert_one({
                        "user_id": member.id,
                        "guild_id": member.guild.id,
                        "action": "leave",
                        "timestamp": datetime.now(IST)
                    })
                    await log_channel.send(f"❌ **Left**: {member.mention}")
                except Exception as e:
                    logger.error(f"Error logging leave: {str(e)}")
    
    @commands.hybrid_command(name="birthday", description="Set a user's birthday")
    @commands.has_permissions(administrator=True)
    async def set_birthday(self, ctx, member: discord.Member, date: str):
        try:
            month, day = map(int, date.split('-'))
            datetime.now(IST).replace(year=2020, month=month, day=day)
            birthday = f"{month:02d}-{day:02d}"
            
            await self.bot.birthdays.update_one(
                {"user_id": member.id, "guild_id": ctx.guild.id},
                {"$set": {"birthday": birthday}},
                upsert=True
            )
            
            await ctx.send(f"🎂 Birthday for {member.mention} set to {date}!")
        except ValueError:
            await ctx.send("❌ Invalid date format. Use MM-DD (e.g., 12-31)", ephemeral=True)
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error setting birthday: {str(e)}")
    
    @commands.hybrid_command(name="deletebirthday", description="Delete a user's birthday")
    @commands.has_permissions(administrator=True)
    async def delete_birthday(self, ctx, member: discord.Member):
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
    
    @tasks.loop(time=time(hour=0, minute=0, tzinfo=IST))
    async def birthday_task(self):
        try:
            now = datetime.now(IST)
            today = now.strftime("%m-%d")
            logger.info(f"Running birthday check for {today}")
            
            async for record in self.bot.birthdays.find({"birthday": today}):
                guild = self.bot.get_guild(record["guild_id"])
                if not guild:
                    continue
                
                config = await database.get_guild_config(
                    self.bot.guild_configs,
                    str(guild.id)
                )
                
                if not config:
                    continue
                
                announcement_channel_id = config.get('announcement_channel_id')
                if not announcement_channel_id:
                    continue
                
                channel = self.bot.get_channel(int(announcement_channel_id))
                if not channel:
                    continue
                
                member = guild.get_member(record["user_id"])
                if member:
                    # Check for user-specific custom message first
                    user_custom_message = record.get("custom_message")
                    
                    if user_custom_message:
                        # Use user-specific custom message
                        message = user_custom_message
                    else:
                        # Use server default message
                        message = config.get('birthday_message', 
                            "🎉 **Happy Birthday** {USER_MENTION}! 🥳")
                    
                    # Replace placeholders
                    message = message \
                        .replace("{USER_MENTION}", member.mention) \
                        .replace("{USER_NAME}", member.display_name)
                    
                    await channel.send(message)
                    logger.info(f"Announced birthday for {member.name} in {guild.name}")
        except Exception as e:
            logger.error(f"Birthday task error: {str(e)}")
    
    @birthday_task.before_loop
    async def before_birthday_task(self):
        await self.bot.wait_until_ready()
        logger.info("Birthday task is ready")

async def setup(bot):
    await bot.add_cog(BirthdayCog(bot))
    logger.info("Birthday cog setup complete")