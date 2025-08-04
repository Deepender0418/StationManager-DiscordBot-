#!/usr/bin/env python3
"""
Help cog - Command help system
"""

import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("Help cog initialized")
    
    @commands.hybrid_command(name="show", description="Show command template")
    async def show_template(self, ctx, command_name: str):
        """Show template for a specific command"""
        command_name = command_name.lower()
        
        if command_name in self.bot.command_templates:
            template = self.bot.command_templates[command_name]
            
            embed = discord.Embed(
                title=f"🤖 {template['bot_info']}",
                description=f"**Command:** `!{command_name}`\n**Description:** {template['description']}",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="📋 Usage",
                value=f"`{template['usage']}`",
                inline=False
            )
            
            if template['examples']:
                examples = "\n".join([f"`{ex}`" for ex in template['examples']])
                embed.add_field(
                    name="💡 Examples",
                    value=examples,
                    inline=False
                )
            
            embed.set_footer(text="💡 Use this command to see how to use any command!")
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Command `!{command_name}` not found. Use `!templates` to see all available commands.", ephemeral=True)

    @commands.hybrid_command(name="templates", description="Show all command templates")
    async def show_templates(self, ctx):
        """Show all available command templates"""
        embed = discord.Embed(
            title="🤖 Command Templates",
            description="Here are all the available commands and their templates:",
            color=discord.Color.blue()
        )
        
        # Group commands by bot type
        bot_groups = {}
        for cmd_name, cmd_info in self.bot.command_templates.items():
            bot_type = cmd_info['bot_info']
            if bot_type not in bot_groups:
                bot_groups[bot_type] = []
            bot_groups[bot_type].append((cmd_name, cmd_info))
        
        # Add each bot group
        for bot_type, commands in bot_groups.items():
            cmd_list = []
            for cmd_name, cmd_info in commands:
                cmd_list.append(f"`!{cmd_name}` - {cmd_info['description']}")
            
            embed.add_field(
                name=bot_type,
                value="\n".join(cmd_list),
                inline=False
            )
        
        embed.set_footer(text="💡 Type any command to see its template!")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="help", description="Show command information")
    async def help_command(self, ctx, command_name: str = None):
        """Show help for commands"""
        # Check for common typos and provide helpful suggestions
        if command_name and command_name.lower() == "introbot":
            embed = discord.Embed(
                title="🤖 Command Not Found",
                description="It looks like you might be looking for the **bot introduction** command!",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="💡 Did you mean?",
                value="`!botintro` - Bot introduces itself and explains its features",
                inline=False
            )
            embed.add_field(
                name="📋 Usage",
                value="`!botintro` (Admin only)",
                inline=False
            )
            embed.add_field(
                name="💭 What it does",
                value="Sends a beautiful introduction message to your announcement channel explaining all the bot's features!",
                inline=False
            )
            embed.set_footer(text="💡 Common mistake: 'introbot' → 'botintro'")
            await ctx.send(embed=embed)
            return
        
        command_templates = {
            "config": {
                "description": "Set channel configurations",
                "usage": "!config <type> <channel>",
                "examples": ["!config welcome #welcome-channel", "!config log #mod-logs", "!config announcement #announcements"],
                "types": ["welcome", "log", "announcement"]
            },
            "birthday": {
                "description": "Set birthday (Admin: @user MM-DD [message] | User: MM-DD)",
                "usage": "!birthday @user MM-DD [message] (Admin) | !birthday MM-DD (User)",
                "examples": [
                    "!birthday @John 05-15", 
                    "!birthday @John 05-15 Happy Birthday {USER_MENTION}! Hope you have an amazing day, {USER_NAME}!",
                    "!birthday 08-03"
                ],
                "template_vars": "Use {USER_MENTION} to mention the user, {USER_NAME} for their display name"
            },
            "deletebirthday": {
                "description": "Delete a user's birthday (Admin only)",
                "usage": "!deletebirthday @user",
                "examples": ["!deletebirthday @John"]
            },
            "listbirthdays": {
                "description": "List all birthdays in the server (Admin only)",
                "usage": "!listbirthdays",
                "examples": ["!listbirthdays"]
            },
            "testbirthday": {
                "description": "Test birthday announcement for a user (Admin only)",
                "usage": "!testbirthday [@user]",
                "examples": ["!testbirthday", "!testbirthday @John"]
            },
            "announce": {
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
            },
            "testevents": {
                "description": "Test daily events announcement (Admin only)",
                "usage": "!testevents",
                "examples": ["!testevents"]
            },
            "testwelcome": {
                "description": "Test welcome message (Admin only)",
                "usage": "!testwelcome",
                "examples": ["!testwelcome"]
            },
            "botintro": {
                "description": "Bot introduces itself and explains its features (Admin only)",
                "usage": "!botintro",
                "examples": ["!botintro"]
            },
            "templates": {
                "description": "Show all command templates",
                "usage": "!templates",
                "examples": ["!templates"]
            },
            "invites": {
                "description": "View invite statistics (Admin only)",
                "usage": "!invites",
                "examples": ["!invites"]
            },
            "invitestats": {
                "description": "View detailed invite statistics (Admin only)",
                "usage": "!invitestats",
                "examples": ["!invitestats"]
            }
        }

        if command_name:
            cmd = command_templates.get(command_name.lower())
            if cmd:
                embed = discord.Embed(title=f"Help: {command_name}", color=0x00ff00)
                embed.add_field(name="Description", value=cmd["description"], inline=False)
                embed.add_field(name="Usage", value=f"`{cmd['usage']}`", inline=False)

                if command_name.lower() == "config":
                    types = ", ".join(cmd["types"])
                    embed.add_field(name="Channel Types", value=types, inline=False)

                if "template_vars" in cmd:
                    embed.add_field(name="Template Variables", value=cmd["template_vars"], inline=False)

                if "examples" in cmd and cmd["examples"]:
                    examples = "\n".join([f"`{ex}`" for ex in cmd["examples"]])
                    embed.add_field(name="Examples", value=examples, inline=False)
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Command not found. Use `!help` for all commands.")
        else:
            embed = discord.Embed(title="Command Help", description="List of available commands", color=0x00ff00)
            for name, info in command_templates.items():
                emoji = "🔐 " if name in ["config", "birthday", "deletebirthday", "listbirthdays", "testbirthday", "announce", "sync"] else ""
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
