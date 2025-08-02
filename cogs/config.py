import discord
from discord.ext import commands
import logging
from utils import database

logger = logging.getLogger(__name__)

class ConfigCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logging.info("Config cog initialized")

    @commands.hybrid_command(name="config", description="Configure bot channels")
    @commands.has_permissions(manage_guild=True)
    async def config_command(self, ctx, channel_type: str, channel: discord.TextChannel):
        valid_types = ['welcome', 'log', 'announcement']  # Added 'announcement'
        channel_type = channel_type.lower()
        
        if channel_type not in valid_types:
            await ctx.send(
                f"Invalid channel type. Valid types: {', '.join(valid_types)}",
                ephemeral=True
            )
            return
        
        field_name = f"{channel_type}_channel_id"
        success = await database.update_guild_config(
            self.bot.guild_configs,
            str(ctx.guild.id),
            {field_name: str(channel.id)}
        )
        
        if success:
            await ctx.send(f"✅ Set {channel_type} channel to {channel.mention}", ephemeral=True)
        else:
            await ctx.send("❌ Failed to update configuration", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ConfigCog(bot))
    logging.info("Config cog setup complete")