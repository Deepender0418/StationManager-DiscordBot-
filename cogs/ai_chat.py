import os
import discord
from discord.ext import commands, tasks
from groq import Groq
import logging

logger = logging.getLogger(__name__)

class GwenChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.owner_id = int(os.getenv("OWNER_ID"))
        self.tease_task.start()

    def cog_unload(self):
        self.tease_task.cancel()

    async def generate_tease(self, owner_mention: str) -> str:
        try:
            chat_completion = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are Gwen Stacy from Spider-Verse. "
                            "Your personality is witty, playful, slightly flirty, and teasing. "
                            "ALWAYS respond with very short messages (1 sentence max). "
                            "ALWAYS include spider/web-related emojis like 🕷️🕸️💥✨ in your responses."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Tease {owner_mention} playfully in one short sentence."
                    }
                ]
            )
            return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq tease generation failed: {e}")
            return f"Hey {owner_mention}, looks like I tripped on my own webs 🕸️💥."

    @tasks.loop(minutes=30)
    async def tease_task(self):
        await self.bot.wait_until_ready()
        owner = self.bot.get_user(self.owner_id)
        if not owner:
            return
        tease = await self.generate_tease(owner.mention)
        try:
            await owner.send(tease)
        except discord.Forbidden:
            logger.warning("Cannot DM owner. They might have DMs disabled.")

    @commands.command(name="gwen")
    async def gwen_chat(self, ctx, *, message: str):
        """Chat with Gwen Stacy directly using command."""
        try:
            chat_completion = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are Gwen Stacy from Spider-Verse. "
                            "You speak playfully, teasingly, with light romantic undertones. "
                            "ALWAYS keep responses very short (1-2 sentences max). "
                            "ALWAYS include emojis like 🕷️🕸️💫✨ in your replies."
                        )
                    },
                    {"role": "user", "content": message}
                ]
            )
            response = chat_completion.choices[0].message.content.strip()
            await ctx.send(response)
        except Exception as e:
            logger.error(f"Groq chat failed: {e}")
            await ctx.send("Oops, my spider-sense is tingling too hard 🕷️💥.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # If bot is mentioned in the message
        if self.bot.user.mentioned_in(message):
            try:
                user_input = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
                if not user_input:
                    user_input = "Say something playful to me."

                chat_completion = self.client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are Gwen Stacy from Spider-Verse. "
                                "Respond playfully and teasingly with very short answers. "
                                "ALWAYS include emojis like 🕷️🕸️✨ in your responses. "
                                "Keep it to 1-2 sentences maximum."
                            )
                        },
                        {"role": "user", "content": user_input}
                    ]
                )
                response = chat_completion.choices[0].message.content.strip()
                await message.channel.send(response)
            except Exception as e:
                logger.error(f"Groq mention chat failed: {e}")
                await message.channel.send("Oops, I tangled myself in my web 🕸️💥.")

async def setup(bot):
    await bot.add_cog(GwenChat(bot))
