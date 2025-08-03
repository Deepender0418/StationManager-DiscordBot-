#!/usr/bin/env python3
"""
Events cog - Daily special events and holidays
"""

import discord
from discord.ext import commands
import aiohttp
import logging
from datetime import datetime
from utils.timezone import IST
from utils.database import get_guild_config

logger = logging.getLogger(__name__)

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("Events cog initialized")
    
    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Events cog ready")
    
    async def fetch_daily_events(self):
        """Fetch daily events from API"""
        try:
            today = datetime.now(IST)
            date_str = today.strftime("%m/%d")
            logger.info(f"Fetching events for date: {date_str}")
            
            # Priority list for most popular/important events
            priority_events = [
                "friendship day", "sisters day", "national friendship day", "national sisters day",
                "mother's day", "father's day", "valentine's day", "christmas", "new year",
                "independence day", "thanksgiving", "halloween", "easter", "memorial day",
                "veterans day", "labor day", "martin luther king day", "presidents day",
                "national pizza day", "national ice cream day", "national chocolate day",
                "international women's day", "international men's day", "earth day",
                "national coffee day", "national donut day", "national burger day"
            ]
            
            # Known holidays with descriptions (in case APIs fail)
            known_holidays = {
                "08/03": [
                    {"name": "Friendship Day", "url": "https://www.checkiday.com/7aa7b1b24d0504b7cff363562be9cc47/friendship-day", "description": "A day to celebrate the beautiful bonds of friendship that enrich our lives. Take time to reach out to friends, old and new, and let them know how much they mean to you."},
                    {"name": "Sisters' Day", "url": "https://www.checkiday.com/ea4f14ed66abb6a04b8ee0a1eb1843c8/sisters-day", "description": "Honor the special relationship between sisters everywhere. Whether biological or chosen, sisters share a unique bond that lasts a lifetime."},
                    {"name": "National Watermelon Day", "url": "https://www.checkiday.com/6b0d36b1c8fe376fe20d8f0c83fb1500/national-watermelon-day", "description": "Celebrate this refreshing summer fruit that's perfect for hot days. Watermelon is not only delicious but also packed with hydration and nutrients."}
                ],
                "08/04": [
                    {"name": "National Chocolate Chip Cookie Day", "url": "https://nationaltoday.com/national-chocolate-chip-cookie-day/", "description": "Celebrate the classic American cookie that brings joy to people of all ages. Bake some cookies and share them with loved ones!"},
                    {"name": "National Coast Guard Day", "url": "https://nationaltoday.com/national-coast-guard-day/", "description": "Honor the brave men and women of the Coast Guard who protect our waters and save lives every day."}
                ],
                "08/05": [
                    {"name": "National Oyster Day", "url": "https://nationaltoday.com/national-oyster-day/", "description": "Celebrate this delicious seafood delicacy that's enjoyed around the world. Oysters are not only tasty but also rich in nutrients."},
                    {"name": "National Work Like a Dog Day", "url": "https://nationaltoday.com/national-work-like-a-dog-day/", "description": "Work hard and stay dedicated to your goals. This day reminds us of the importance of perseverance and determination."}
                ]
            }
            
            # Try multiple APIs for better reliability
            apis = [
                f"https://www.checkiday.com/api/3/?d={date_str}",
                f"https://nationaltoday.com/wp-json/nationaltoday/v1/date/{today.month}/{today.day}",
                f"https://holidays.abstractapi.com/v1/?api_key=demo&country=US&year={today.year}&month={today.month}&day={today.day}"
            ]
            
            for api_url in apis:
                try:
                    logger.info(f"Trying API: {api_url}")
                    async with aiohttp.ClientSession() as session:
                        async with session.get(api_url, timeout=10) as response:
                            if response.status == 200:
                                data = await response.json()
                                logger.info(f"API response received")
                                
                                # Handle different API formats
                                events = []
                                if 'events' in data:
                                    events = data['events']
                                elif 'holidays' in data:
                                    events = data['holidays']
                                elif isinstance(data, list):
                                    events = data
                                
                                if events:
                                    # Find the most popular/important event
                                    best_event = None
                                    
                                    # First, look for priority events
                                    for event in events:
                                        event_name = event.get('name', '').lower()
                                        if any(priority in event_name for priority in priority_events):
                                            best_event = event
                                            logger.info(f"Found priority event: {event.get('name')}")
                                            break
                                    
                                    # If no priority event found, take the first one
                                    if not best_event and events:
                                        best_event = events[0]
                                        logger.info(f"Using first event: {best_event.get('name')}")
                                    
                                    if best_event:
                                        # Add description if not present
                                        if 'description' not in best_event:
                                            best_event['description'] = f"Today we celebrate {best_event.get('name')}! This special day reminds us of the importance of this occasion in our lives."
                                        
                                        return [best_event]  # Return only the best event
                                    
                                else:
                                    logger.warning(f"No events found in API response")
                            else:
                                logger.warning(f"API returned status {response.status}")
                except Exception as e:
                    logger.error(f"Error with API {api_url}: {str(e)}")
                    continue
            
            # Check known holidays fallback
            if date_str in known_holidays:
                logger.info(f"Using known holidays for {date_str}")
                return [known_holidays[date_str][0]]  # Return only the first (most important) event
            
            # Final fallback: Create a basic event for today
            logger.info("No API working and no known holidays, creating fallback event")
            fallback_events = [
                {
                    "name": "Mac Never Told Me What's Special Today",
                    "url": "",
                    "description": "🤖 Mac didn't tell me what's special today, but that doesn't mean today isn't special! Every day is what you make of it. Take a moment to appreciate the little things and make today amazing!"
                }
            ]
            return fallback_events
            
        except Exception as e:
            logger.error(f"Error fetching daily events: {str(e)}")
            return []
    
    async def send_daily_events_announcement(self):
        """Send daily events announcement to all configured guilds"""
        try:
            events = await self.fetch_daily_events()
            
            if not events:
                logger.info("No events found for today")
                return
            
            # Get the single best event
            event = events[0]
            
            # Get all guilds the bot is in
            for guild in self.bot.guilds:
                try:
                    # Get guild config
                    config = await get_guild_config(self.bot.guild_configs, str(guild.id))
                    announcement_channel_id = config.get('announcement_channel_id') if config else None
                    
                    if not announcement_channel_id:
                        continue
                    
                    announcement_channel = self.bot.get_channel(int(announcement_channel_id))
                    if not announcement_channel:
                        continue
                    
                    # Create single event announcement
                    embed = discord.Embed(
                        title="📅 What's Special Today?",
                        description=f"**{event.get('name', 'Special Day')}**\n\n{event.get('description', 'Today is a special day worth celebrating!')}",
                        color=discord.Color.blue(),
                        timestamp=datetime.now(IST)
                    )
                    
                    # Add clickable link if available
                    if event.get('url'):
                        embed.add_field(
                            name="🔗 Learn More",
                            value=f"[Click here to read more about {event.get('name')}]({event.get('url')})",
                            inline=False
                        )
                    
                    embed.set_footer(text=f"📅 {datetime.now(IST).strftime('%B %d, %Y')} • Daily Events")
                    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/📅.png")
                    
                    await announcement_channel.send(content="@everyone", embed=embed)
                    logger.info(f"Sent daily events announcement to {guild.name}")
                    
                except Exception as e:
                    logger.error(f"Error sending events announcement to guild {guild.id}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error in daily events announcement: {str(e)}")
    
    @commands.hybrid_command(name="testevents", description="Test daily events announcement (Admin only)")
    @commands.has_permissions(administrator=True)
    async def test_events(self, ctx):
        """Test the daily events announcement"""
        try:
            # First check if announcement channel is configured
            config = await get_guild_config(self.bot.guild_configs, str(ctx.guild.id))
            announcement_channel_id = config.get('announcement_channel_id') if config else None
            
            if not announcement_channel_id:
                await ctx.send("❌ Announcement channel not configured! Set it with `/config announcement #channel`", ephemeral=True)
                return
            
            announcement_channel = self.bot.get_channel(int(announcement_channel_id))
            if not announcement_channel:
                await ctx.send("❌ Announcement channel not found! It might have been deleted.", ephemeral=True)
                return
            
            await ctx.send("📅 Testing daily events announcement...", ephemeral=True)
            
            # Fetch and send events
            events = await self.fetch_daily_events()
            
            if not events:
                await ctx.send("❌ No events found for today.", ephemeral=True)
                return
            
            # Get the single best event
            event = events[0]
            
            # Create single event announcement
            embed = discord.Embed(
                title="📅 What's Special Today? (TEST)",
                description=f"**{event.get('name', 'Special Day')}**\n\n{event.get('description', 'Today is a special day worth celebrating!')}",
                color=discord.Color.blue(),
                timestamp=datetime.now(IST)
            )
            
            # Add clickable link if available
            if event.get('url'):
                embed.add_field(
                    name="🔗 Learn More",
                    value=f"[Click here to read more about {event.get('name')}]({event.get('url')})",
                    inline=False
                )
            
            embed.set_footer(text=f"📅 {datetime.now(IST).strftime('%B %d, %Y')} • Daily Events • (TEST)")
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/📅.png")
            
            await announcement_channel.send(content="@everyone", embed=embed)
            await ctx.send(f"✅ Daily events test announcement sent to {announcement_channel.mention}!", ephemeral=True)
            
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error testing events: {str(e)}")

async def setup(bot):
    await bot.add_cog(EventsCog(bot))
    logger.info("Events cog setup complete") 
