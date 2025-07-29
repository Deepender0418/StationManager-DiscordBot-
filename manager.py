import os
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone, time  # Add these
import motor.motor_asyncio
from dotenv import load_dotenv
import asyncio
import sys

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')
WELCOME_CHANNEL_ID = int(os.getenv('WELCOME_CHANNEL_ID'))
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID'))
ANNOUNCEMENT_CHANNEL_ID = int(os.getenv('ANNOUNCEMENT_CHANNEL_ID'))

intents = discord.Intents.default()
intents.members = True
intents.invites = True
intents.message_content = True  # Privileged intent
intents.presences = False       # Not needed, keep disabled


bot = commands.Bot(command_prefix='!', intents=intents)

# MongoDB setup
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client.discord_bot
birthdays = db.birthdays
invite_logs = db.invite_logs

# Cache for invites
invite_cache = {}

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await cache_invites()
    birthday_task.start()

async def cache_invites():
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            invite_cache[guild.id] = {invite.code: invite for invite in invites}
        except discord.Forbidden:
            print(f"Missing permissions to fetch invites in {guild.name}")



@bot.event
async def on_member_join(member):
    # Welcome message
    welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
        embed = discord.Embed(
            title=f"Welcome {member.name}!",
            description=f"Thanks for joining {member.guild.name}!",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.avatar.url)
        await welcome_channel.send(f"Hello {member.mention}! 👋")
        await welcome_channel.send(embed=embed)
    
    # Invite tracking
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    new_invites = await member.guild.invites()
    inviter = None
    
    for code, invite in invite_cache[member.guild.id].items():
        for new_invite in new_invites:
            if new_invite.code == code and new_invite.uses > invite.uses:
                inviter = invite.inviter
                invite_cache[member.guild.id][code] = new_invite
                await invite_logs.insert_one({
                    "user_id": member.id,
                    "inviter_id": inviter.id,
                    "guild_id": member.guild.id,
                    "action": "join",
                    "timestamp": datetime.utcnow()
                })
                break
    
    # Log join event
    if log_channel:
        if inviter:
            msg = f"✅ **Joined**: {member.mention} (Invited by {inviter.mention})"
        else:
            msg = f"✅ **Joined**: {member.mention} (Invite source unknown)"
        await log_channel.send(msg)

@bot.event
async def on_member_remove(member):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await invite_logs.insert_one({
            "user_id": member.id,
            "guild_id": member.guild.id,
            "action": "leave",
            "timestamp": datetime.utcnow()
        })
        await log_channel.send(f"❌ **Left**: {member.mention}")

@bot.command()
@commands.has_permissions(manage_guild=True)
async def announce(ctx, *, message):
    """Send a custom announcement (Admin only)"""
    channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="📢 Announcement",
            description=message,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Announced by {ctx.author.display_name}")
        await channel.send(embed=embed)
        await ctx.send("Announcement sent!")
    else:
        await ctx.send("Announcement channel not found!")

@bot.command()
@commands.has_permissions(administrator=True)
async def setbirthday(ctx, member: discord.Member, date: str):
    """Set a user's birthday (Admin only) MM-DD format"""
    try:
        month, day = map(int, date.split('-'))
        datetime(2020, month, day)  # Validate date
        birthday = f"{month:02d}-{day:02d}"
        
        await birthdays.update_one(
            {"user_id": member.id, "guild_id": ctx.guild.id},
            {"$set": {"birthday": birthday}},
            upsert=True
        )
        
        await ctx.send(f"🎂 Birthday for {member.mention} set to {date}!")
    except (ValueError, IndexError):
        await ctx.send("Invalid date format. Use MM-DD (e.g., !setbirthday @user 12-31)")
    except Exception as e:
        await ctx.send(f"Error: {str(e)}")

@bot.command()
@commands.has_permissions(administrator=True)
async def deletebirthday(ctx, member: discord.Member):
    """Delete a user's birthday (Admin only)"""
    result = await birthdays.delete_one(
        {"user_id": member.id, "guild_id": ctx.guild.id}
    )
    if result.deleted_count > 0:
        await ctx.send(f"🎂 Birthday for {member.mention} deleted!")
    else:
        await ctx.send("No birthday record found for this user.")

@tasks.loop(time=time(hour=18, minute=30, tzinfo=timezone.utc))  # Midnight UTC
async def birthday_task():
    try:
        now = datetime.now(timezone.utc)
        today = now.strftime("%m-%d")
        
        async for record in birthdays.find({"birthday": today}):
            guild = bot.get_guild(record["guild_id"])
            if guild:
                member = guild.get_member(record["user_id"])
                if member:
                    channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
                    if channel:
                        await channel.send(f"🎉 **Happy Birthday** {member.mention}! 🥳")
    except Exception as e:
        print(f"Birthday task error: {e}")

@birthday_task.error
async def birthday_task_error(error):
    print(f"Birthday task failed: {error}")


@bot.event
async def on_invite_create(invite):
    guild_id = invite.guild.id
    if guild_id not in invite_cache:
        invite_cache[guild_id] = {}
    invite_cache[guild_id][invite.code] = invite

@bot.event
async def on_invite_delete(invite):
    guild_id = invite.guild.id
    if guild_id in invite_cache and invite.code in invite_cache[guild_id]:
        del invite_cache[guild_id][invite.code]


# pinging
from flask import Flask, request
from threading import Thread

# Flask web server for UptimeRobot pings
app = Flask('')

@app.route('/')
def home():
    print(f"[{datetime.now()}] Ping received from {request.remote_addr}")
    return "Discord Bot is Alive!"

def run_webserver():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    server_thread = Thread(target=run_webserver)
    server_thread.daemon = True
    server_thread.start()



# Start the web server
keep_alive()

# Run the bot
try:
    bot.run(TOKEN)
except discord.errors.PrivilegedIntentsRequired:
    print("\nERROR: Missing Privileged Intents!")
    print("Enable in Discord Developer Portal:")
    print("1. SERVER MEMBERS INTENT")
    print("2. MESSAGE CONTENT INTENT")
    sys.exit(1)
except Exception as e:
    print(f"Fatal error: {e}")
    sys.exit(1)
