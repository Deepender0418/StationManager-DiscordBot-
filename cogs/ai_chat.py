#!/usr/bin/env python3
"""
Gwen Chat Cog - AI-Powered Gwen Stacy Character Chat System

This cog provides an interactive chat experience with Gwen Stacy from Spider-Verse,
featuring:
- Natural language conversations using Groq AI
- Persistent conversation history with MongoDB
- Continuous conversation tracking across restarts
- Teasing task for owner interactions
- Mention-based and command-based interaction modes

The cog maintains conversation context and personality consistency while providing
short, playful responses with emojis in Gwen's characteristic style.
"""

import os
import discord
from discord.ext import commands, tasks
from groq import Groq
import logging
from datetime import datetime, timedelta
from pymongo import MongoClient
from utils.timezone import IST

logger = logging.getLogger(__name__)

class GwenChatCog(commands.Cog):
    """
    Gwen Stacy chat cog that provides AI-powered conversational interactions
    
    This cog provides:
    - Character-accurate Gwen Stacy personality with witty, playful responses
    - MongoDB-backed conversation history for continuity across restarts
    - Automatic teasing messages to the bot owner
    - Multiple interaction methods (commands, mentions, DMs)
    - Short, emoji-filled responses in Gwen's signature style
    """
    
    def __init__(self, bot):
        """
        Initialize the Gwen chat cog
        
        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.owner_id = int(os.getenv("OWNER_ID"))
        
        # MongoDB connection for conversation persistence
        self.mongo_client = MongoClient(os.getenv("MONGO_URI"))
        self.db = self.mongo_client["gwen_bot"]
        self.conversations = self.db["conversations"]
        
        # Start background tasks
        self.tease_task.start()
        self.cleanup_task.start()
        
        logger.info("Gwen chat cog initialized")
    
    def cog_unload(self):
        """
        Cleanup when cog is unloaded
        
        This method:
        1. Stops all background tasks
        2. Closes MongoDB connection
        3. Logs the unloading process
        """
        self.tease_task.cancel()
        self.cleanup_task.cancel()
        self.mongo_client.close()
        logger.info("Gwen chat cog unloaded")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the cog is ready and loaded"""
        logger.info("Gwen chat cog ready")
    
    # ============================================================================
    # DATABASE MANAGEMENT SECTION
    # ============================================================================
    
    async def get_conversation_history(self, ctx) -> list:
        """
        Retrieve conversation history from MongoDB
        
        This method:
        1. Creates a unique key based on context (channel ID or user ID)
        2. Retrieves conversation history from MongoDB
        3. Returns empty list if no history exists
        
        Args:
            ctx: The Discord context object
            
        Returns:
            list: Conversation history or empty list
        """
        try:
            key = ctx.channel.id if ctx.guild else ctx.author.id
            doc = self.conversations.find_one({"_id": key})
            return doc["history"] if doc and "history" in doc else []
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {str(e)}")
            return []
    
    async def update_conversation_history(self, ctx, user_message: str, bot_response: str):
        """
        Update conversation history in MongoDB
        
        This method:
        1. Creates a unique key based on context
        2. Retrieves existing history or initializes new
        3. Adds new messages with timestamps
        4. Trims history to maintain size limits
        5. Updates MongoDB with new history
        
        Args:
            ctx: The Discord context object
            user_message: The user's message content
            bot_response: Gwen's response content
        """
        try:
            key = ctx.channel.id if ctx.guild else ctx.author.id
            max_history = 6  # Keep last 6 exchanges
            
            # Get current history or initialize
            doc = self.conversations.find_one({"_id": key})
            if not doc:
                history = []
            else:
                history = doc.get("history", [])
            
            # Add new messages to history
            history.extend([
                {"role": "user", "content": user_message, "timestamp": datetime.utcnow()},
                {"role": "assistant", "content": bot_response, "timestamp": datetime.utcnow()}
            ])
            
            # Trim history if too long
            if len(history) > max_history * 2:
                history = history[-(max_history * 2):]
            
            # Update or insert document
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
        Generate a response from Gwen Stacy using Groq AI
        
        This method:
        1. Formats the request with system prompt and conversation history
        2. Calls the Groq API to generate a response
        3. Returns a fallback message if API call fails
        
        Args:
            message: The user's message to respond to
            history: Conversation history for context (optional)
            
        Returns:
            str: Gwen's response or fallback message
        """
        try:
            # Prepare messages for API call
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
                        "Avoid long explanations — you're quick and snappy, like you're texting a friend."
                    )
                }
            ]
            
            # Add conversation history if provided
            if history:
                messages.extend(history)
            
            # Add current message
            messages.append({"role": "user", "content": message})
            
            # Call Groq API
            chat_completion = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                max_tokens=80,
                temperature=0.75
            )
            
            return chat_completion.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Groq API call failed: {str(e)}")
            return "My web shooter jammed again 🕸️💥. Try me again in a sec?"
    
    async def generate_tease(self, owner_mention: str) -> str:
        """
        Generate a teasing message for the bot owner
        
        This method:
        1. Creates a specialized prompt for teasing messages
        2. Calls the Groq API with teasing instructions
        3. Returns a fallback message if API call fails
        
        Args:
            owner_mention: The mention string for the bot owner
            
        Returns:
            str: Teasing message or fallback
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
                            "Avoid long explanations — you're quick and snappy, like you're texting a friend."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Send a quick, flirty tease to {owner_mention} like you're texting them."
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
    
    @tasks.loop(minutes=30)
    async def tease_task(self):
        """
        Background task to send teasing messages to the bot owner
        
        This task:
        1. Waits until the bot is ready
        2. Generates a teasing message
        3. Sends it to the owner via DM
        4. Handles permission errors gracefully
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
        
        This task:
        1. Waits until the bot is ready
        2. Deletes conversations older than 30 days
        3. Logs the cleanup process
        """
        await self.bot.wait_until_ready()
        cutoff_date = datetime.utcnow() - timedelta(days=30)  # 30 days retention
        result = self.conversations.delete_many({"last_updated": {"$lt": cutoff_date}})
        logger.info(f"Cleaned up {result.deleted_count} old conversations")
    
    # ============================================================================
    # COMMAND HANDLERS SECTION
    # ============================================================================
    
    @commands.hybrid_command(name="gwen", description="Chat with Gwen Stacy from Spider-Verse")
    async def gwen_chat(self, ctx, *, message: str):
        """
        Chat with Gwen Stacy directly using command
        
        This command:
        1. Retrieves conversation history from MongoDB
        2. Generates a response using Groq AI
        3. Updates conversation history with new exchange
        4. Sends the response to the channel
        
        Args:
            ctx: The Discord context object
            message: The message to send to Gwen
        """
        try:
            # Get conversation history
            history = await self.get_conversation_history(ctx)
            
            # Generate response
            response = await self.generate_gwen_response(message, history)
            
            # Update conversation history
            await self.update_conversation_history(ctx, message, response)
            
            # Send response
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
        Handle message events for mention-based interactions
        
        This listener:
        1. Ignores messages from bots
        2. Responds when the bot is mentioned
        3. Maintains conversation history
        4. Handles errors gracefully
        
        Args:
            message: The Discord message object
        """
        if message.author.bot:
            return

        # If bot is mentioned in the message
        if self.bot.user.mentioned_in(message):
            try:
                # Extract user input from mention
                user_input = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
                if not user_input:
                    user_input = "What's up?"
                
                # Create context for history tracking
                ctx = await self.bot.get_context(message)
                
                # Get conversation history
                history = await self.get_conversation_history(ctx)
                
                # Generate response
                response = await self.generate_gwen_response(user_input, history)
                
                # Update conversation history
                await self.update_conversation_history(ctx, user_input, response)
                
                # Send response
                await message.channel.send(response)
                logger.info(f"Gwen mention response sent: {response}")
                
            except Exception as e:
                await message.channel.send("Oops, my web got tangled again 🕸️💫. DM me instead?")
                logger.error(f"Error handling mention: {str(e)}")

# ============================================================================
# COG SETUP SECTION
# ============================================================================

async def setup(bot):
    """
    Setup function called by Discord.py to load this cog
    
    This function:
    1. Creates an instance of GwenChatCog
    2. Adds it to the bot
    3. Logs successful setup
    
    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(GwenChatCog(bot))
    logger.info("Gwen chat cog setup complete")
