#!/usr/bin/env python3
"""
AI Chat Cog - Groq AI Integration

This cog provides AI chat functionality using the Groq API.
It includes features to:
- Respond to messages mentioning the bot or in specific channels
- Maintain conversation context
- Handle rate limiting and API errors
- Provide configurable AI personality and behavior
"""

import discord
from discord.ext import commands
import aiohttp
import logging
import json
import os
import asyncio
from datetime import datetime, timedelta
from utils.database import get_guild_config

logger = logging.getLogger(__name__)

class AIChatCog(commands.Cog):
    """
    AI chat management cog that handles Groq AI interactions
    
    This cog provides:
    - Natural language processing through Groq API
    - Context-aware conversations
    - Rate limiting to prevent API abuse
    - Configurable response behavior
    """
    
    def __init__(self, bot):
        """
        Initialize the AI chat cog
        
        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.api_key = os.getenv('GROQ_API_KEY')
        self.model = os.getenv('GROQ_MODEL', 'llama3-8b-8192')  # Default to a fast model
        self.conversation_context = {}  # Store conversation context per channel
        self.last_message_time = {}  # Rate limiting per channel
        self.cooldown = 2  # seconds between messages in the same channel
        
        # Check if API key is configured
        if not self.api_key:
            logger.warning("Groq API key not configured. AI features will be disabled.")
            self.enabled = False
        else:
            self.enabled = True
            logger.info(f"Groq AI cog initialized with model: {self.model}")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the cog is ready and loaded"""
        if self.enabled:
            logger.info("Groq AI cog ready")
        else:
            logger.warning("Groq AI cog loaded but disabled due to missing API key")
    
    def should_respond(self, message):
        """
        Determine if the bot should respond to a message
        
        Args:
            message: The Discord message object
            
        Returns:
            bool: True if the bot should respond, False otherwise
        """
        # Don't respond if AI is disabled
        if not self.enabled:
            return False
            
        # Don't respond to ourselves
        if message.author == self.bot.user:
            return False
        
        # Check if we're mentioned or it's a DM
        if self.bot.user in message.mentions or isinstance(message.channel, discord.DMChannel):
            return True
        
        # Check rate limiting
        channel_id = message.channel.id
        current_time = datetime.now().timestamp()
        
        if channel_id in self.last_message_time:
            time_diff = current_time - self.last_message_time[channel_id]
            if time_diff < self.cooldown:
                return False
        
        return False
    
    async def get_ai_response(self, message):
        """
        Get response from Groq API
        
        Args:
            message: The Discord message object
            
        Returns:
            str: AI response text or None if error
        """
        if not self.api_key:
            return "I'm sorry, my AI capabilities are currently unavailable. Please check my configuration."
        
        # Prepare conversation context
        channel_id = message.channel.id
        if channel_id not in self.conversation_context:
            self.conversation_context[channel_id] = []
        
        # Build conversation history for the API
        messages = [
            {
                "role": "system", 
                "content": "You are a helpful AI assistant in a Discord server. Be friendly, concise, and engaging."
            }
        ]
        
        # Add conversation history if available
        for msg in self.conversation_context[channel_id]:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["content"]})
        
        # Add the current message
        messages.append({"role": "user", "content": message.clean_content})
        
        # Prepare payload for Groq API
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024,
            "top_p": 1,
            "stream": False
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, json=payload, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        response_text = data["choices"][0]["message"]["content"]
                        
                        # Update conversation context
                        self.conversation_context[channel_id].append({
                            "role": "user",
                            "content": message.clean_content,
                            "timestamp": datetime.now().isoformat()
                        })
                        self.conversation_context[channel_id].append({
                            "role": "assistant",
                            "content": response_text,
                            "timestamp": datetime.now().isoformat()
                        })
                        
                        # Keep context manageable size
                        if len(self.conversation_context[channel_id]) > 20:
                            self.conversation_context[channel_id] = self.conversation_context[channel_id][-10:]
                        
                        return response_text
                    else:
                        error_text = await response.text()
                        logger.error(f"Groq API error: {response.status} - {error_text}")
                        return "I'm experiencing technical difficulties. Please try again later."
        
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error contacting Groq API: {str(e)}")
            return "I'm having trouble connecting to my AI service. Please try again later."
        except asyncio.TimeoutError:
            logger.error("Groq API request timed out")
            return "My AI service is taking too long to respond. Please try again later."
        except Exception as e:
            logger.error(f"Unexpected error in get_ai_response: {str(e)}")
            return "An unexpected error occurred. Please try again later."
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """
        Handle incoming messages and respond when appropriate
        
        Args:
            message: The Discord message object
        """
        # Check if we should respond to this message
        if not self.should_respond(message):
            return
        
        # Update rate limiting
        self.last_message_time[message.channel.id] = datetime.now().timestamp()
        
        # Send typing indicator
        async with message.channel.typing():
            # Get AI response
            response = await self.get_ai_response(message)
            
            # Send response
            if response:
                # Split long messages to avoid Discord's character limit
                if len(response) > 2000:
                    chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
                    for chunk in chunks:
                        await message.reply(chunk, mention_author=False)
                else:
                    await message.reply(response, mention_author=False)
    
    @commands.hybrid_command(name="reset_chat", description="Reset conversation context with AI")
    async def reset_chat(self, ctx):
        """
        Reset the conversation context with AI
        
        Args:
            ctx: Discord context
        """
        if not self.enabled:
            await ctx.send("❌ AI features are currently disabled. Please configure the API key.", ephemeral=True)
            return
            
        channel_id = ctx.channel.id
        if channel_id in self.conversation_context:
            self.conversation_context[channel_id] = []
            await ctx.send("✅ Conversation context has been reset.", ephemeral=True)
        else:
            await ctx.send("🤔 No conversation context to reset in this channel.", ephemeral=True)
    
    @commands.hybrid_command(name="chat", description="Chat with AI")
    async def chat_command(self, ctx, *, message: str):
        """
        Direct command to chat with AI
        
        Args:
            ctx: Discord context
            message: The message to send to AI
        """
        if not self.enabled:
            await ctx.send("❌ AI features are currently disabled. Please configure the API key.", ephemeral=True)
            return
            
        # Create a mock message object for processing
        class MockMessage:
            def __init__(self, content, author, channel, guild):
                self.clean_content = content
                self.author = author
                self.channel = channel
                self.guild = guild
        
        mock_message = MockMessage(
            content=message,
            author=ctx.author,
            channel=ctx.channel,
            guild=ctx.guild
        )
        
        # Send typing indicator
        async with ctx.channel.typing():
            # Get AI response
            response = await self.get_ai_response(mock_message)
            
            # Send response
            if response:
                await ctx.send(response)
    
    @commands.hybrid_command(name="set_model", description="Set the AI model (Admin only)")
    @commands.has_permissions(administrator=True)
    async def set_model(self, ctx, model_name: str):
        """
        Set the AI model to use (Admin only)
        
        Args:
            ctx: Discord context
            model_name: The name of the model to use
        """
        # List of available Groq models (you can expand this list)
        available_models = [
            "llama3-8b-8192",
            "llama3-70b-8192",
            "mixtral-8x7b-32768",
            "gemma-7b-it"
        ]
        
        if model_name not in available_models:
            await ctx.send(f"❌ Invalid model. Available models: {', '.join(available_models)}", ephemeral=True)
            return
            
        self.model = model_name
        await ctx.send(f"✅ Model set to: {model_name}", ephemeral=True)
        logger.info(f"Model changed to: {model_name}")

# ============================================================================
# COG SETUP SECTION
# ============================================================================

async def setup(bot):
    """
    Setup function called by Discord.py to load this cog
    
    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(AIChatCog(bot))
    logger.info("Groq AI cog setup complete")
