#!/usr/bin/env python3
"""
Help Cog - Command Help and Documentation System

This cog provides a comprehensive help system for the Discord bot.
It includes functionality to:
- Display general help information
- Show detailed command help
- List all available commands
- Provide command templates and examples
- Handle command suggestions and typos
- Display bot information and usage instructions

The help system is designed to be user-friendly and provides
both basic and advanced help options for different user needs.
"""

import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class HelpCog(commands.Cog):
    """
    Help system cog that provides command documentation and assistance
    
    This cog provides:
    - General help command with bot overview
    - Detailed command help with examples
    - Command template system
    - Typo detection and suggestions
    - Bot information and usage instructions
    """
    
    def __init__(self, bot):
        """
        Initialize the help cog
        
        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        logger.info("Help cog initialized")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the cog is ready and loaded"""
        logger.info("Help cog ready")
    
    # ============================================================================
    # HELP COMMANDS SECTION
    # ============================================================================
    
    @commands.hybrid_command(name="help", description="Show command help information")
    async def help_command(self, ctx, command_name: str = None):
        """
        Show help information for commands
        
        This command provides help in two ways:
        1. General help: Shows overview of all available commands
        2. Specific help: Shows detailed information for a specific command
        
        Args:
            ctx: Discord context
            command_name: Optional specific command to get help for
        """
        try:
            if command_name:
                # ============================================================================
                # SPECIFIC COMMAND HELP SECTION
                # ============================================================================
                
                await self.show_command_help(ctx, command_name)
            else:
                # ============================================================================
                # GENERAL HELP SECTION
                # ============================================================================
                
                await self.show_general_help(ctx)
                
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error in help command: {str(e)}")
    
    async def show_general_help(self, ctx):
        """
        Show general help information with command overview
        
        This method creates a comprehensive overview of all available
        commands organized by category for easy navigation.
        
        Args:
            ctx: Discord context
        """
        # Create main help embed
        embed = discord.Embed(
            title="🤖 Discord Server Manager Bot - Help",
            description="Welcome to the help system! Here are all the available commands organized by category.",
            color=discord.Color.blue()
        )
        
        # ============================================================================
        # COMMAND CATEGORIES SECTION
        # ============================================================================
        
        # Birthday commands
        embed.add_field(
            name="🎂 **Birthday Commands**",
            value="`!birthday` - Set birthdays\n`!testbirthday` - Test birthday announcements\n`!listbirthdays` - List all birthdays\n`!deletebirthday` - Delete a birthday",
            inline=False
        )
        
        # Configuration commands
        embed.add_field(
            name="⚙️ **Configuration Commands**",
            value="`!config` - Set channel configurations\n`!testwelcome` - Test welcome messages\n`!botintro` - Bot introduction",
            inline=False
        )
        
        # Event commands
        embed.add_field(
            name="📅 **Event Commands**",
            value="`!testevents` - Test daily events\n`!announce` - Send announcements",
            inline=False
        )
        
        # Invite tracking commands
        embed.add_field(
            name="🎫 **Invite Tracking Commands**",
            value="`!invites` - View invite statistics\n`!invitestats` - Detailed invite analytics",
            inline=False
        )
        
        # Help commands
        embed.add_field(
            name="❓ **Help Commands**",
            value="`!help [command]` - Get help for specific command\n`!templates` - Show all command templates\n`!show <command>` - Show command template",
            inline=False
        )
        
        # ============================================================================
        # USAGE INSTRUCTIONS SECTION
        # ============================================================================
        
        embed.add_field(
            name="💡 **How to Use**",
            value="• Use `!help <command>` for detailed help on a specific command\n• Use `!templates` to see all available commands\n• Most commands require admin permissions\n• Commands with `[Admin]` are admin-only",
            inline=False
        )
        
        # Set footer with additional information
        embed.set_footer(text="💡 Tip: Use !help <command> for detailed information about any command!")
        
        await ctx.send(embed=embed, ephemeral=True)
    
    async def show_command_help(self, ctx, command_name: str):
        """
        Show detailed help for a specific command
        
        This method provides comprehensive information about a specific
        command including usage, examples, and descriptions.
        
        Args:
            ctx: Discord context
            command_name: Name of the command to get help for
        """
        # Normalize command name
        command_name = command_name.lower().strip()
        
        # Check if command exists in templates
        if command_name in self.bot.command_templates:
            template = self.bot.command_templates[command_name]
            
            # Create detailed help embed
            embed = discord.Embed(
                title=f"🤖 {template['bot_info']}",
                description=f"**Command:** `!{command_name}`\n**Description:** {template['description']}",
                color=discord.Color.green()
            )
            
            # Add usage information
            embed.add_field(
                name="📋 **Usage**",
                value=f"`{template['usage']}`",
                inline=False
            )
            
            # Add examples if available
            if template['examples']:
                examples = "\n".join([f"`{ex}`" for ex in template['examples']])
                embed.add_field(
                    name="💡 **Examples**",
                    value=examples,
                    inline=False
                )
            
            # Add additional information
            embed.add_field(
                name="ℹ️ **Additional Info**",
                value="• This command is part of the bot's core functionality\n• Make sure you have the required permissions\n• Use the examples above as a guide",
                inline=False
            )
            
            embed.set_footer(text=f"💡 Use !{command_name} to execute this command")
            
            await ctx.send(embed=embed, ephemeral=True)
            
        else:
            # Command not found - provide suggestions
            await self.handle_command_not_found(ctx, command_name)
    
    async def handle_command_not_found(self, ctx, command_name: str):
        """
        Handle cases where a command is not found
        
        This method provides helpful suggestions when users try to get
        help for a command that doesn't exist or has a typo.
        
        Args:
            ctx: Discord context
            command_name: The command name that wasn't found
        """
        # Check for common typos
        typo_suggestions = {
            "introbot": "botintro",
            "botintro": "botintro",
            "birthday": "birthday",
            "config": "config",
            "help": "help"
        }
        
        if command_name in typo_suggestions:
            suggested_command = typo_suggestions[command_name]
            
            embed = discord.Embed(
                title="🤖 Command Not Found",
                description=f"Did you mean **`!{suggested_command}`**?",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="💡 **Suggestion**",
                value=f"Try using `!help {suggested_command}` for help with the correct command.",
                inline=False
            )
            
            embed.set_footer(text=f"💡 Common typo: '{command_name}' → '{suggested_command}'")
            
            await ctx.send(embed=embed, ephemeral=True)
            
        else:
            # No suggestion available
            embed = discord.Embed(
                title="❌ Command Not Found",
                description=f"The command `!{command_name}` was not found.",
                color=discord.Color.red()
            )
            
            embed.add_field(
                name="💡 **What to do**",
                value="• Use `!help` to see all available commands\n• Use `!templates` to browse command templates\n• Check your spelling and try again",
                inline=False
            )
            
            embed.set_footer(text="💡 Use !help to see all available commands")
            
            await ctx.send(embed=embed, ephemeral=True)
    
    # ============================================================================
    # TEMPLATE COMMANDS SECTION
    # ============================================================================
    
    @commands.hybrid_command(name="templates", description="Show all command templates")
    async def show_templates(self, ctx):
        """
        Show all available command templates
        
        This command displays a comprehensive list of all available
        commands with their descriptions for easy reference.
        """
        try:
            # Create templates embed
            embed = discord.Embed(
                title="📋 All Command Templates",
                description="Here are all the commands available in this bot:",
                color=discord.Color.purple()
            )
            
            # ============================================================================
            # COMMAND LISTING SECTION
            # ============================================================================
            
            # Group commands by category for better organization
            categories = {
                "🎂 Birthday": ["birthday", "testbirthday", "listbirthdays", "deletebirthday"],
                "⚙️ Configuration": ["config", "testwelcome", "botintro"],
                "📅 Events": ["testevents", "announce"],
                "🎫 Invite Tracking": ["invites", "invitestats"],
                "❓ Help": ["help", "templates", "show"]
            }
            
            for category, commands in categories.items():
                category_commands = []
                
                for cmd in commands:
                    if cmd in self.bot.command_templates:
                        template = self.bot.command_templates[cmd]
                        category_commands.append(f"`!{cmd}` - {template['description']}")
                
                if category_commands:
                    # Join commands with line breaks for better formatting
                    commands_text = "\n".join(category_commands)
                    embed.add_field(
                        name=category,
                        value=commands_text,
                        inline=False
                    )
            
            # Add usage instructions
            embed.add_field(
                name="💡 **How to Use**",
                value="• Use `!help <command>` for detailed help\n• Use `!show <command>` to see command template\n• Commands marked with [Admin] require admin permissions",
                inline=False
            )
            
            embed.set_footer(text=f"📊 Total Commands: {len(self.bot.command_templates)}")
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error showing templates: {str(e)}")
    
    @commands.hybrid_command(name="show", description="Show command template")
    async def show_template(self, ctx, command_name: str):
        """
        Show detailed template for a specific command
        
        This command provides the same detailed information as the help
        command but is specifically for showing command templates.
        
        Args:
            ctx: Discord context
            command_name: Name of the command to show template for
        """
        try:
            # Normalize command name
            command_name = command_name.lower().strip()
            
            # Check if command exists in templates
            if command_name in self.bot.command_templates:
                template = self.bot.command_templates[command_name]
                
                # Create template embed
                embed = discord.Embed(
                    title=f"📋 Command Template: !{command_name}",
                    description=f"**Description:** {template['description']}",
                    color=discord.Color.blue()
                )
                
                # Add usage information
                embed.add_field(
                    name="📋 **Usage**",
                    value=f"`{template['usage']}`",
                    inline=False
                )
                
                # Add examples if available
                if template['examples']:
                    examples = "\n".join([f"`{ex}`" for ex in template['examples']])
                    embed.add_field(
                        name="💡 **Examples**",
                        value=examples,
                        inline=False
                    )
                
                # Add bot info
                embed.add_field(
                    name="🤖 **Bot Info**",
                    value=template['bot_info'],
                    inline=False
                )
                
                embed.set_footer(text=f"💡 Use !{command_name} to execute this command")
                
                await ctx.send(embed=embed, ephemeral=True)
                
            else:
                # Command not found
                embed = discord.Embed(
                    title="❌ Command Not Found",
                    description=f"The command `!{command_name}` was not found.",
                    color=discord.Color.red()
                )
                
                embed.add_field(
                    name="💡 **What to do**",
                    value="• Use `!templates` to see all available commands\n• Check your spelling and try again",
                    inline=False
                )
                
                await ctx.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}", ephemeral=True)
            logger.error(f"Error showing template: {str(e)}")

# ============================================================================
# COG SETUP SECTION
# ============================================================================

async def setup(bot):
    """
    Setup function called by Discord.py to load this cog
    
    This function:
    1. Creates an instance of HelpCog
    2. Adds it to the bot
    3. Logs successful setup
    
    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(HelpCog(bot))
    logger.info("Help cog setup complete")
