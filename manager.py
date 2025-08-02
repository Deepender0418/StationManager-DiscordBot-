import os
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone, time
import motor.motor_asyncio
from dotenv import load_dotenv
import asyncio
import sys
from flask import Flask, request, render_template, redirect, url_for
from threading import Thread
import logging
import json
from bson import ObjectId

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')
ADMIN_SECRET = os.getenv('ADMIN_SECRET', 'default-secret')

# Create IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# Set up logging with IST timezone
class ISTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, IST)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)
ist_formatter = ISTFormatter(
    fmt='%(asctime)s IST - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
for handler in logging.getLogger().handlers:
    handler.setFormatter(ist_formatter)

# Flask setup
app = Flask(__name__)
app.secret_key = ADMIN_SECRET

# MongoDB setup
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client.discord_bot
guild_configs = db.guild_configs
birthdays = db.birthdays
invite_logs = db.invite_logs

# Discord bot setup
intents = discord.Intents.default()
intents.members = True
intents.invites = True
intents.message_content = True
intents.presences = False

bot = commands.Bot(command_prefix='!', intents=intents)

# Cache for invites
invite_cache = {}

# =====================================
# HELPER FUNCTIONS
# =====================================

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return super().default(o)

async def get_guild_config(guild_id):
    config = await guild_configs.find_one({"guild_id": str(guild_id)})
    if not config:
        default_config = {
            "guild_id": str(guild_id),
            "welcome_channel_id": None,
            "log_channel_id": None,
            "announcement_channel_id": None
        }
        await guild_configs.insert_one(default_config)
        return default_config
    return config

async def update_guild_config(guild_id, updates):
    await guild_configs.update_one(
        {"guild_id": str(guild_id)},
        {"$set": updates},
        upsert=True
    )

# =====================================
# FLASK ROUTES (WEB DASHBOARD)
# =====================================

@app.route('/')
def home():
    return "Discord Bot is Alive!"

@app.route('/config/<guild_id>', methods=['GET', 'POST'])
def guild_config(guild_id):
    if request.method == 'POST':
        updates = {
            "welcome_channel_id": request.form.get('welcome_channel'),
            "log_channel_id": request.form.get('log_channel'),
            "announcement_channel_id": request.form.get('announcement_channel')
        }
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(update_guild_config(guild_id, updates))
        loop.close()
        return redirect(url_for('guild_config', guild_id=guild_id))
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    config = loop.run_until_complete(get_guild_config(guild_id))
    guild = bot.get_guild(int(guild_id))
    channels = [{"id": str(c.id), "name": c.name} for c in guild.text_channels] if guild else []
    loop.close()
    
    return render_template('config.html', 
                         guild_id=guild_id,
                         guild_name=guild.name if guild else "Unknown Server",
                         config=config,
                         channels=channels)

@app.route('/status')
def status():
    utc_now = datetime.now(timezone.utc)
    ist_now = datetime.now(IST)
    
    return {
        "status": "online",
        "bot": str(bot.user),
        "uptime": str(datetime.now(IST) - start_time),
        "timezones": {
            "UTC": utc_now.strftime("%Y-%m-%d %H:%M:%S"),
            "IST": ist_now.strftime("%Y-%m-%d %H:%M:%S")
        },
        "next_birthday_check": ist_now.replace(hour=0, minute=0, second=0) + timedelta(days=1)
    }

@app.route('/debug')
def debug_info():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    all_configs = list(loop.run_until_complete(guild_configs.find().to_list(None)))
    loop.close()
    
    configs_json = JSONEncoder().encode(all_configs)
    
    return f"""
    <h1>Debug Information</h1>
    <p>Bot Status: {'Online' if bot.is_ready() else 'Offline'}</p>
    <p>Guilds: {len(bot.guilds)}</p>
    <h2>Server Configurations:</h2>
    <pre>{json.dumps(json.loads(configs_json), indent=2)}</pre>
    """

# =====================================
# DISCORD BOT EVENTS AND COMMANDS
# =====================================

start_time = datetime.now(IST)

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')
    await cache_invites()
    if not birthday_task.is_running():
        birthday_task.start()
    
    for guild in bot.guilds:
        logger.info(f'Connected to: {guild.name} (ID: {guild.id})')
        await get_guild_config(guild.id)

async def cache_invites():
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            invite_cache[guild.id] = {invite.code: invite for invite in invites}
            logger.info(f'Cached {len(invites)} invites for {guild.name}')
        except discord.Forbidden:
            logger.warning(f'Missing permissions to fetch invites in {guild.name}')

@bot.event
async def on_member_join(member):
    config = await get_guild_config(member.guild.id)
    welcome_channel_id = config.get('welcome_channel_id')
    
    if welcome_channel_id:
        welcome_channel = bot.get_channel(int(welcome_channel_id))
        if welcome_channel:
            embed = discord.Embed(
                title=f"Welcome {member.name}!",
                description=f"Thanks for joining {member.guild.name}!",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=member.avatar.url)
            await welcome_channel.send(f"Hello {member.mention}! 👋")
            await welcome_channel.send(embed=embed)
    
    config = await get_guild_config(member.guild.id)
    log_channel_id = config.get('log_channel_id')
    
    if log_channel_id:
        log_channel = bot.get_channel(int(log_channel_id))
        if log_channel:
            new_invites = await member.guild.invites()
            inviter = None
            
            guild_cache = invite_cache.get(member.guild.id, {})
            for code, invite in guild_cache.items():
                for new_invite in new_invites:
                    if new_invite.code == code and new_invite.uses > invite.uses:
                        inviter = invite.inviter
                        invite_cache[member.guild.id][code] = new_invite
                        await invite_logs.insert_one({
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

@bot.event
async def on_member_remove(member):
    config = await get_guild_config(member.guild.id)
    log_channel_id = config.get('log_channel_id')
    
    if log_channel_id:
        log_channel = bot.get_channel(int(log_channel_id))
        if log_channel:
            await invite_logs.insert_one({
                "user_id": member.id,
                "guild_id": member.guild.id,
                "action": "leave",
                "timestamp": datetime.now(IST)
            })
            await log_channel.send(f"❌ **Left**: {member.mention}")

@bot.command()
@commands.has_permissions(manage_guild=True)
async def config(ctx, channel_type: str, channel: discord.TextChannel):
    """Set configuration channels (welcome, log, announcement)"""
    valid_types = ['welcome', 'log', 'announcement']
    if channel_type.lower() not in valid_types:
        await ctx.send(f"Invalid channel type. Valid types: {', '.join(valid_types)}")
        return
    
    field_name = f"{channel_type.lower()}_channel_id"
    await update_guild_config(ctx.guild.id, {field_name: str(channel.id)})
    await ctx.send(f"✅ Set {channel_type} channel to {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setbirthday(ctx, member: discord.Member, date: str):
    """Set a user's birthday (Admin only) MM-DD format"""
    try:
        month, day = map(int, date.split('-'))
        datetime.now(IST).replace(year=2020, month=month, day=day)  # Validate in IST
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

@tasks.loop(time=time(hour=0, minute=0, tzinfo=IST))  # Midnight IST
async def birthday_task():
    try:
        now = datetime.now(IST)
        today = now.strftime("%m-%d")
        
        async for record in birthdays.find({"birthday": today}):
            guild = bot.get_guild(record["guild_id"])
            if guild:
                config = await get_guild_config(guild.id)
                announcement_channel_id = config.get('announcement_channel_id')
                
                if announcement_channel_id:
                    channel = bot.get_channel(int(announcement_channel_id))
                    if channel:
                        member = guild.get_member(record["user_id"])
                        if member:
                            await channel.send(f"🎉 **Happy Birthday** {member.mention}! 🥳")
    except Exception as e:
        logger.error(f"Birthday task error: {e}")

@birthday_task.error
async def birthday_task_error(error):
    logger.error(f"Birthday task failed: {error}")

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

# =====================================
# TEMPLATE AND WEB SERVER SETUP
# =====================================

def run_flask():
    logger.info("Starting Flask web server on port 8080")
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()
    logger.info("Web server thread started")

# Create template directory and file
if not os.path.exists('templates'):
    os.makedirs('templates')

with open('templates/config.html', 'w') as f:
    f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Server Configuration - {{ guild_name }}</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { color: #333; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        select { width: 100%; padding: 8px; border-radius: 4px; border: 1px solid #ccc; }
        button { background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background-color: #45a049; }
        .timezone-info { margin-top: 30px; padding: 15px; background: #f5f5f5; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>Server Configuration: {{ guild_name }}</h1>
    <p>Guild ID: {{ guild_id }}</p>
    
    <form method="POST">
        <div class="form-group">
            <label for="welcome_channel">Welcome Channel:</label>
            <select id="welcome_channel" name="welcome_channel">
                <option value="">-- Select Channel --</option>
                {% for channel in channels %}
                <option value="{{ channel.id }}" {% if config.welcome_channel_id == channel.id %}selected{% endif %}>
                    {{ channel.name }}
                </option>
                {% endfor %}
            </select>
        </div>
        
        <div class="form-group">
            <label for="log_channel">Log Channel:</label>
            <select id="log_channel" name="log_channel">
                <option value="">-- Select Channel --</option>
                {% for channel in channels %}
                <option value="{{ channel.id }}" {% if config.log_channel_id == channel.id %}selected{% endif %}>
                    {{ channel.name }}
                </option>
                {% endfor %}
            </select>
        </div>
        
        <div class="form-group">
            <label for="announcement_channel">Announcement Channel:</label>
            <select id="announcement_channel" name="announcement_channel">
                <option value="">-- Select Channel --</option>
                {% for channel in channels %}
                <option value="{{ channel.id }}" {% if config.announcement_channel_id == channel.id %}selected{% endif %}>
                    {{ channel.name }}
                </option>
                {% endfor %}
            </select>
        </div>
        
        <button type="submit">Save Configuration</button>
    </form>
    
    <div class="timezone-info">
        <h2>Time Zone Information</h2>
        <p>Birthday announcements will occur at <strong>midnight IST (UTC+5:30)</strong></p>
        <p>Current IST time: <span id="current-time">Loading...</span></p>
        <p>Next birthday check: <span id="next-check">Loading...</span></p>
    </div>
    
    <p><a href="/debug">View Debug Information</a></p>
    
    <script>
        function updateTimes() {
            const now = new Date();
            const istOffset = 5.5 * 60 * 60 * 1000;
            const istTime = new Date(now.getTime() + istOffset);
            
            document.getElementById('current-time').textContent = 
                istTime.toISOString().replace('T', ' ').substring(0, 19) + " IST";
            
            const nextCheck = new Date(istTime);
            nextCheck.setDate(nextCheck.getDate() + 1);
            nextCheck.setHours(0, 0, 0, 0);
            
            document.getElementById('next-check').textContent = 
                nextCheck.toISOString().replace('T', ' ').substring(0, 19) + " IST";
        }
        
        updateTimes();
        setInterval(updateTimes, 60000);
    </script>
</body>
</html>
""")

# =====================================
# START APPLICATION
# =====================================

if __name__ == '__main__':
    keep_alive()
    logger.info("Web server initialized")
    
    try:
        logger.info("Starting Discord bot...")
        bot.run(TOKEN)
    except discord.errors.PrivilegedIntentsRequired:
        logger.error("Missing privileged intents! Enable in Developer Portal")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
