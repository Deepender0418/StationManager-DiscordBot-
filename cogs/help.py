import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("Help cog initialized")
    
    @commands.hybrid_command(name="help", description="Show command information")
    async def help_command(self, ctx, command_name: str = None):
        command_templates = {
            "config": {
                "description": "Set channel configurations",
                "usage": "!config <type> <channel>",
                "examples": ["!config welcome #welcome-channel", "!config log #mod-logs", "!config announcement #announcements"],
                "types": ["welcome", "log", "announcement"]
            },
            "birthday": {
                "description": "Set a user's birthday (Admin only)",
                "usage": "!birthday @user MM-DD",
                "examples": ["!birthday @John 05-15"]
            },
            "deletebirthday": {
                "description": "Delete a user's birthday (Admin only)",
                "usage": "!deletebirthday @user",
                "examples": ["!deletebirthday @John"]
            },
            "announce": {  # NEW COMMAND
                "description": "Send an official server announcement (Admin only)",
                "usage": "!announce [message]",
                "examples": ["!announce Server maintenance at 10PM", "!announce Join our tournament this Saturday!"]
            },
            "sync": {
                "description": "Sync slash commands (Owner only)",
                "usage": "!sync",
                "examples": []
            },
            "help": {
                "description": "Show command help information",
                "usage": "!help [command]",
                "examples": ["!help", "!help birthday"]
            }
        }

        if not command_name:
            embed = discord.Embed(title="Command Help", description="List of available commands", color=0x00ff00)

        if command_name:
            cmd = command_templates.get(command_name.lower())
            if cmd:
                embed = discord.Embed(title=f"Help: {command_name}", color=0x00ff00)
                embed.add_field(name="Description", value=cmd["description"], inline=False)
                embed.add_field(name="Usage", value=f"`{cmd['usage']}`", inline=False)
                
                # Add types for config command
                if command_name.lower() == "config":
                    types = ", ".join(cmd["types"])
                    embed.add_field(name="Channel Types", value=types, inline=False)
                
                if "examples" in cmd and cmd["examples"]:
                    examples = "\n".join([f"`{ex}`" for ex in cmd["examples"]])
                    embed.add_field(name="Examples", value=examples, inline=False)
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Command not found. Use `!help` for all commands.")
        else:
            embed = discord.Embed(title="Command Help", description="List of available commands", color=0x00ff00)
            for name, info in command_templates.items():
                # Add emoji for admin commands
                emoji = "🔐 " if name in ["config", "birthday", "deletebirthday", "announce", "sync"] else ""
                embed.add_field(
                    name=f"{emoji}{name}",
                    value=f"{info['description']}\n`{info['usage']}`",
                    inline=False
                )
            embed.set_footer(text="Commands with 🔐 require special permissions\nUse !help [command] for more details")
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
    logger.info("Help cog setup complete")