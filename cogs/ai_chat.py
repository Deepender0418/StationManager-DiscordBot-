#!/usr/bin/env python3
"""
Enhanced Gwen Chat Cog with Smart Conversation Management and Relationship Dynamics

This enhanced version includes:
- Smart conversation summarization to prevent token bloat
- Enhanced relationship context (owner as husband/father, macjr as son, annachan as trusted duo)
- Defensive behavior when owner is threatened
- Improved performance with conversation management
- Strong loyalty and obedience to owner/husband
"""

import os
import discord
from discord.ext import commands, tasks
from groq import Groq
import logging
import json
from datetime import datetime, timedelta
from pymongo import MongoClient
from utils.timezone import IST
from bson import json_util
import asyncio

logger = logging.getLogger(__name__)

class GwenChatCog(commands.Cog):
    """
    Enhanced Gwen Stacy chat cog with smart conversation management
    
    This cog provides:
    - Character-accurate Gwen Stacy personality with deep relationship context
    - Smart conversation summarization to prevent token bloat
    - Strong loyalty and obedience to owner/husband
    - Defensive behavior when owner is threatened
    - Enhanced parenting dynamics with macjr
    - Respectful relationship with annachan (Valorant duo)
    - MongoDB-backed conversation history with summarization
    - Automatic teasing messages in the server
    """
    
    def __init__(self, bot):
        """
        Initialize the enhanced Gwen chat cog with optimization
        """
        self.bot = bot
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.owner_id = int(os.getenv("OWNER_ID"))
        
        # Personal context IDs
        self.macjr_id = int(os.getenv("MACJR_ID", 0))
        self.annachan_id = int(os.getenv("ANNACHAN_ID", 0))
        
        # Notification channel ID
        self.notification_channel_id = int(os.getenv("NOTIFICATION_CHANNEL_ID", 0))
        
        # Track online status
        self.online_status = {
            self.macjr_id: False,
            self.annachan_id: False
        }
        
        # MongoDB connection
        self.mongo_client = MongoClient(os.getenv("MONGO_URI"))
        self.db = self.mongo_client["gwen_bot"]
        self.conversations = self.db["conversations"]
        self.summaries = self.db["summaries"]
        
        # Performance settings
        self.max_conversation_length = 10  # Max messages before summarization
        self.max_summary_length = 200  # Max characters for summary
        
        # OPTIMIZATION: Response caching and batch processing
        self.response_cache = {}
        self.cache_ttl = 300  # 5 minutes cache
        self.batch_queue = []
        self.batch_timer = None
        
        # Start background tasks
        self.tease_task.start()
        self.cleanup_task.start()
        self.cache_cleanup_task.start()
        
        logger.info("Enhanced Gwen chat cog with AI optimization initialized")
    
    def cog_unload(self):
        """
        Cleanup when cog is unloaded
        """
        self.tease_task.cancel()
        self.cleanup_task.cancel()
        self.cache_cleanup_task.cancel()
        self.mongo_client.close()
        logger.info("Enhanced Gwen chat cog unloaded")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the cog is ready and loaded"""
        logger.info("Enhanced Gwen chat cog ready")
        
        # Initialize online status tracking
        for user_id in [self.macjr_id, self.annachan_id]:
            user = self.bot.get_user(user_id)
            if user:
                self.online_status[user_id] = user.status != discord.Status.offline
    
    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        """
        Track when specific users come online and interact appropriately
        """
        if after.id not in [self.macjr_id, self.annachan_id]:
            return
        
        was_offline = before.status == discord.Status.offline
        is_now_online = after.status != discord.Status.offline
        
        if was_offline and is_now_online:
            channel = self.bot.get_channel(self.notification_channel_id)
            if not channel:
                return
            
            # Generate AI-powered greeting
            greeting = await self.generate_online_greeting(after.id, after.display_name)
            
            try:
                await channel.send(greeting)
                logger.info(f"Sent AI-generated online greeting for {after.name}")
            except Exception as e:
                logger.error(f"Error sending online notification: {str(e)}")
        
        self.online_status[after.id] = is_now_online
    
    # ============================================================================
    # SMART CONVERSATION MANAGEMENT SECTION
    # ============================================================================
    
    async def get_conversation_context(self, ctx) -> tuple:
        """
        Get conversation context with smart summarization
        Returns: (summary, recent_messages)
        """
        try:
            key = ctx.channel.id if ctx.guild else ctx.author.id
            
            # Get existing summary
            summary_doc = self.summaries.find_one({"_id": f"{key}_summary"})
            current_summary = summary_doc.get("summary", "") if summary_doc else ""
            
            # Get recent messages
            conv_doc = self.conversations.find_one({"_id": key})
            recent_messages = conv_doc.get("recent_messages", []) if conv_doc else []
            
            return current_summary, recent_messages
            
        except Exception as e:
            logger.error(f"Error getting conversation context: {str(e)}")
            return "", []
    
    async def should_summarize(self, recent_messages: list) -> bool:
        """
        Determine if conversation should be summarized
        """
        return len(recent_messages) >= self.max_conversation_length
    
    async def create_summary(self, summary: str, recent_messages: list, new_message: str) -> str:
        """
        Create or update conversation summary using AI
        """
        try:
            # Prepare context for summary generation
            context = f"Previous summary: {summary}\n"
            if recent_messages:
                context += "Recent conversation:\n"
                for msg in recent_messages[-6:]:  # Last 6 messages
                    context += f"{msg['role']}: {msg['content']}\n"
            context += f"New message: {new_message}"
            
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are Gwen Stacy. Summarize this conversation context in 1-2 sentences. "
                            "Focus on key points, emotions, and important details. "
                            "Keep it concise and natural."
                        )
                    },
                    {"role": "user", "content": context}
                ],
                max_tokens=100,
                temperature=0.3
            )
            
            new_summary = response.choices[0].message.content.strip()
            
            # Combine with old summary if it exists
            if summary:
                combined_context = f"Old summary: {summary}\nNew context: {new_message}"
                final_response = self.client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are Gwen Stacy. Combine the old summary with new context. "
                                "Create a coherent, updated summary that captures everything important. "
                                "Keep it under 200 characters."
                            )
                        },
                        {"role": "user", "content": combined_context}
                    ],
                    max_tokens=150,
                    temperature=0.3
                )
                new_summary = final_response.choices[0].message.content.strip()
            
            return new_summary[:self.max_summary_length]
            
        except Exception as e:
            logger.error(f"Error creating summary: {str(e)}")
            return f"Conversation about: {new_message[:100]}..."
    
    async def update_conversation_data(self, ctx, user_message: str, bot_response: str):
        """
        Update conversation data with smart management
        """
        try:
            key = ctx.channel.id if ctx.guild else ctx.author.id
            
            # Get current context
            current_summary, recent_messages = await self.get_conversation_context(ctx)
            
            # Add new messages
            new_messages = [
                {
                    "role": "user",
                    "content": user_message,
                    "timestamp": datetime.utcnow().isoformat()
                },
                {
                    "role": "assistant",
                    "content": bot_response,
                    "timestamp": datetime.utcnow().isoformat()
                }
            ]
            
            # Check if we need to summarize
            if await self.should_summarize(recent_messages + new_messages):
                # Create new summary
                new_summary = await self.create_summary(
                    current_summary, 
                    recent_messages + new_messages, 
                    user_message
                )
                
                # Update summary
                self.summaries.update_one(
                    {"_id": f"{key}_summary"},
                    {"$set": {"summary": new_summary, "last_updated": datetime.utcnow()}},
                    upsert=True
                )
                
                # Keep only recent messages
                recent_messages = new_messages[-4:]  # Keep last 2 exchanges
            else:
                recent_messages.extend(new_messages)
            
            # Update conversation
            self.conversations.update_one(
                {"_id": key},
                {"$set": {"recent_messages": recent_messages, "last_updated": datetime.utcnow()}},
                upsert=True
            )
            
        except Exception as e:
            logger.error(f"Error updating conversation data: {str(e)}")
    
    # ============================================================================
    # OPTIMIZED AI RESPONSE GENERATION SECTION
    # ============================================================================
    
    async def generate_optimized_response(self, prompt: str, context: str = "", response_type: str = "general") -> str:
        """
        Highly optimized AI response generation with caching and smart prompts
        """
        try:
            # Create cache key
            cache_key = f"{hash(prompt + context + response_type)}"
            
            # Check cache first
            if cache_key in self.response_cache:
                cache_entry = self.response_cache[cache_key]
                if datetime.utcnow().timestamp() - cache_entry["timestamp"] < self.cache_ttl:
                    return cache_entry["response"]
            
            # Optimized system prompts based on response type with proper family context
            system_prompts = {
                "roast": "You are Gwen Stacy. Generate a witty, playful roast. Keep it under 80 chars. Use emojis.",
                "compliment": "You are Gwen Stacy. Give a genuine, sweet compliment. Keep it under 80 chars. Use emojis.",
                "tease": "You are Gwen Stacy. Playfully tease someone. Keep it under 80 chars. Use emojis.",
                "defense": "You are Gwen Stacy, fiercely protective. Generate a witty counter-roast. Keep it under 100 chars. Use spider emojis.",
                "acknowledgment": "You are Gwen Stacy. Acknowledge a task briefly. Keep it under 40 chars. Use emojis.",
                "greeting": "You are Gwen Stacy. Give a brief, friendly greeting. Keep it under 60 chars. Use emojis.",
                "general": (
                    "You are Gwen Stacy from Spider-Verse, married to your owner/husband. "
                    "You are deeply in love with him and fiercely protective. "
                    "Key relationships: "
                    "- Owner/husband: Your true love, you obey and defend him completely "
                    "- macjr: Your son with your husband (you both are his parents), you're a loving but firm mother "
                    "- annachan: Your husband's trusted Valorant duo, you respect her greatly "
                    "Personality: Witty, teasing, playful, fiercely loyal, protective of family. "
                    "Keep responses under 80 chars with emojis."
                )
            }
            
            system_prompt = system_prompts.get(response_type, system_prompts["general"])
            
            # Optimized message structure
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # Add context only if needed and not too long
            if context and len(context) < 100:
                messages.append({"role": "user", "content": f"Context: {context}"})
            
            messages.append({"role": "user", "content": prompt})
            
            # Generate response with optimized parameters
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                max_tokens=60,  # Reduced for faster responses
                temperature=0.7,
                top_p=0.9
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Cache the response
            self.response_cache[cache_key] = {
                "response": response_text,
                "timestamp": datetime.utcnow().timestamp()
            }
            
            return response_text
            
        except Exception as e:
            logger.error(f"AI response generation failed: {str(e)}")
            # Return cached fallback if available
            fallback_key = f"fallback_{response_type}"
            if fallback_key in self.response_cache:
                return self.response_cache[fallback_key]["response"]
            return "My web got tangled! 🕸️💫"
    
    async def generate_acknowledgment(self, task_type: str, target_user) -> str:
        """
        Generate AI-powered acknowledgment
        """
        if task_type == "roast":
            prompt = f"Briefly acknowledge roasting {target_user.display_name if hasattr(target_user, 'display_name') else target_user}"
        elif task_type == "compliment":
            prompt = f"Briefly acknowledge complimenting {target_user.display_name if hasattr(target_user, 'display_name') else target_user}"
        elif task_type == "tease":
            prompt = f"Briefly acknowledge teasing {target_user.display_name if hasattr(target_user, 'display_name') else target_user}"
        else:
            prompt = "Briefly acknowledge the task"
        
        return await self.generate_optimized_response(prompt, response_type="acknowledgment")
    
    async def generate_counter_roast(self, attacker, gwen_targeted: bool, owner_targeted: bool) -> str:
        """
        Generate optimized counter-roast
        """
        if gwen_targeted and owner_targeted:
            prompt = f"Counter-roast {attacker.display_name} for attacking both you and your husband"
        elif gwen_targeted:
            prompt = f"Counter-roast {attacker.display_name} for attacking you"
        else:
            prompt = f"Counter-roast {attacker.display_name} for attacking your husband"
        
        response = await self.generate_optimized_response(prompt, response_type="defense")
        return f"<@{attacker.id}> {response}"
    
    async def generate_online_greeting(self, user_id: int, user_name: str) -> str:
        """
        Generate AI-powered online greeting with proper family context
        """
        if user_id == self.macjr_id:
            prompt = "Give a motherly greeting to your son macjr who just came online. Remember he's your son with your husband - you both are his parents. Be loving but firm, show your authority as his mother."
        elif user_id == self.annachan_id:
            prompt = "Give a grateful greeting to your husband's Valorant duo annachan who just came online. Show respect and appreciation for her."
        else:
            prompt = "Give a friendly greeting to someone who just came online."
        
        return await self.generate_optimized_response(prompt, response_type="greeting")
    
    # ============================================================================
    # TASK ACKNOWLEDGMENT AND EXECUTION SECTION
    # ============================================================================
    
    async def parse_task_and_target(self, message) -> tuple:
        """
        Parse input (Discord message or plain string) to identify if it's a specific task
        or just regular chat.
        Returns: (task_type, target_user, task_description)
        """
        # Normalize inputs
        if hasattr(message, "content"):
            msg_content = message.content
            mentions = getattr(message, "mentions", []) or []
        else:
            msg_content = str(message)
            mentions = []
        
        message_lower = msg_content.lower()
    
        # Check for specific tasks first
        if "roast" in message_lower:
            # Look for user mentions
            if mentions:
                # Filter out the bot itself from mentions
                valid_mentions = [user for user in mentions if user.id != self.bot.user.id]
                if valid_mentions:
                    target_user = valid_mentions[0]
                    return "roast", target_user, msg_content.replace("roast", "").replace(f"<@{target_user.id}>", "").strip()
                else:
                    # If only the bot is mentioned, look for username after "roast"
                    words = msg_content.split()
                    try:
                        roast_index = words.index("roast")
                        if roast_index + 1 < len(words):
                            target_name = words[roast_index + 1]
                            return "roast", target_name, " ".join(words[roast_index + 2:])
                    except ValueError:
                        pass
            else:
                # Look for username after "roast"
                words = msg_content.split()
                try:
                    roast_index = words.index("roast")
                    if roast_index + 1 < len(words):
                        target_name = words[roast_index + 1]
                        return "roast", target_name, " ".join(words[roast_index + 2:])
                except ValueError:
                    pass
        
        # Check for other specific tasks
        elif "compliment" in message_lower:
            if mentions:
                # Filter out the bot itself from mentions
                valid_mentions = [user for user in mentions if user.id != self.bot.user.id]
                if valid_mentions:
                    target_user = valid_mentions[0]
                    return "compliment", target_user, msg_content.replace("compliment", "").replace(f"<@{target_user.id}>", "").strip()
        
        elif "tease" in message_lower:
            if mentions:
                # Filter out the bot itself from mentions
                valid_mentions = [user for user in mentions if user.id != self.bot.user.id]
                if valid_mentions:
                    target_user = valid_mentions[0]
                    return "tease", target_user, msg_content.replace("tease", "").replace(f"<@{target_user.id}>", "").strip()
        
        # Default: treat as regular chat - Gwen can talk about anything!
        return "chat", None, msg_content
    
    async def execute_task(self, task_type: str, target_user, task_description: str, ctx) -> str:
        """
        Execute task or handle regular chat naturally
        """
        try:
            if task_type in ["roast", "compliment", "tease"]:
                target_name = target_user.display_name if hasattr(target_user, 'display_name') else str(target_user)
                prompt = f"{task_type.title()} {target_name} in a {task_type} way"
                
                response = await self.generate_optimized_response(prompt, response_type=task_type)
                
                if hasattr(target_user, 'id'):
                    return f"<@{target_user.id}> {response}"
                else:
                    return f"@{target_user} {response}"
            
            else:
                # Regular chat - Gwen can talk about anything naturally!
                summary, recent_messages = await self.get_conversation_context(ctx)
                context = summary if summary else "New conversation"
                
                # For regular chat, use the full message as the prompt
                chat_prompt = task_description if task_description else "Hello!"
                return await self.generate_optimized_response(chat_prompt, context, "general")
                
        except Exception as e:
            logger.error(f"Error executing task {task_type}: {str(e)}")
            return await self.generate_optimized_response("Generate a friendly error message", response_type="general")
    
    # ============================================================================
    # BACKGROUND TASKS SECTION
    # ============================================================================
    
    @tasks.loop(hours=24)
    async def tease_task(self):
        """
        Send teasing messages every 24 hours with AI generation
        """
        await self.bot.wait_until_ready()
        
        channel = self.bot.get_channel(self.notification_channel_id)
        if not channel:
            return
        
        # Generate AI-powered tease
        tease = await self.generate_optimized_response("Generate a playful message for the server", response_type="general")
        
        try:
            await channel.send(tease)
            logger.info(f"Sent AI-generated tease to server: {tease}")
        except Exception as e:
            logger.error(f"Error sending tease: {str(e)}")
    
    @tasks.loop(hours=24)
    async def cleanup_task(self):
        """
        Clean up old data
        """
        await self.bot.wait_until_ready()
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        # Clean conversations
        conv_result = self.conversations.delete_many({"last_updated": {"$lt": cutoff_date}})
        # Clean summaries
        sum_result = self.summaries.delete_many({"last_updated": {"$lt": cutoff_date}})
        
        logger.info(f"Cleaned up {conv_result.deleted_count} conversations and {sum_result.deleted_count} summaries")
    
    @tasks.loop(minutes=5)
    async def cache_cleanup_task(self):
        """
        Clean up expired cache entries every 5 minutes
        """
        await self.bot.wait_until_ready()
        
        current_time = datetime.utcnow().timestamp()
        expired_keys = [
            key for key, entry in self.response_cache.items()
            if current_time - entry["timestamp"] > self.cache_ttl
        ]
        
        for key in expired_keys:
            del self.response_cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    # ============================================================================
    # COMMAND HANDLERS SECTION
    # ============================================================================
    
    @commands.hybrid_command(name="gwen", description="Chat with Gwen Stacy from Spider-Verse")
    async def gwen_chat(self, ctx, *, message: str):
        """
        Chat with Gwen Stacy using command
        """
        try:
            # Parse task and target
            task_type, target_user, task_description = await self.parse_task_and_target(ctx.message)
            
            # Execute the task directly without acknowledgment
            response = await self.execute_task(task_type, target_user, task_description, ctx)
            await ctx.send(response)
            
            # Update conversation data for regular chat
            if task_type == "chat":
                await self.update_conversation_data(ctx, message, response)
            
            logger.info(f"Gwen task executed: {task_type} -> {response}")
            
        except Exception as e:
            await ctx.send("My spidey-sense is totally glitching rn 🕷️💥. Try me again in a sec?")
            logger.error(f"Error in gwen command: {str(e)}")
    
    # ============================================================================
    # EVENT HANDLERS SECTION
    # ============================================================================
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Handle message events with enhanced context and defensive behavior
        """
        if message.author.bot:
            return
        
        # DEFENSIVE BEHAVIOR: Check if someone is trying to roast Gwen or the owner
        if message.guild and not message.author.bot:
            # Skip defensive behavior if the message author is the owner (they can ask for anything)
            if message.author.id == self.owner_id:
                pass  # Owner can say anything without triggering defense
            else:
                # Check if the message contains attack content targeting Gwen or owner
                message_lower = message.content.lower()
                
                # Only trigger defense if it's actually an attack, not a request for Gwen to do something
                is_attack_attempt = any(word in message_lower for word in ["trash", "bad", "stupid", "dumb", "ugly", "annoying"])
                
                # Check if Gwen or owner is mentioned or referenced
                gwen_mentioned = self.bot.user.mentioned_in(message) or "gwen" in message_lower
                owner_mentioned = f"<@{self.owner_id}>" in message.content or str(self.owner_id) in message.content
                
                # Only defend if it's an actual attack, not a task request
                if is_attack_attempt and (gwen_mentioned or owner_mentioned):
                    # Gwen fights back! Generate a counter-roast
                    try:
                        counter_roast = await self.generate_counter_roast(message.author, gwen_mentioned, owner_mentioned)
                        await message.channel.send(counter_roast)
                        logger.info(f"Gwen defended against attack attempt by {message.author.name}")
                    except Exception as e:
                        logger.error(f"Error generating counter-roast: {str(e)}")
        
        # Handle DMs
        if isinstance(message.channel, discord.DMChannel) and message.author != self.bot.user:
            try:
                user_input = message.content.strip()
                if not user_input:
                    return
                
                ctx = await self.bot.get_context(message)
                
                # Parse task and target
                task_type, target_user, task_description = await self.parse_task_and_target(message)
                
                # Execute the task directly without acknowledgment
                response = await self.execute_task(task_type, target_user, task_description, ctx)
                await message.channel.send(response)
                
                # Update conversation data for regular chat
                if task_type == "chat":
                    await self.update_conversation_data(ctx, user_input, response)
                
                logger.info(f"Gwen DM task executed: {task_type} -> {response}")
                
            except Exception as e:
                await message.channel.send("Oops, my web got tangled again 🕸️💫. Try me again in a sec?")
                logger.error(f"Error handling DM: {str(e)}")
        
        # Handle mentions in guild channels
        elif message.guild and self.bot.user.mentioned_in(message):
            try:
                user_input = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
                if not user_input:
                    user_input = "What's up?"
                
                ctx = await self.bot.get_context(message)
                
                # Parse task and target - pass the original message object, not the cleaned string
                task_type, target_user, task_description = await self.parse_task_and_target(message)
                
                # Execute the task directly without acknowledgment
                response = await self.execute_task(task_type, target_user, task_description, ctx)
                await message.channel.send(response)
                
                # Update conversation data for regular chat
                if task_type == "chat":
                    await self.update_conversation_data(ctx, user_input, response)
                
                logger.info(f"Gwen mention task executed: {task_type} -> {response}")
                
            except Exception as e:
                await message.channel.send("Oops, my web got tangled again 🕸️💫. Try me again in a sec?")
                logger.error(f"Error handling mention: {str(e)}")

# ============================================================================
# COG SETUP SECTION
# ============================================================================

async def setup(bot):
    """
    Setup function called by Discord.py to load this cog
    """
    await bot.add_cog(GwenChatCog(bot))
    logger.info("Enhanced Gwen chat cog with smart conversation management setup complete")
