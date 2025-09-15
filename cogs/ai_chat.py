#!/usr/bin/env python3
"""
AI Chat Cog - Groq AI Integration (with fallback system)

This cog provides AI chat functionality using the Groq API.
- Responds to mentions or DMs
- Maintains per-channel context
- Handles rate limiting and API errors
- Supports model switching with fallback to a safe default
"""

import discord
from discord.ext import commands
import aiohttp
import logging
import os
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class AIChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.api_key = os.getenv("GROQ_API_KEY")
        # Default safe model
        self.default_model = "llama-3.1-8b-instant"
        self.model = os.getenv("GROQ_MODEL", self.default_model)

        self.conversation_context = {}
        self.last_message_time = {}
        self.cooldown = 2

        if not self.api_key:
            logger.warning("Groq API key not configured. AI features disabled.")
            self.enabled = False
        else:
            self.enabled = True
            logger.info(f"Groq AI cog initialized with model: {self.model}")

    @commands.Cog.listener()
    async def on_ready(self):
        if self.enabled:
            logger.info("Groq AI cog ready")
        else:
            logger.warning("Groq AI cog loaded but disabled (missing API key)")

    def should_respond(self, message):
        if not self.enabled or message.author == self.bot.user:
            return False

        if self.bot.user in message.mentions or isinstance(message.channel, discord.DMChannel):
            return True

        channel_id = message.channel.id
        now = datetime.now().timestamp()
        if channel_id in self.last_message_time:
            if now - self.last_message_time[channel_id] < self.cooldown:
                return False
        return False

    async def query_groq(self, payload, headers):
        """Low-level Groq API request with fallback"""
        async with aiohttp.ClientSession() as session:
            async with session.post(self.api_url, json=payload, headers=headers, timeout=15) as resp:
                data = await resp.json()
                return resp.status, data

    async def get_ai_response(self, message):
        if not self.api_key:
            return "❌ AI unavailable. Please configure GROQ_API_KEY."

        channel_id = message.channel.id
        if channel_id not in self.conversation_context:
            self.conversation_context[channel_id] = []

        messages = [
            {"role": "system", "content": "You are a helpful Discord AI assistant. Be friendly, concise, and engaging."}
        ]
        for msg in self.conversation_context[channel_id]:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["content"]})
        messages.append({"role": "user", "content": message.clean_content})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024,
            "top_p": 1,
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            status, data = await self.query_groq(payload, headers)

            if status == 200:
                response_text = data["choices"][0]["message"]["content"]
            else:
                # Handle decommissioned model fallback
                error_msg = data.get("error", {}).get("message", "")
                if "decommissioned" in error_msg.lower():
                    logger.warning(f"Model {self.model} decommissioned, falling back to {self.default_model}")
                    self.model = self.default_model
                    payload["model"] = self.default_model
                    status, data = await self.query_groq(payload, headers)
                    if status == 200:
                        response_text = data["choices"][0]["message"]["content"]
                    else:
                        logger.error(f"Groq fallback failed: {status} - {data}")
                        return "⚠️ AI service error. Please try again later."
                else:
                    logger.error(f"Groq API error: {status} - {data}")
                    return "⚠️ AI service error. Please try again later."

            # Update context
            self.conversation_context[channel_id].append(
                {"role": "user", "content": message.clean_content, "timestamp": datetime.now().isoformat()}
            )
            self.conversation_context[channel_id].append(
                {"role": "assistant", "content": response_text, "timestamp": datetime.now().isoformat()}
            )

            if len(self.conversation_context[channel_id]) > 20:
                self.conversation_context[channel_id] = self.conversation_context[channel_id][-10:]

            return response_text

        except asyncio.TimeoutError:
            logger.error("Groq API request timed out")
            return "⏳ AI service is taking too long to respond. Try again later."
        except Exception as e:
            logger.error(f"Unexpected AI error: {e}")
            return "❌ An unexpected error occurred with the AI."

    @commands.Cog.listener()
    async def on_message(self, message):
        if not self.should_respond(message):
            return

        self.last_message_time[message.channel.id] = datetime.now().timestamp()

        async with message.channel.typing():
            response = await self.get_ai_response(message)
            if response:
                if len(response) > 2000:
                    for chunk in [response[i:i+2000] for i in range(0, len(response), 2000)]:
                        await message.reply(chunk, mention_author=False)
                else:
                    await message.reply(response, mention_author=False)

    @commands.hybrid_command(name="reset_chat", description="Reset AI conversation context")
    async def reset_chat(self, ctx):
        if not self.enabled:
            await ctx.send("❌ AI features disabled. Missing API key.", ephemeral=True)
            return

        self.conversation_context[ctx.channel.id] = []
        await ctx.send("✅ Conversation context has been reset.", ephemeral=True)

    @commands.hybrid_command(name="chat", description="Chat with AI directly")
    async def chat_command(self, ctx, *, message: str):
        if not self.enabled:
            await ctx.send("❌ AI disabled. Configure API key.", ephemeral=True)
            return

        class MockMessage:
            def __init__(self, content, author, channel, guild):
                self.clean_content = content
                self.author = author
                self.channel = channel
                self.guild = guild

        mock = MockMessage(message, ctx.author, ctx.channel, ctx.guild)

        async with ctx.channel.typing():
            response = await self.get_ai_response(mock)
            if response:
                await ctx.send(response)

    @commands.hybrid_command(name="set_model", description="Set AI model (Admin only)")
    @commands.has_permissions(administrator=True)
    async def set_model(self, ctx, model_name: str):
        available_models = [
            "llama-3.1-8b-instant",
            "llama-3.3-70b-versatile",
            "gemma-7b-it",
            "mixtral-8x7b-32768",
            "meta-llama/llama-guard-4-12b",
        ]

        if model_name not in available_models:
            await ctx.send(f"❌ Invalid model. Available: {', '.join(available_models)}", ephemeral=True)
            return

        self.model = model_name
        await ctx.send(f"✅ Model set to: {model_name}", ephemeral=True)
        logger.info(f"AI model changed to: {model_name}")

# ============================================================================
# COG SETUP
# ============================================================================

async def setup(bot):
    await bot.add_cog(AIChatCog(bot))
    logger.info("Groq AI cog setup complete")
