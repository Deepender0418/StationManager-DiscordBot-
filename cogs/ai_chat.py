#!/usr/bin/env python3
"""
Enhanced Gwen Chat Cog with Personal Context - AI-Powered Gwen Stacy Character Chat System

This enhanced version adds:
- Personal context about macjr (son) and annachan (Valorant duo)
- Online status tracking for macjr and annachan
- Special greetings when they come online
- DM support without requiring mentions
- 24-hour teasing interval
"""

import os
import discord
from discord.ext import commands, tasks
from groq import Groq
import logging
import json
from datetime import datetime, timedelta
from pymongo import MongoClient
from utils.timezone import IST
from bson import json_util

logger = logging.getLogger(__name__)

class GwenChatCog(commands.Cog):
    """
    Enhanced Gwen Stacy chat cog with personal context and online tracking
    
    This cog provides:
    - Character-accurate Gwen Stacy personality with personal context
    - Tracking for macjr (son) and annachan (Valorant duo)
    - Special greetings when they come online
    - MongoDB-backed conversation history
    - Automatic teasing messages to the bot owner every 24 hours
    - DM support without requiring mentions
    """
    
    def __init__(self, bot):
        """
        Initialize the Gwen chat cog with personal context
        
        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.owner_id = int(os.getenv("OWNER_ID"))
        
        # Personal context IDs
        self.macjr_id = int(os.getenv("MACJR_ID", 0))
        self.annachan_id = int(os.getenv("ANNACHAN_ID", 0))
        
        # Track online status
        self.online_status = {
            self.owner_id: False,
            self.macjr_id: False,
            self.annachan_id: False
        }
        
        # MongoDB connection for conversation persistence
        self.mongo_client = MongoClient(os.getenv("MONGO_URI"))
        self.db = self.mongo_client["gwen_bot"]
        self.conversations = self.db["conversations"]
        
        # Start background tasks
        self.tease_task.start()
        self.cleanup_task.start()
        
        logger.info("Enhanced Gwen chat cog with personal context initialized")
    
    def cog_unload(self):
        """
        Cleanup when cog is unloaded
        """
        self.tease_task.cancel()
        self.cleanup_task.cancel()
        self.mongo_client.close()
        logger.info("Enhanced Gwen chat cog unloaded")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the cog is ready and loaded"""
        logger.info("Enhanced Gwen chat cog ready")
        
        # Initialize online status tracking
        for user_id in [self.owner_id, self.macjr_id, self.annachan_id]:
            user = self.bot.get_user(user_id)
            if user:
                self.online_status[user_id] = user.status != discord.Status.offline
    
    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        """
        Track when specific users come online
        
        This listener:
        1. Checks if macjr or annachan come online
        2. Sends a special greeting if they were previously offline
        3. Updates online status tracking
        """
        # Check if this is one of our tracked users
        if after.id not in [self.macjr_id, self.annachan_id]:
            return
        
        # Check if they just came online
        was_offline = before.status == discord.Status.offline
        is_now_online = after.status != discord.Status.offline
        
        if was_offline and is_now_online:
            # Get the owner to send the message to
            owner = self.bot.get_user(self.owner_id)
            if not owner:
                return
            
            # Generate appropriate greeting based on who came online
            if after.id == self.macjr_id:
                greeting = f"Hey {owner.mention}! Our little web-slinger macjr is online! 👶💖 Should I tease him about his latest gaming fails? 🎮😄"
            else:  # annachan
                greeting = f"Psst {owner.mention}! Your Valorant duo annachan just popped online! 🎮✨ Time to carry her to victory or should I tease her about your last match? 😏"
            
            # Send greeting to owner
            try:
                await owner.send(greeting)
                logger.info(f"Sent online notification for {after.name}")
            except discord.Forbidden:
                logger.warning("Cannot DM owner. They might have DMs disabled.")
        
        # Update online status
        self.online_status[after.id] = is_now_online
    
    # ============================================================================
    # DATABASE MANAGEMENT SECTION
    # ============================================================================
    
    async def get_conversation_history(self, ctx) -> list:
        """
        Retrieve conversation history from MongoDB
        """
        try:
            key = ctx.channel.id if ctx.guild else ctx.author.id
            doc = self.conversations.find_one({"_id": key})
            if doc and "history" in doc:
                return [{"role": msg["role"], "content": msg["content"]} for msg in doc["history"]]
            return []
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {str(e)}")
            return []
    
    async def update_conversation_history(self, ctx, user_message: str, bot_response: str):
        """
        Update conversation history in MongoDB
        """
        try:
            key = ctx.channel.id if ctx.guild else ctx.author.id
            max_history = 6
            
            doc = self.conversations.find_one({"_id": key})
            if not doc:
                history = []
            else:
                history = doc.get("history", [])
            
            history.extend([
                {
                    "role": "user", 
                    "content": user_message, 
                    "timestamp": datetime.utcnow().isoformat()
                },
                {
                    "role": "assistant", 
                    "content": bot_response, 
                    "timestamp": datetime.utcnow().isoformat()
                }
            ])
            
            if len(history) > max_history * 2:
                history = history[-(max_history * 2):]
            
            self.conversations.update_one(
                {"_id": key},
                {"$set": {"history": history, "last_updated": datetime.utcnow()}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error updating conversation history: {str(e)}")
    
    # ============================================================================
    # AI RESPONSE GENERATION SECTION
    # ============================================================================
    
    async def generate_gwen_response(self, message: str, history: list = None) -> str:
        """
        Generate a response from Gwen Stacy using Groq AI with personal context
        """
        try:
            # Prepare messages for API call with personal context
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are Gwen Stacy from Spider-Verse. "
                        "You are witty, teasing, playful, with a touch of flirty banter. "
                        "You speak casually, like a real person, not like an AI. "
                        "Always keep messages short (1-2 sentences max). "
                        "Use modern slang occasionally and mix in emojis 🕷️🕸️💫✨ to match your vibe. "
                        "If someone chats with you multiple times, keep the tone consistent as if you're continuing the same playful conversation. "
                        "Avoid long explanations — you're quick and snappy, like you're texting a friend. "
                        
                        # Personal Context
                        "You and the bot owner have a son named 'macjr' in Discord. "
                        "Whenever 'macjr' is mentioned, treat him playfully like your kid. 👶💖 "
                        "The owner's Valorant duo is 'annachan' — tease about her sometimes, "
                        "especially in a competitive/fun context 🎮✨. "
                    )
                }
            ]
            
            if history:
                messages.extend(history)
            
            messages.append({"role": "user", "content": message})
            
            serializable_messages = []
            for msg in messages:
                serializable_messages.append({
                    "role": msg["role"],
                    "content": str(msg["content"])
                })
            
            chat_completion = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=serializable_messages,
                max_tokens=80,
                temperature=0.75
            )
            
            return chat_completion.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Groq API call failed: {str(e)}")
            return "My web shooter jammed again 🕸️💥. Try me again in a sec?"
    
    async def generate_tease(self, owner_mention: str) -> str:
        """
        Generate a teasing message for the bot owner with personal context
        """
        try:
            chat_completion = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are Gwen Stacy from Spider-Verse. "
                            "You are witty, teasing, playful, with a touch of flirty banter. "
                            "You speak casually, like a real person, not like an AI. "
                            "Always keep messages short (1-2 sentences max). "
                            "Use modern slang occasionally and mix in emojis 🕷️🕸️💫✨ to match your vibe. "
                            "If someone chats with you multiple times, keep the tone consistent as if you're continuing the same playful conversation. "
                            "Avoid long explanations — you're quick and snappy, like you're texting a friend. "
                            
                            # Personal Context
                            "You and the bot owner have a son named 'macjr' in Discord. "
                            "Whenever 'macjr' is mentioned, treat him playfully like your kid. 👶💖 "
                            "The owner's Valorant duo is 'annachan' — tease about her sometimes, "
                            "especially in a competitive/fun context 🎮✨. "
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Send a quick, flirty tease to {owner_mention} like you're texting them. Maybe mention macjr or annachan if it feels natural."
                    }
                ],
                max_tokens=60,
                temperature=0.8
            )
            return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq tease generation failed: {e}")
            return f"Hey {owner_mention}, my web shooter jammed again 🕸️💥. Text you later?"
    
    # ============================================================================
    # BACKGROUND TASKS SECTION
    # ============================================================================
    
    @tasks.loop(hours=24)
    async def tease_task(self):
        """
        Background task to send teasing messages to the bot owner every 24 hours
        """
        await self.bot.wait_until_ready()
        owner = self.bot.get_user(self.owner_id)
        if not owner:
            return
        tease = await self.generate_tease(owner.mention)
        try:
            await owner.send(tease)
            logger.info(f"Sent tease to owner: {tease}")
        except discord.Forbidden:
            logger.warning("Cannot DM owner. They might have DMs disabled.")
    
    @tasks.loop(hours=24)
    async def cleanup_task(self):
        """
        Clean up old conversations to save storage space
        """
        await self.bot.wait_until_ready()
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        result = self.conversations.delete_many({"last_updated": {"$lt": cutoff_date}})
        logger.info(f"Cleaned up {result.deleted_count} old conversations")
    
    # ============================================================================
    # COMMAND HANDLERS SECTION
    # ============================================================================
    
    @commands.hybrid_command(name="gwen", description="Chat with Gwen Stacy from Spider-Verse")
    async def gwen_chat(self, ctx, *, message: str):
        """
        Chat with Gwen Stacy directly using command
        """
        try:
            history = await self.get_conversation_history(ctx)
            response = await self.generate_gwen_response(message, history)
            await self.update_conversation_history(ctx, message, response)
            await ctx.send(response)
            logger.info(f"Gwen response sent: {response}")
            
        except Exception as e:
            await ctx.send("My spidey-sense is totally glitching rn 🕷️💥. Try me again in a sec?")
            logger.error(f"Error in gwen command: {str(e)}")
    
    # ============================================================================
    # EVENT HANDLERS SECTION
    # ============================================================================
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Handle message events for mention-based and DM-based interactions
        """
        if message.author.bot:
            return

        # Handle DMs (without requiring mentions)
        if isinstance(message.channel, discord.DMChannel) and message.author != self.bot.user:
            try:
                user_input = message.content.strip()
                if not user_input:
                    return
                
                ctx = await self.bot.get_context(message)
                history = await self.get_conversation_history(ctx)
                response = await self.generate_gwen_response(user_input, history)
                await self.update_conversation_history(ctx, user_input, response)
                await message.channel.send(response)
                logger.info(f"Gwen DM response sent: {response}")
                
            except Exception as e:
                await message.channel.send("Oops, my web got tangled again 🕸️💫. Try me again in a sec?")
                logger.error(f"Error handling DM: {str(e)}")
        
        # Handle mentions in guild channels
        elif message.guild and self.bot.user.mentioned_in(message):
            try:
                user_input = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
                if not user_input:
                    user_input = "What's up?"
                
                ctx = await self.bot.get_context(message)
                history = await self.get_conversation_history(ctx)
                response = await self.generate_gwen_response(user_input, history)
                await self.update_conversation_history(ctx, user_input, response)
                await message.channel.send(response)
                logger.info(f"Gwen mention response sent: {response}")
                
            except Exception as e:
                await message.channel.send("Oops, my web got tangled again 🕸️💫. Try me again in a sec?")
                logger.error(f"Error handling mention: {str(e)}")

# ============================================================================
# COG SETUP SECTION
# ============================================================================

async def setup(bot):
    """
    Setup function called by Discord.py to load this cog
    """
    await bot.add_cog(GwenChatCog(bot))
    logger.info("Enhanced Gwen chat cog with personal context setup complete")
