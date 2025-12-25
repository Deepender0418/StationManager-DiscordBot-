#!/usr/bin/env python3
"""
Role Management Cog - Handles default role assignment for new members

This cog provides:
- Automatic default role assignment when members join
- Command to add default role to all existing members
- Configuration for default role per server
- Command to list all roles (Owner only)
- Command to assign any role to any member (Owner only)
"""

import discord
from discord.ext import commands
import logging
from utils.database import get_guild_config

logger = logging.getLogger(__name__)

class RoleCog(commands.Cog):
    """
    Role management cog for handling default role assignments
    """
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("✅ RoleCog initialized")

    # ============================================================================
    # EVENT HANDLERS SECTION
    # ============================================================================

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """
        Automatically assign default role when a member joins
        
        This handler:
        1. Gets the guild configuration from database
        2. Checks if default role is configured
        3. Assigns the role to the new member
        4. Handles errors gracefully
        """
        try:
            # Get guild configuration from database
            config = await get_guild_config(self.bot.guild_configs, str(member.guild.id))
            
            if not config or 'default_role_id' not in config or not config['default_role_id']:
                logger.debug(f"No default role configured for {member.guild.name}")
                return
            
            # Get the default role
            default_role_id = int(config['default_role_id'])
            default_role = member.guild.get_role(default_role_id)
            
            if not default_role:
                logger.warning(f"Default role with ID {default_role_id} not found in {member.guild.name}")
                return
            
            # Assign the role to the new member
            await member.add_roles(default_role, reason="Automatic default role assignment")
            logger.info(f"✅ Assigned default role '{default_role.name}' to {member.display_name} in {member.guild.name}")
            
        except Exception as e:
            logger.error(f"❌ Error assigning default role to {member.display_name}: {str(e)}")

    # ============================================================================
    # COMMANDS SECTION
    # ============================================================================

    @commands.command(name='setdefaultrole')
    @commands.has_permissions(administrator=True)
    async def set_default_role(self, ctx, role: discord.Role):
        """
        Set the default role for new members (Admin only)
        
        Usage: !setdefaultrole @RoleName
        Example: !setdefaultrole @Members
        """
        try:
            # Update guild configuration in database
            await self.bot.guild_configs.update_one(
                {"guild_id": str(ctx.guild.id)},
                {"$set": {"default_role_id": str(role.id)}},
                upsert=True
            )
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Default Role Set",
                description=f"Default role has been set to **{role.mention}**",
                color=discord.Color.green()
            )
            embed.add_field(
                name="📝 What happens now?",
                value="• New members will automatically receive this role\n• Use `!adddefaultroleall` to assign to existing members",
                inline=False
            )
            embed.set_footer(text="Role management system")
            
            await ctx.send(embed=embed)
            logger.info(f"✅ Default role set to '{role.name}' in {ctx.guild.name}")
            
        except Exception as e:
            logger.error(f"❌ Error setting default role: {str(e)}")
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to set default role. Please try again.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name='adddefaultroleall')
    @commands.has_permissions(administrator=True)
    async def add_default_role_all(self, ctx):
        """
        Add default role to all existing members (Admin only)
        
        This command:
        1. Gets the configured default role
        2. Iterates through all members
        3. Assigns the role to members who don't have it
        4. Provides progress updates
        """
        try:
            # Get guild configuration
            config = await get_guild_config(self.bot.guild_configs, str(ctx.guild.id))
            
            if not config or 'default_role_id' not in config or not config['default_role_id']:
                embed = discord.Embed(
                    title="❌ No Default Role Set",
                    description="Please set a default role first using `!setdefaultrole @RoleName`",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed)
                return
            
            # Get the default role
            default_role_id = int(config['default_role_id'])
            default_role = ctx.guild.get_role(default_role_id)
            
            if not default_role:
                embed = discord.Embed(
                    title="❌ Role Not Found",
                    description="The configured default role no longer exists. Please set a new one.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            # Check bot permissions
            if not ctx.guild.me.guild_permissions.manage_roles:
                embed = discord.Embed(
                    title="❌ Missing Permissions",
                    description="I need the 'Manage Roles' permission to assign roles.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            if default_role.position >= ctx.guild.me.top_role.position:
                embed = discord.Embed(
                    title="❌ Role Hierarchy Issue",
                    description="The default role is higher than my highest role. Please move my role above the default role.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            # Start role assignment process
            members = [member for member in ctx.guild.members if not member.bot and default_role not in member.roles]
            
            if not members:
                embed = discord.Embed(
                    title="✅ All Set!",
                    description="All non-bot members already have the default role!",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
                return
            
            # Send initial progress message
            progress_embed = discord.Embed(
                title="🔄 Assigning Default Roles",
                description=f"Assigning {default_role.mention} to **{len(members)}** members...",
                color=discord.Color.blue()
            )
            progress_embed.add_field(
                name="⏰ Please wait",
                value="This may take a while for large servers. I'll update you on the progress.",
                inline=False
            )
            progress_message = await ctx.send(embed=progress_embed)
            
            # Assign roles with progress updates
            success_count = 0
            failed_count = 0
            batch_size = 10  # Process in batches to avoid rate limits
            
            for i, member in enumerate(members):
                try:
                    await member.add_roles(default_role, reason="Bulk default role assignment")
                    success_count += 1
                    
                    # Update progress every batch_size members
                    if (i + 1) % batch_size == 0 or (i + 1) == len(members):
                        progress_embed.description = (
                            f"Assigning {default_role.mention} to members...\n"
                            f"**Progress:** {i + 1}/{len(members)}\n"
                            f"**Successful:** {success_count}\n"
                            f"**Failed:** {failed_count}"
                        )
                        await progress_message.edit(embed=progress_embed)
                        
                except Exception as e:
                    failed_count += 1
                    logger.warning(f"Failed to assign role to {member.display_name}: {str(e)}")
            
            # Send completion message
            completion_embed = discord.Embed(
                title="✅ Role Assignment Complete",
                color=discord.Color.green()
            )
            completion_embed.add_field(
                name="📊 Results",
                value=f"**Successful:** {success_count}\n**Failed:** {failed_count}\n**Total Processed:** {len(members)}",
                inline=False
            )
            
            if failed_count > 0:
                completion_embed.add_field(
                    name="⚠️ Note",
                    value="Some roles failed to assign. This is usually due to role hierarchy issues or missing permissions.",
                    inline=False
                )
            
            await progress_message.edit(embed=completion_embed)
            logger.info(f"✅ Bulk role assignment completed in {ctx.guild.name}: {success_count} successful, {failed_count} failed")
            
        except Exception as e:
            logger.error(f"❌ Error in bulk role assignment: {str(e)}")
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred during role assignment. Please try again.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name='showdefaultrole')
    @commands.has_permissions(administrator=True)
    async def show_default_role(self, ctx):
        """
        Show the currently configured default role (Admin only)
        """
        try:
            config = await get_guild_config(self.bot.guild_configs, str(ctx.guild.id))
            
            if not config or 'default_role_id' not in config or not config['default_role_id']:
                embed = discord.Embed(
                    title="⚙️ Default Role Configuration",
                    description="No default role is currently set.",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="💡 How to set",
                    value="Use `!setdefaultrole @RoleName` to configure a default role",
                    inline=False
                )
            else:
                default_role_id = int(config['default_role_id'])
                default_role = ctx.guild.get_role(default_role_id)
                
                if default_role:
                    embed = discord.Embed(
                        title="⚙️ Default Role Configuration",
                        description=f"Current default role: {default_role.mention}",
                        color=discord.Color.green()
                    )
                    embed.add_field(
                        name="Role ID",
                        value=f"`{default_role.id}`",
                        inline=True
                    )
                    embed.add_field(
                        name="Members with role",
                        value=f"`{len(default_role.members)}`",
                        inline=True
                    )
                else:
                    embed = discord.Embed(
                        title="⚠️ Default Role Not Found",
                        description="The configured default role no longer exists.",
                        color=discord.Color.orange()
                    )
                    embed.add_field(
                        name="💡 Solution",
                        value="Use `!setdefaultrole @RoleName` to set a new default role",
                        inline=False
                    )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ Error showing default role: {str(e)}")
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to retrieve default role information.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name='listroles', aliases=['roles', 'allroles'])
    @commands.is_owner()
    async def list_roles(self, ctx):
        """
        List all roles in the server (Bot Owner only)
        
        Shows:
        - All roles with their IDs
        - Member count per role
        - Role hierarchy position
        - Color preview
        """
        try:
            # Get all roles, sorted by position (highest first)
            roles = sorted(ctx.guild.roles, key=lambda r: r.position, reverse=True)
            
            if not roles:
                embed = discord.Embed(
                    title="🎭 Server Roles",
                    description="No roles found in this server.",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed)
                return
            
            # Create paginated embeds
            roles_per_page = 15
            pages = []
            
            for i in range(0, len(roles), roles_per_page):
                role_chunk = roles[i:i + roles_per_page]
                
                embed = discord.Embed(
                    title=f"🎭 Server Roles - Page {i//roles_per_page + 1}/{(len(roles)-1)//roles_per_page + 1}",
                    description=f"Total Roles: **{len(roles)}**",
                    color=discord.Color.blue()
                )
                embed.set_footer(text=f"Server: {ctx.guild.name} | ID: {ctx.guild.id}")
                
                for role in role_chunk:
                    # Skip @everyone role in detailed listing
                    if role == ctx.guild.default_role:
                        continue
                    
                    # Get role info
                    role_name = f"@{role.name}"
                    role_id = f"`{role.id}`"
                    member_count = f"👥 `{len(role.members)}`"
                    position = f"📊 `{role.position}`"
                    
                    # Get color preview
                    color_preview = ""
                    if role.color != discord.Color.default():
                        color_preview = f"🎨 `{str(role.color)}`"
                    
                    # Check if role is mentionable
                    mentionable = "✅" if role.mentionable else "❌"
                    
                    # Format field value
                    field_value = f"{role_id} | {member_count} | {position} | {mentionable}"
                    if color_preview:
                        field_value += f" | {color_preview}"
                    
                    # Add badges for special roles
                    badges = []
                    if role.hoist:
                        badges.append("📌")
                    if role.managed:
                        badges.append("🤖")
                    if role.is_premium_subscriber():
                        badges.append("⭐")
                    
                    if badges:
                        role_name = f"{role_name} {' '.join(badges)}"
                    
                    embed.add_field(
                        name=role_name,
                        value=field_value,
                        inline=False
                    )
                
                # Add @everyone role info at the end
                everyone = ctx.guild.default_role
                embed.add_field(
                    name="@everyone 👥",
                    value=f"ID: `{everyone.id}` | Members: `{len(everyone.members)}` | Position: `{everyone.position}`",
                    inline=False
                )
                
                pages.append(embed)
            
            # Send first page
            if len(pages) == 1:
                await ctx.send(embed=pages[0])
            else:
                # Simple pagination - just send all pages
                for page in pages:
                    await ctx.send(embed=page)
                    # Small delay to avoid rate limits
                    import asyncio
                    await asyncio.sleep(0.5)
            
            logger.info(f"✅ Listed all roles for {ctx.guild.name}")
            
        except Exception as e:
            logger.error(f"❌ Error listing roles: {str(e)}")
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to list roles. Please try again.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name='assignrole', aliases=['giverole', 'addrole'])
    @commands.is_owner()
    async def assign_role(self, ctx, member: discord.Member, role: discord.Role):
        """
        Assign any role to any member (Bot Owner only)
        
        Usage: !assignrole @member @role
        Example: !assignrole @JohnDoe @Moderator
        """
        try:
            # Check if member already has the role
            if role in member.roles:
                embed = discord.Embed(
                    title="⚠️ Role Already Assigned",
                    description=f"{member.mention} already has the role {role.mention}",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed)
                return
            
            # Check bot permissions
            if not ctx.guild.me.guild_permissions.manage_roles:
                embed = discord.Embed(
                    title="❌ Missing Permissions",
                    description="I need the 'Manage Roles' permission to assign roles.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            # Check role hierarchy
            if role.position >= ctx.guild.me.top_role.position:
                embed = discord.Embed(
                    title="❌ Role Hierarchy Issue",
                    description=f"The role {role.mention} is higher than my highest role.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            # Check if role is managed (bot/integration role)
            if role.managed:
                embed = discord.Embed(
                    title="❌ Cannot Assign Managed Role",
                    description=f"The role {role.mention} is managed by an integration and cannot be assigned manually.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            # Assign the role
            await member.add_roles(role, reason=f"Assigned by bot owner {ctx.author}")
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Role Assigned Successfully",
                description=f"**{role.mention}** has been assigned to **{member.mention}**",
                color=discord.Color.green()
            )
            embed.add_field(
                name="👤 Member Info",
                value=f"Name: `{member.display_name}`\nID: `{member.id}`",
                inline=True
            )
            embed.add_field(
                name="🎭 Role Info",
                value=f"Name: `{role.name}`\nID: `{role.id}`",
                inline=True
            )
            embed.add_field(
                name="👑 Assigned By",
                value=f"{ctx.author.mention}\n`{ctx.author}`",
                inline=False
            )
            embed.set_footer(text=f"Total roles for member: {len(member.roles)}")
            
            await ctx.send(embed=embed)
            logger.info(f"✅ Owner {ctx.author} assigned role '{role.name}' to member '{member}' in {ctx.guild.name}")
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description=f"I don't have permission to assign the role {role.mention}.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"❌ Error assigning role: {str(e)}")
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to assign role: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name='removerole', aliases=['takerole'])
    @commands.is_owner()
    async def remove_role(self, ctx, member: discord.Member, role: discord.Role):
        """
        Remove any role from any member (Bot Owner only)
        
        Usage: !removerole @member @role
        Example: !removerole @JohnDoe @Moderator
        """
        try:
            # Check if member has the role
            if role not in member.roles:
                embed = discord.Embed(
                    title="⚠️ Role Not Assigned",
                    description=f"{member.mention} doesn't have the role {role.mention}",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed)
                return
            
            # Check bot permissions
            if not ctx.guild.me.guild_permissions.manage_roles:
                embed = discord.Embed(
                    title="❌ Missing Permissions",
                    description="I need the 'Manage Roles' permission to remove roles.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            # Check role hierarchy
            if role.position >= ctx.guild.me.top_role.position:
                embed = discord.Embed(
                    title="❌ Role Hierarchy Issue",
                    description=f"The role {role.mention} is higher than my highest role.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            # Check if role is managed (bot/integration role)
            if role.managed:
                embed = discord.Embed(
                    title="❌ Cannot Remove Managed Role",
                    description=f"The role {role.mention} is managed by an integration and cannot be removed manually.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            # Remove the role
            await member.remove_roles(role, reason=f"Removed by bot owner {ctx.author}")
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Role Removed Successfully",
                description=f"**{role.mention}** has been removed from **{member.mention}**",
                color=discord.Color.green()
            )
            embed.add_field(
                name="👤 Member Info",
                value=f"Name: `{member.display_name}`\nID: `{member.id}`",
                inline=True
            )
            embed.add_field(
                name="🎭 Role Info",
                value=f"Name: `{role.name}`\nID: `{role.id}`",
                inline=True
            )
            embed.add_field(
                name="👑 Removed By",
                value=f"{ctx.author.mention}\n`{ctx.author}`",
                inline=False
            )
            embed.set_footer(text=f"Total roles for member: {len(member.roles)}")
            
            await ctx.send(embed=embed)
            logger.info(f"✅ Owner {ctx.author} removed role '{role.name}' from member '{member}' in {ctx.guild.name}")
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description=f"I don't have permission to remove the role {role.mention}.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"❌ Error removing role: {str(e)}")
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to remove role: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    # ============================================================================
    # ERROR HANDLERS SECTION
    # ============================================================================

    @set_default_role.error
    @add_default_role_all.error
    @show_default_role.error
    @list_roles.error
    @assign_role.error
    @remove_role.error
    async def role_commands_error(self, ctx, error):
        """
        Handle errors for role management commands
        """
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="You need Administrator permissions to use this command.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.NotOwner):
            embed = discord.Embed(
                title="❌ Owner Only",
                description="This command can only be used by the bot owner.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                title="❌ Invalid Argument",
                description="Please mention valid members and roles. Example: `!assignrole @Member @Role`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="❌ Missing Argument",
                description="Please specify all required arguments. Example: `!assignrole @Member @Role`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MemberNotFound):
            embed = discord.Embed(
                title="❌ Member Not Found",
                description="The specified member was not found. Please mention a valid member.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.RoleNotFound):
            embed = discord.Embed(
                title="❌ Role Not Found",
                description="The specified role was not found. Please mention a valid role.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        else:
            logger.error(f"Unexpected error in role command: {str(error)}")
            embed = discord.Embed(
                title="❌ Unexpected Error",
                description="An unexpected error occurred. Please try again.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

async def setup(bot):
    """
    Setup function to add this cog to the bot
    """
    await bot.add_cog(RoleCog(bot))
    logger.info("✅ RoleCog loaded successfully")
