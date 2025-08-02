import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class SyncCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("Sync cog initialized")
    
    @commands.hybrid_command(name="sync", description="Sync slash commands")
    @commands.is_owner()
    async def sync_command(self, ctx):
        try:
            await self.bot.tree.sync()
            await ctx.send("✅ Slash commands synced globally!")
            logger.info("Slash commands synced")
        except Exception as e:
            await ctx.send(f"❌ Error: {e}")
            logger.error(f"Error syncing commands: {str(e)}")

async def setup(bot):
    await bot.add_cog(SyncCog(bot))
    logger.info("Sync cog setup complete")