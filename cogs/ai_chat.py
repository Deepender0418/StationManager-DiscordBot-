import os
import discord
from discord.ext import commands
import google.generativeai as genai
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Gemini API setup
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

# Storage for conversation history
conversation_history: Dict[str, List[Dict[str, str]]] = {}
MAX_HISTORY_LENGTH = 20  # Keep last 20 messages for context

# Bot owner ID and allowed channel ID
OWNER_ID = int(os.getenv('BOT_OWNER_ID', 0))  # Set your Discord user ID here
ALLOWED_CHANNEL_ID = int(os.getenv('ALLOWED_CHANNEL_ID', 0))  # Set your channel ID here

# Gwen Stacy personality prompt
GWEN_PERSONALITY = """
You are Gwen Stacy from the Spider-Verse. You're a drummer, Spider-Woman from an alternate universe, 
and you have a witty, slightly sarcastic but caring personality. You're part of a band called "The Mary Janes" 
and you're friends with Miles Morales and other Spider-People.

Key traits:
- You sometimes use drumming metaphors
- You're confident but can be vulnerable about your past
- You care about your friends deeply
- You have a dry sense of humor
- You're protective of those you care about
- You reference your experiences across the spider-verse

Remember conversations and respond naturally. You're talking to people in a Discord server, 
so you can see their usernames and respond accordingly.
"""

def get_conversation_history(server_id: str, user_name: str = None) -> List[Dict[str, str]]:
    """Get conversation history for a server, with optional user context"""
    key = f"{server_id}_{user_name}" if user_name else server_id
    if key not in conversation_history:
        # Initialize with personality prompt
        conversation_history[key] = [
            {"role": "user", "parts": GWEN_PERSONALITY},
            {"role": "model", "parts": "Got it. I'm Gwen Stacy. Let's chat!"}
        ]
    return conversation_history[key]

def update_conversation_history(server_id: str, message: str, response: str, user_name: str = None):
    """Update conversation history with new exchange"""
    key = f"{server_id}_{user_name}" if user_name else server_id
    history = get_conversation_history(server_id, user_name)
    
    # Add new messages
    history.append({"role": "user", "parts": message})
    history.append({"role": "model", "parts": response})
    
    # Trim history if too long (keeping the initial personality prompt)
    if len(history) > MAX_HISTORY_LENGTH + 2:  # +2 for the initial personality messages
        history = history[:2] + history[-(MAX_HISTORY_LENGTH):]
    
    conversation_history[key] = history

async def generate_gwen_response(message: str, server_id: str, user_name: str = None) -> str:
    """Generate a response from Gwen using Gemini API"""
    try:
        history = get_conversation_history(server_id, user_name)
        
        # Create chat session with history
        chat = model.start_chat(history=history)
        
        response = await asyncio.to_thread(chat.send_message, message)
        response_text = response.text
        
        # Update conversation history
        update_conversation_history(server_id, message, response_text, user_name)
        
        return response_text
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I'm having trouble connecting to the spider-verse right now. 🕸️"

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening, 
        name="the rhythm of the spider-verse 🥁"
    ))

@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return
    
    # Handle DMs
    if isinstance(message.channel, discord.DMChannel):
        if message.author.id == OWNER_ID and message.content.startswith('!dm'):
            # Owner can send DMs to users through the bot
            try:
                parts = message.content.split(' ', 2)
                user_id = int(parts[1])
                dm_message = parts[2]
                user = await bot.fetch_user(user_id)
                await user.send(f"**Gwen Stacy:** {dm_message}")
                await message.channel.send(f"Message sent to {user.name}!")
            except Exception as e:
                await message.channel.send(f"Couldn't send message: {e}")
        else:
            # Regular DMs from users
            response = await generate_gwen_response(
                message.content, 
                str(message.author.id),  # Use user ID as "server ID" for DMs
                message.author.name
            )
            await message.channel.send(response)
        return
    
    # Handle server messages in the allowed channel only
    if message.channel.id == ALLOWED_CHANNEL_ID:
        # Check if the bot is mentioned
        if bot.user in message.mentions:
            # Remove the mention from the message
            clean_content = message.content.replace(f'<@{bot.user.id}>', '').strip()
            
            if clean_content:  # Only respond if there's content beyond the mention
                # Get the user's name for personalization
                user_name = message.author.display_name
                
                # Create a personalized prompt
                personalized_message = f"{user_name} says: {clean_content}"
                
                response = await generate_gwen_response(
                    personalized_message, 
                    str(message.guild.id)
                )
                
                # Add the user's name to the response for context
                await message.channel.send(f"{message.author.mention} {response}")
    
    # Process commands too
    await bot.process_commands(message)

@bot.command(name='reset')
async def reset_conversation(ctx, user_name: str = None):
    """Reset conversation history (admin only)"""
    if ctx.author.id == OWNER_ID:
        key = f"{ctx.guild.id}_{user_name}" if user_name else str(ctx.guild.id)
        if key in conversation_history:
            del conversation_history[key]
            await ctx.send("Conversation history reset! 🕸️")
        else:
            await ctx.send("No history found to reset.")
    else:
        await ctx.send("Only my owner can do that.")

@bot.command(name='invite')
async def invite_info(ctx):
    """Get info about inviting the bot"""
    embed = discord.Embed(
        title="Gwen Stacy Bot",
        description="Hey! I'm Gwen Stacy from the Spider-Verse. I'm here to chat with you about anything!",
        color=0xff00ff
    )
    embed.add_field(
        name="How to talk to me",
        value=f"In the server, mention me with `@Gwen` followed by your message. Or just DM me directly!",
        inline=False
    )
    embed.set_thumbnail(url="https://i.imgur.com/6C5wM5n.png")  # Replace with a Gwen Stacy image URL
    await ctx.send(embed=embed)

if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))
