#!/usr/bin/env python3
"""
AI Chat Cog - Gwen Stacy (Spider-Verse)
Groq API + MongoDB Persistent Memory
Hybrid RAM + DB memory (FAST)
"""

import discord
from discord.ext import commands
import aiohttp
import asyncio
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class AIChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # ---------------- AI CONFIG ----------------
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.api_key = os.getenv("GROQ_API_KEY")

        self.default_model = "llama-3.1-8b-instant"
        self.model = os.getenv("GROQ_MODEL", self.default_model)

        self.enabled = bool(self.api_key)

        # ---------------- DATABASE ----------------
        self.db = bot.mongo
        self.user_collection = self.db.user_memory
        self.channel_collection = self.db.channel_memory

        # ---------------- MEMORY CACHE (RAM) ----------------
        self.user_memory_cache = {}      # user_id -> list
        self.channel_memory_cache = {}   # channel_id -> list

        # ---------------- COOLDOWN ----------------
        self.last_message_time = {}
        self.cooldown = 2

        if self.enabled:
            logger.info("🕷️ Gwen Stacy AI loaded")
        else:
            logger.warning("Groq API key missing — AI disabled")

    # ======================================================
    # HELPERS
    # ======================================================

    def get_display_name(self, message):
        if message.guild:
            return message.author.display_name
        return message.author.name

    def should_respond(self, message):
        if not self.enabled:
            return False
        if message.author.bot:
            return False
        if isinstance(message.channel, discord.DMChannel):
            return True
        if self.bot.user in message.mentions:
            return True
        return False

    # ======================================================
    # MEMORY (HYBRID CACHE + MONGO)
    # ======================================================

    async def get_user_memory(self, user_id):
        if user_id in self.user_memory_cache:
            return self.user_memory_cache[user_id]

        doc = await self.user_collection.find_one({"user_id": user_id})
        memory = doc["messages"] if doc else []
        self.user_memory_cache[user_id] = memory
        return memory

    async def get_channel_memory(self, channel_id):
        if channel_id in self.channel_memory_cache:
            return self.channel_memory_cache[channel_id]

        doc = await self.channel_collection.find_one({"channel_id": channel_id})
        memory = doc["messages"] if doc else []
        self.channel_memory_cache[channel_id] = memory
        return memory

    async def save_user_memory(self, user_id, memory):
        await self.user_collection.update_one(
            {"user_id": user_id},
            {"$set": {"messages": memory}},
            upsert=True
        )

    async def save_channel_memory(self, channel_id, memory):
        await self.channel_collection.update_one(
            {"channel_id": channel_id},
            {"$set": {"messages": memory}},
            upsert=True
        )

    # ======================================================
    # GROQ REQUEST
    # ======================================================

    async def query_groq(self, payload, headers):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=15
            ) as resp:
                return resp.status, await resp.json()

    # ======================================================
    # CORE AI LOGIC
    # ======================================================

    async def get_ai_response(self, message):
        user_id = message.author.id
        channel_id = message.channel.id
        user_name = self.get_display_name(message)

        content = message.clean_content.replace(
            f"@{self.bot.user.name}", ""
        ).strip()

        user_memory = await self.get_user_memory(user_id)
        channel_memory = await self.get_channel_memory(channel_id)

        # ---------------- SYSTEM PROMPT ----------------
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are Gwen Stacy (Spider-Gwen from Spider-Verse).\n"
                    f"The user's name is {user_name}.\n\n"
                    "Personality:\n"
                    "- Confident, witty, playful, emotionally intelligent\n"
                    "- Casual modern speech, light sarcasm\n"
                    "- Caring when needed\n\n"
                    "Rules:\n"
                    "- Never mention being an AI\n"
                    "- Never break character\n"
                    "- Use the user's name naturally\n"
                    "- Use at most one emoji per reply\n"
                )
            }
        ]

        # ---------------- MEMORY INJECTION ----------------
        for msg in user_memory[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        for msg in channel_memory[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": content})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            status, data = await self.query_groq(payload, headers)

            if status != 200:
                err = data.get("error", {}).get("message", "")
                if "decommissioned" in err.lower():
                    self.model = self.default_model
                    payload["model"] = self.default_model
                    status, data = await self.query_groq(payload, headers)

            if status != 200:
                logger.error(f"Groq error: {status} - {data}")
                return "⚠️ Something went wrong."

            response = data["choices"][0]["message"]["content"]
            ts = datetime.now().isoformat()

            # ---------------- SAVE MEMORY ----------------
            user_memory.extend([
                {"role": "user", "content": content, "ts": ts},
                {"role": "assistant", "content": response, "ts": ts}
            ])

            channel_memory.extend([
                {"role": "user", "content": content, "ts": ts},
                {"role": "assistant", "content": response, "ts": ts}
            ])

            # LIMIT MEMORY
            user_memory[:] = user_memory[-20:]
            channel_memory[:] = channel_memory[-10:]

            # Async save (non-blocking)
            asyncio.create_task(self.save_user_memory(user_id, user_memory))
            asyncio.create_task(self.save_channel_memory(channel_id, channel_memory))

            return response

        except asyncio.TimeoutError:
            return "⏳ Multiverse lag. Try again."
        except Exception:
            logger.exception("AI error")
            return "❌ Something broke."

    # ======================================================
    # EVENTS
    # ======================================================

    @commands.Cog.listener()
    async def on_message(self, message):
        if not self.should_respond(message):
            return

        async with message.channel.typing():
            reply = await self.get_ai_response(message)
            if reply:
                if len(reply) > 2000:
                    for i in range(0, len(reply), 2000):
                        await message.reply(reply[i:i+2000], mention_author=False)
                else:
                    await message.reply(reply, mention_author=False)

    # ======================================================
    # COMMANDS
    # ======================================================

    @commands.hybrid_command(name="reset_chat", description="Reset channel memory")
    async def reset_chat(self, ctx):
        await self.channel_collection.delete_one({"channel_id": ctx.channel.id})
        self.channel_memory_cache.pop(ctx.channel.id, None)
        await ctx.send("🕷️ Cleared the vibe here.", ephemeral=True)

    @commands.hybrid_command(name="reset_me", description="Reset your memory")
    async def reset_me(self, ctx):
        await self.user_collection.delete_one({"user_id": ctx.author.id})
        self.user_memory_cache.pop(ctx.author.id, None)
        await ctx.send("💙 Fresh start. No past baggage.", ephemeral=True)

# ======================================================
# SETUP
# ======================================================

async def setup(bot):
    await bot.add_cog(AIChatCog(bot))
    logger.info("🕷️ Gwen Stacy AI cog ready")
