import discord
from discord.ext import commands, tasks
from datetime import datetime, time
import aiohttp
import logging
from utils.timezone import IST

logger = logging.getLogger(__name__)

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # FIX: Create the task without starting it in __init__
        self.event_task = tasks.loop(time=time(hour=8, minute=0, tzinfo=IST))(self._event_task)
        logger.info("Events cog initialized")
    
    # FIX: Start the task in on_ready instead of __init__
    @commands.Cog.listener()
    async def on_ready(self):
        self.event_task.start()
        logger.info("Events task started")
    
    # FIX: Rename the task method to avoid conflict
    async def _event_task(self):
        try:
            today = datetime.now().strftime("%m-%d")
            logger.info(f"Running daily events check for {today}")
            
            events = await self.get_todays_events()
            if not events:
                logger.info("No special events found today")
                return
            
            # Process each guild
            async for config in self.bot.guild_configs.find():
                guild_id = config.get("guild_id")
                announcement_channel_id = config.get("announcement_channel_id")
                
                if not announcement_channel_id:
                    continue
                
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    continue
                
                channel = self.bot.get_channel(int(announcement_channel_id))
                if not channel:
                    continue
                
                # Format message
                message = self.format_event_message(events)
                await channel.send(message)
                logger.info(f"Sent daily events announcement to {guild.name}")
                
        except Exception as e:
            logger.error(f"Event task error: {str(e)}")
    
    async def get_todays_events(self):
        """Fetch today's special events from API"""
        try:
            today = datetime.now()
            month = today.month
            day = today.day
            
            # Use Checkiday API (free and no API key required)
            url = f"https://apihub.checkiday.com/api/3?d={day}&m={month}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"API request failed: {response.status}")
                        return None
                    
                    data = await response.json()
                    return data.get("holidays", [])
        
        except Exception as e:
            logger.error(f"Error fetching events: {str(e)}")
            return None
    
    def format_event_message(self, events):
        """Format events into a Discord message"""
        message = "🌟 **What's Special About Today?** 🌟\n\n"
        
        for i, event in enumerate(events[:5]):  # Limit to 5 events
            name = event.get("name", "Unknown Event")
            url = event.get("url", "")
            
            if url:
                message += f"{i+1}. [{name}]({url})\n"
            else:
                message += f"{i+1}. {name}\n"
        
        message += "\nHave a great day everyone! 😊"
        return message
    
    # FIX: Use the correct before_loop signature
    @_event_task.before_loop
    async def before_event_task(self):
        await self.bot.wait_until_ready()
        logger.info("Events task is ready")

async def setup(bot):
    await bot.add_cog(EventsCog(bot))
    logger.info("Events cog setup complete")
