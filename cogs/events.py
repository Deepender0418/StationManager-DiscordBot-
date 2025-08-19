#!/usr/bin/env python3
"""
Events Cog - Daily Events and Holiday Announcements

This cog handles daily events and holiday announcements for the Discord bot.
It provides functionality to:
- Fetch daily events from multiple APIs
- Send daily event announcements at 8 AM
- Handle holidays and special observances
- Provide fallback events when APIs are unavailable
- Test event announcements for admins

The cog uses multiple event APIs for reliability and provides
comprehensive event information to keep server members informed
about special days and celebrations.
"""

import discord
from discord.ext import commands
import aiohttp
import logging
from datetime import datetime
from utils.timezone import IST
from utils.database import get_guild_config
import os

logger = logging.getLogger(__name__)

class EventsCog(commands.Cog):
    """
    Events management cog that handles daily events and holiday announcements
    
    This cog provides:
    - Daily event fetching from multiple APIs
    - Automatic event announcements at 8 AM
    - Holiday and observance tracking
    - Fallback event system
    - Event testing functionality
    """
    
    def __init__(self, bot):
        """
        Initialize the events cog
        
        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        logger.info("Events cog initialized")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the cog is ready and loaded"""
        logger.info("Events cog ready")
    
    # ============================================================================
    # EVENT FETCHING SECTION
    # ============================================================================
    
    async def fetch_daily_events(self):
        """
        Fetch daily events from multiple APIs for reliability
        
        This method:
        1. Tries multiple event APIs in sequence
        2. Prioritizes popular and important events
        3. Provides fallback events when APIs fail
        4. Handles different API response formats
        5. Returns the best event for the day
        
        The method uses a priority system to select the most relevant
        event when multiple events are available for the same day.
        
        Returns:
            list: List of event dictionaries, or empty list if no events found
        """
        try:
            # Get today's date in IST timezone
            today = datetime.now(IST)
            date_str = today.strftime("%m/%d")  # Format: MM/DD
            logger.info(f"Fetching events for date: {date_str}")
            
            # ============================================================================
            # PRIORITY EVENTS SECTION
            # ============================================================================
            
            # Priority list for most popular/important events
            # These events are preferred when multiple events are available
            priority_events = [
                "friendship day", "sisters day", "national friendship day", "national sisters day",
                "mother's day", "father's day", "valentine's day", "christmas", "new year",
                "independence day", "thanksgiving", "halloween", "easter", "memorial day",
                "veterans day", "labor day", "martin luther king day", "presidents day",
                "national pizza day", "national ice cream day", "national chocolate day",
                "international women's day", "international men's day", "earth day",
                "national coffee day", "national donut day", "national burger day"
            ]
            
            # ============================================================================
            # KNOWN HOLIDAYS FALLBACK SECTION
            # ============================================================================
            
            # Known holidays with descriptions (in case APIs fail)
            # This provides reliable fallback events for specific dates
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
            
            # ============================================================================
            # API FETCHING SECTION
            # ============================================================================
            
            # Try multiple APIs for better reliability
            # If one API fails, we try the next one
            apis = [
                (f"https://www.checkiday.com/api/3/?d={date_str}", "checkiday"),
                (f"https://nationaltoday.com/wp-json/nationaltoday/v1/date/{today.month}/{today.day}", "nationaltoday"),
                (f"https://holidays.abstractapi.com/v1/?api_key=demo&country=US&year={today.year}&month={today.month}&day={today.day}", "abstractapi"),
            ]
            
            request_timeout_seconds = int(os.getenv("EVENTS_API_TIMEOUT", "10"))

            for api_url, source in apis:
                try:
                    logger.info(f"Trying API: {api_url}")
                    
                    # Create HTTP session and fetch data
                    async with aiohttp.ClientSession(headers={"User-Agent": "ServerManagerBot/1.0"}) as session:
                        async with session.get(api_url, timeout=request_timeout_seconds) as response:
                            if response.status == 200:
                                data = await response.json()
                                logger.info(f"API response received")
                                
                                # ============================================================================
                                # RESPONSE PARSING SECTION
                                # ============================================================================
                                
                                # Handle different API formats and normalize
                                raw_events = []
                                if isinstance(data, dict) and 'events' in data:
                                    raw_events = data['events']
                                elif isinstance(data, dict) and 'holidays' in data:
                                    raw_events = data['holidays']
                                elif isinstance(data, list):
                                    raw_events = data

                                events = []
                                for ev in raw_events:
                                    name = ev.get('name') or ev.get('title') or ev.get('holiday') or ev.get('summary')
                                    url = ev.get('url') or ev.get('link') or ev.get('website')
                                    description = ev.get('description') or ev.get('excerpt') or ev.get('summary')
                                    if name:
                                        events.append({'name': name, 'url': url, 'description': description, '_src': source})
                                
                                if events:
                                    # Find the most popular/important event
                                    best_event = None
                                    
                                    # First, look for priority events
                                    for event in events:
                                        event_name = (event.get('name') or '').lower()
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
                                        if not best_event.get('description'):
                                            best_event['description'] = f"Today we celebrate {best_event.get('name')}! This special day reminds us of the importance of this occasion in our lives."
                                        
                                        return [best_event]  # Return only the best event
                                    
                                else:
                                    logger.warning(f"No events found in API response")
                            else:
                                logger.warning(f"API returned status {response.status}")
                                
                except Exception as e:
                    logger.error(f"Error with API {api_url}: {str(e)}")
                    continue  # Try next API
                
            # ============================================================================
            # FALLBACK SECTION
            # ============================================================================
            
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
    
    # ============================================================================
    # EVENT ANNOUNCEMENT SECTION
    # ============================================================================
    
    async def send_daily_events_announcement(self):
        """
        Send daily events announcement to all configured guilds
        
        This method:
        1. Fetches today's events using the fetch_daily_events method
        2. Sends announcements to all guilds with configured announcement channels
        3. Creates rich embeds with event information
        4. Handles errors gracefully for individual guilds
        5. Logs successful announcements
        
        This method is called automatically by the background task in bot.py
        every day at 8 AM.
        """
        try:
            # Fetch events for today
            events = await self.fetch_daily_events()
            
            if not events:
                logger.info("No events found for today")
                return
            
            # Get the single best event
            event = events[0]
            
            # Send announcement to all guilds the bot is in
            for guild in self.bot.guilds:
                try:
                    # Get guild configuration for announcement settings
                    config = await get_guild_config(self.bot.guild_configs, str(guild.id))
                    announcement_channel_id = config.get('announcement_channel_id') if config else None
                    
                    if not announcement_channel_id:
                        continue  # Skip guilds without announcement channel
                    
                    announcement_channel = self.bot.get_channel(int(announcement_channel_id))
                    if not announcement_channel:
                        continue  # Skip if channel not found
                    
                    # ============================================================================
                    # EMBED CREATION SECTION
                    # ============================================================================
                    
                    # Create single event announcement embed
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
                    
                    # Set embed styling
                    embed.set_footer(text=f"📅 {datetime.now(IST).strftime('%B %d, %Y')} • Daily Events")
                    # Removed invalid emoji URL; add a valid image URL if desired
                    
                    # Send announcement with @everyone mention
                    await announcement_channel.send(content="@everyone", embed=embed)
                    logger.info(f"Sent daily events announcement to {guild.name}")
                    
                except Exception as e:
                    logger.error(f"Error sending events announcement to guild {guild.id}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error in daily events announcement: {str(e)}")
    
    # ============================================================================
    # TESTING COMMANDS SECTION
    # ============================================================================
    
    @commands.hybrid_command(name="testevents", description="Test daily events announcement (Admin only)")
    @commands.has_permissions(administrator=True)
    async def test_events(self, ctx):
        """
        Test the daily events announcement (Admin only)
        
        This command sends a test event announcement to verify that:
        1. The announcement channel is configured correctly
        2. The bot has proper permissions
        3. Event fetching and formatting works as expected
        
        The test uses the same logic as the automatic daily announcement
        but sends it immediately instead of waiting for 8 AM.
        """
        try:
            # ============================================================================
            # CHANNEL VALIDATION SECTION
            # ============================================================================
            
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
            
            # ============================================================================
            # EVENT FETCHING AND SENDING SECTION
            # ============================================================================
            
            # Fetch and send events
            events = await self.fetch_daily_events()
            
            if not events:
                await ctx.send("❌ No events found for today.", ephemeral=True)
                return
            
            # Get the single best event
            event = events[0]
            
            # Create single event announcement embed (test version)
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
            
            # Set embed styling with test indicator
            embed.set_footer(text=f"📅 {datetime.now(IST).strftime('%B %d, %Y')} • Daily Events • (TEST)")
            # Removed invalid emoji URL; add a valid image URL if desired
            
            # Send test announcement
            await announcement_channel.send(content="@everyone", embed=embed)
            await ctx.send(f"✅ Daily events test announcement sent to {announcement_channel.mention}!", ephemeral=True)
            
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error testing events: {str(e)}")

# ============================================================================
# COG SETUP SECTION
# ============================================================================

async def setup(bot):
    """
    Setup function called by Discord.py to load this cog
    
    This function:
    1. Creates an instance of EventsCog
    2. Adds it to the bot
    3. Logs successful setup
    
    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(EventsCog(bot))
    logger.info("Events cog setup complete")
