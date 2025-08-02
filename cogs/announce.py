import discord
from discord.ext import commands
import logging
from utils import database

logger = logging.getLogger(__name__)

class AnnounceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("Announce cog initialized")

    @commands.hybrid_command(name="announce", description="Send an official server announcement")
    @commands.has_permissions(administrator=True)
    async def announce(self, ctx, *, message: str):
        """Send an announcement as the bot (Admin only)"""
        try:
            # Get custom message config
            config = await database.get_guild_config(
                self.bot.guild_configs,
                str(ctx.guild.id)
            )
            
            # Check if announcement channel is set
            announcement_channel_id = config.get('announcement_channel_id') if config else None
            if not announcement_channel_id:
                await ctx.send("❌ Announcement channel not configured! Set it with `/config announcement #channel`", ephemeral=True)
                return
            
            # Get the announcement channel
            announcement_channel = self.bot.get_channel(int(announcement_channel_id))
            if not announcement_channel:
                await ctx.send("❌ Announcement channel not found! It might have been deleted.", ephemeral=True)
                return
            
            # Create embed for professional announcement
            embed = discord.Embed(
                title="📢 Server Announcement",
                description=message,
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Announced by {ctx.author.display_name}")
            
            # Send the announcement
            await announcement_channel.send(embed=embed)
            
            # Confirm to admin
            await ctx.send(f"✅ Announcement sent to {announcement_channel.mention}!", ephemeral=True)
            
            # Log the announcement
            log_channel_id = config.get('log_channel_id') if config else None
            if log_channel_id:
                log_channel = self.bot.get_channel(int(log_channel_id))
                if log_channel:
                    await log_channel.send(f"📢 **Announcement**: {ctx.author.mention} sent an announcement")
            
        except Exception as e:
            await ctx.send(f"❌ Error sending announcement: {str(e)}", ephemeral=True)
            logger.error(f"Announce command error: {str(e)}")

    @announce.error
    async def announce_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("⛔ You need administrator permissions to use this command!", ephemeral=True)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("⚠️ Please provide a message to announce!\nExample: `/announce Server maintenance at 10PM`", ephemeral=True)
        else:
            await ctx.send(f"❌ Unexpected error: {str(error)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AnnounceCog(bot))
    logger.info("Announce cog setup complete")