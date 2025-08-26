# cogs/ai_chat.py
import discord
from discord.ext import commands
import groq
import asyncio
from datetime import datetime
from typing import Dict, List

# Import your database utilities
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.database import get_guild_config, update_guild_config


class AIChat(commands.Cog):
    """AI Chat Cog for Gwen Stacy Discord Bot"""
    
    def __init__(self, bot):
        self.bot = bot
        self.conversation_history_collection = None
        
        # Groq API setup
        self.client = groq.Client(api_key=os.getenv('GROQ_API_KEY'))
        
        # Constants
        self.MAX_HISTORY_LENGTH = 20
        
        # Gwen Stacy personality prompt
        self.GWEN_PERSONALITY = """
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
    
    async def cog_load(self):
        """Called when the cog is loaded"""
        # Set up MongoDB collection
        mongo_uri = os.getenv('MONGO_URI')
        db_name = os.getenv('DATABASE_NAME', 'discord_bot')
        
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            client = AsyncIOMotorClient(mongo_uri)
            db = client[db_name]
            self.conversation_history_collection = db.conversation_history
            
            # Create index for faster lookups
            await self.conversation_history_collection.create_index("context_key")
            await self.conversation_history_collection.create_index("last_updated")
            
            print("✅ AI Chat: MongoDB connection established")
        except Exception as e:
            print(f"❌ AI Chat: Failed to connect to MongoDB: {e}")
            raise
    
    async def get_conversation_history(self, server_id: str, user_name: str = None) -> List[Dict[str, str]]:
        """Get conversation history for a server from MongoDB, with optional user context"""
        key = f"{server_id}_{user_name}" if user_name else server_id
        
        # Try to get existing history from MongoDB
        history_doc = await self.conversation_history_collection.find_one({"context_key": key})
        
        if history_doc:
            return history_doc.get("history", [])
        else:
            # Initialize with personality prompt if no history exists
            initial_history = [
                {"role": "system", "content": self.GWEN_PERSONALITY},
                {"role": "assistant", "content": "Got it. I'm Gwen Stacy. Let's chat!"}
            ]
            # Save to MongoDB
            await self.conversation_history_collection.insert_one({
                "context_key": key,
                "history": initial_history,
                "last_updated": datetime.utcnow()
            })
            return initial_history
    
    async def update_conversation_history(self, server_id: str, message: str, response: str, user_name: str = None):
        """Update conversation history in MongoDB with new exchange"""
        key = f"{server_id}_{user_name}" if user_name else server_id
        history = await self.get_conversation_history(server_id, user_name)
        
        # Add new messages
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response})
        
        # Trim history if too long (keeping the initial personality prompt)
        if len(history) > self.MAX_HISTORY_LENGTH + 2:  # +2 for the initial personality messages
            history = history[:2] + history[-(self.MAX_HISTORY_LENGTH):]
        
        # Update MongoDB
        await self.conversation_history_collection.update_one(
            {"context_key": key},
            {"$set": {"history": history, "last_updated": datetime.utcnow()}},
            upsert=True
        )
    
    async def generate_gwen_response(self, message: str, server_id: str, user_name: str = None) -> str:
        """Generate a response from Gwen using Groq API"""
        try:
            history = await self.get_conversation_history(server_id, user_name)
            
            # Prepare messages for Groq API
            messages = history + [{"role": "user", "content": message}]
            
            # Call Groq API
            chat_completion = await asyncio.to_thread(
                self.client.chat.completions.create,
                messages=messages,
                model="llama3-70b-8192",  # You can change this to any Groq-supported model
                temperature=0.7,
                max_tokens=1024
            )
            
            response_text = chat_completion.choices[0].message.content
            
            # Update conversation history
            await self.update_conversation_history(server_id, message, response_text, user_name)
            
            return response_text
        except Exception as e:
            print(f"Error generating response: {e}")
            return "Sorry, I'm having trouble connecting to the spider-verse right now. 🕸️"
    
    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore messages from the bot itself
        if message.author == self.bot.user:
            return
        
        # Get owner ID and allowed channel ID from environment
        OWNER_ID = int(os.getenv('BOT_OWNER_ID', 0))
        ALLOWED_CHANNEL_ID = int(os.getenv('ALLOWED_CHANNEL_ID', 0))
        
        # Handle DMs
        if isinstance(message.channel, discord.DMChannel):
            if message.author.id == OWNER_ID and message.content.startswith('!dm'):
                # Owner can send DMs to users through the bot
                try:
                    parts = message.content.split(' ', 2)
                    user_id = int(parts[1])
                    dm_message = parts[2]
                    user = await self.bot.fetch_user(user_id)
                    await user.send(f"**Gwen Stacy:** {dm_message}")
                    await message.channel.send(f"Message sent to {user.name}!")
                except Exception as e:
                    await message.channel.send(f"Couldn't send message: {e}")
            else:
                # Regular DMs from users
                response = await self.generate_gwen_response(
                    message.content, 
                    str(message.author.id),  # Use user ID as "server ID" for DMs
                    message.author.name
                )
                await message.channel.send(response)
            return
        
        # Handle server messages in the allowed channel only
        if message.channel.id == ALLOWED_CHANNEL_ID:
            # Check if the bot is mentioned
            if self.bot.user in message.mentions:
                # Remove the mention from the message
                clean_content = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
                
                if clean_content:  # Only respond if there's content beyond the mention
                    # Get the user's name for personalization
                    user_name = message.author.display_name
                    
                    # Create a personalized prompt
                    personalized_message = f"{user_name} says: {clean_content}"
                    
                    response = await self.generate_gwen_response(
                        personalized_message, 
                        str(message.guild.id)
                    )
                    
                    # Add the user's name to the response for context
                    await message.channel.send(f"{message.author.mention} {response}")
    
    @commands.command(name='gwen_reset')
    async def reset_conversation(self, ctx, user_name: str = None):
        """Reset conversation history (admin only)"""
        OWNER_ID = int(os.getenv('BOT_OWNER_ID', 0))
        
        if ctx.author.id == OWNER_ID:
            key = f"{ctx.guild.id}_{user_name}" if user_name else str(ctx.guild.id)
            result = await self.conversation_history_collection.delete_one({"context_key": key})
            
            if result.deleted_count > 0:
                await ctx.send("Conversation history reset! 🕸️")
            else:
                await ctx.send("No history found to reset.")
        else:
            await ctx.send("Only my owner can do that.")
    
    @commands.command(name='gwen_history')
    async def show_history_info(self, ctx):
        """Show information about conversation history storage"""
        OWNER_ID = int(os.getenv('BOT_OWNER_ID', 0))
        
        if ctx.author.id == OWNER_ID:
            # Count total conversations stored
            count = await self.conversation_history_collection.count_documents({})
            
            # Get some stats about the largest histories
            pipeline = [
                {"$project": {"context_key": 1, "history_size": {"$size": "$history"}}},
                {"$sort": {"history_size": -1}},
                {"$limit": 5}
            ]
            largest = await self.conversation_history_collection.aggregate(pipeline).to_list(length=5)
            
            embed = discord.Embed(
                title="Conversation History Stats",
                description=f"Stored in MongoDB collection: conversation_history",
                color=0x00ff00
            )
            embed.add_field(name="Total Conversations", value=str(count), inline=False)
            
            if largest:
                largest_text = "\n".join([f"{doc['context_key']}: {doc['history_size']} messages" for doc in largest])
                embed.add_field(name="Largest Histories", value=largest_text, inline=False)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("Only my owner can see this information.")
    
    @commands.command(name='gwen_invite')
    async def invite_info(self, ctx):
        """Get info about inviting the bot"""
        embed = discord.Embed(
            title="Gwen Stacy Bot",
            description="Hey! I'm Gwen Stacy from the Spider-Verse. I'm here to chat with you about anything!",
            color=0xff00ff
        )
        embed.add_field(
            name="How to talk to me",
            value=f"In the server, mention me with @Gwen followed by your message. Or just DM me directly!",
            inline=False
        )
        embed.set_thumbnail(url="https://i.imgur.com/6CwM5n.png")  # Replace with a Gwen Stacy image URL
        await ctx.send(embed=embed)


async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(AIChat(bot))
