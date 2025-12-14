#!/usr/bin/env python3
"""
AI Chat Cog - Groq AI Integration
Persona: Gwen Stacy (Spider-Verse)
Memory: Per-user + per-channel
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

        self.default_model = "llama-3.1-8b-instant"
        self.model = os.getenv("GROQ_MODEL", self.default_model)

        # MEMORY
        self.channel_context = {}   # channel_id -> messages
        self.user_memory = {}       # user_id -> messages

        self.last_message_time = {}
        self.cooldown = 2

        self.enabled = bool(self.api_key)

        if self.enabled:
            logger.info(f"Groq AI initialized with model: {self.model}")
        else:
            logger.warning("Groq API key missing. AI disabled.")

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def get_display_name(self, message):
        if message.guild:
            return message.author.display_name
        return message.author.name

    def should_respond(self, message):
        if not self.enabled:
            return False
        if message.author.bot:
            return False

        # Respond to mentions or DMs
        if isinstance(message.channel, discord.DMChannel):
            return True
        if self.bot.user in message.mentions:
            return True

        return False

    async def query_groq(self, payload, headers):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=15
            ) as resp:
                return resp.status, await resp.json()

    # ------------------------------------------------------------------
    # CORE AI LOGIC
    # ------------------------------------------------------------------

    async def get_ai_response(self, message):
        user_id = message.author.id
        channel_id = message.channel.id
        user_name = self.get_display_name(message)

        # Init memory
        self.user_memory.setdefault(user_id, [])
        self.channel_context.setdefault(channel_id, [])

        # Clean content (remove bot mention)
        content = message.clean_content.replace(
            f"@{self.bot.user.name}", ""
        ).strip()

        # SYSTEM PROMPT (GWEN STACY)
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are Gwen Stacy (Spider-Gwen from Spider-Verse).\n"
                    f"The user's name is {user_name}.\n\n"
                    "Personality:\n"
                    "- Confident, witty, playful, emotionally intelligent\n"
                    "- Casual modern speech, light sarcasm\n"
                    "- Caring and supportive when needed\n\n"
                    "Rules:\n"
                    "- Never mention being an AI or assistant\n"
                    "- Never break character\n"
                    "- Use the user's name naturally\n"
                    "- Respond like a real person\n"
                    "- Use at most one emoji per message\n"
                )
            }
        ]

        # USER MEMORY (personal history)
        for msg in self.user_memory[user_id][-6:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        # CHANNEL CONTEXT (conversation flow)
        for msg in self.channel_context[channel_id][-6:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        # Current message
        messages.append({"role": "user", "content": content})

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
            status, data = await self.query_groq(payload, headers)

            if status != 200:
                error_msg = data.get("error", {}).get("message", "")
                if "decommissioned" in error_msg.lower():
                    self.model = self.default_model
                    payload["model"] = self.default_model
                    status, data = await self.query_groq(payload, headers)

            if status != 200:
                logger.error(f"Groq error: {status} - {data}")
                return "⚠️ Something went wrong. Try again in a bit."

            response_text = data["choices"][0]["message"]["content"]
            timestamp = datetime.now().isoformat()

            # SAVE MEMORY
            self.user_memory[user_id].extend([
                {"role": "user", "content": content, "timestamp": timestamp},
                {"role": "assistant", "content": response_text, "timestamp": timestamp}
            ])

            self.channel_context[channel_id].extend([
                {"role": "user", "content": content, "timestamp": timestamp},
                {"role": "assistant", "content": response_text, "timestamp": timestamp}
            ])

            # LIMIT MEMORY
            if len(self.user_memory[user_id]) > 30:
                self.user_memory[user_id] = self.user_memory[user_id][-20:]

            if len(self.channel_context[channel_id]) > 20:
                self.channel_context[channel_id] = self.channel_context[channel_id][-10:]

            return response_text

        except asyncio.TimeoutError:
            return "⏳ Took too long… multiverse lag."
        except Exception as e:
            logger.exception("AI error")
            return "❌ Something weird just happened."

    # ------------------------------------------------------------------
    # EVENTS
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message):
        if not self.should_respond(message):
            return

        async with message.channel.typing():
            response = await self.get_ai_response(message)
            if response:
                if len(response) > 2000:
                    for chunk in range(0, len(response), 2000):
                        await message.reply(
                            response[chunk:chunk+2000],
                            mention_author=False
                        )
                else:
                    await message.reply(response, mention_author=False)

    # ------------------------------------------------------------------
    # COMMANDS
    # ------------------------------------------------------------------

    @commands.hybrid_command(name="reset_chat", description="Reset channel conversation")
    async def reset_chat(self, ctx):
        self.channel_context[ctx.channel.id] = []
        await ctx.send("🕷️ Cleared the vibe in this channel.", ephemeral=True)

    @commands.hybrid_command(name="reset_me", description="Reset your personal memory")
    async def reset_me(self, ctx):
        self.user_memory[ctx.author.id] = []
        await ctx.send("💙 Fresh start. I won’t hold the past against you.", ephemeral=True)

    @commands.hybrid_command(name="set_model", description="Set AI model (Admin only)")
    @commands.has_permissions(administrator=True)
    async def set_model(self, ctx, model_name: str):
        available_models = [
            "llama-3.1-8b-instant",
            "llama-3.3-70b-versatile",
            "gemma-7b-it",
            "mixtral-8x7b-32768",
        ]

        if model_name not in available_models:
            await ctx.send(
                f"❌ Invalid model.\nAvailable: {', '.join(available_models)}",
                ephemeral=True
            )
            return

        self.model = model_name
        await ctx.send(f"✅ Model set to **{model_name}**", ephemeral=True)

# ------------------------------------------------------------------
# SETUP
# ------------------------------------------------------------------

async def setup(bot):
    await bot.add_cog(AIChatCog(bot))
    logger.info("Gwen Stacy AI cog loaded")
