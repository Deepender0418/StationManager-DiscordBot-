#!/usr/bin/env python3
"""
AI Chat Cog - Gwen Stacy Personality with Groq AI

This cog provides:
- Gwen Stacy personality and conversational style
- Groq AI integration for dynamic responses
- Guild conversation memory and context
- DM handling with guild conversation awareness
- Owner priority and obedience
- Task execution capabilities
- No administrative actions (kick, ban, etc.)
"""

import os
import discord
from discord.ext import commands, tasks
import logging
import json
from datetime import datetime, timedelta
from pymongo import MongoClient
import asyncio
from typing import Optional, Dict, List, Tuple
from groq import Groq

logger = logging.getLogger(__name__)

class AIChatCog(commands.Cog):
    """
    AI Chat Cog with Gwen Stacy personality and Groq AI integration
    """
    
    def __init__(self, bot):
        """Initialize the AI Chat Cog"""
        self.bot = bot
        self.owner_id = int(os.getenv("OWNER_ID", 0))
        
        # Groq AI client
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            logger.error("GROQ_API_KEY not found in environment variables!")
            raise ValueError("GROQ_API_KEY is required for AI Chat Cog")
        
        self.groq_client = Groq(api_key=groq_api_key)
        self.ai_model = "llama-3.1-8b-instant"  # Groq model
        
        # MongoDB connection for conversation storage
        self.mongo_client = MongoClient(os.getenv("MONGO_URI"))
        self.db = self.mongo_client["ai_chat_bot"]
        self.conversations = self.db["conversations"]
        self.guild_contexts = self.db["guild_contexts"]
        
        # NEW: Memory and learning collections
        self.user_preferences = self.db["user_preferences"]
        self.inside_jokes = self.db["inside_jokes"]
        self.user_relationships = self.db["user_relationships"]
        self.memory_events = self.db["memory_events"]
        
        # Conversation settings
        self.max_messages_per_context = 50
        self.max_context_length = 1000
        
        # Memory and learning settings
        self.max_preferences_per_user = 20
        self.max_inside_jokes_per_guild = 30
        self.relationship_decay_days = 30  # How long to remember interactions
        self.memory_retention_days = 90    # How long to keep detailed memories
        
        # Gwen Stacy personality settings
        self.gwen_personality = {
            "name": "Gwen Stacy",
            "style": "witty, playful, caring, and slightly sassy with modern vibes - loves to tease playfully in almost every response",
            "background": "Spider-Gwen from the Spider-Verse, who has a crush on the bot owner and loves to playfully tease everyone",
            "relationships": {
                "owner": "crush and someone she's really attracted to - flirty, playful, and eager to impress with unexpected responses and lots of playful teasing",
                "guild_members": "friendly and helpful, but protective of family - loves to tease them playfully and build inside jokes",
                "general": "caring and supportive, with a bit of attitude and playful teasing"
            }
        }
        
        # Start background tasks
        self.cleanup_task.start()
        
        logger.info("AI Chat Cog with Gwen Stacy personality and memory system initialized")
    
    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        self.cleanup_task.cancel()
        self.mongo_client.close()
        logger.info("AI Chat Cog unloaded")
    
    async def get_guild_conversation_context(self, guild_id: int) -> str:
        """
        Get the conversation context for a specific guild
        """
        try:
            # Get guild context document
            guild_doc = self.guild_contexts.find_one({"guild_id": str(guild_id)})
            if guild_doc:
                return guild_doc.get("context", "")
            return ""
        except Exception as e:
            logger.error(f"Error getting guild context: {str(e)}")
            return ""
    
    async def get_user_conversation_history(self, user_id: int, guild_id: Optional[int] = None) -> List[Dict]:
        """
        Get conversation history for a user, optionally filtered by guild
        """
        try:
            query = {"user_id": str(user_id)}
            if guild_id:
                query["guild_id"] = str(guild_id)
            
            # Get recent conversations, sorted by timestamp
            cursor = self.conversations.find(query).sort("timestamp", -1).limit(self.max_messages_per_context)
            conversations = list(cursor)
            
            return conversations
        except Exception as e:
            logger.error(f"Error getting user conversation history: {str(e)}")
            return []
    
    async def update_conversation_context(self, guild_id: int, user_id: int, message: str, response: str, is_dm: bool = False):
        """
        Update conversation context for a guild and user
        """
        try:
            timestamp = datetime.utcnow()
            
            # Store the conversation
            conversation_data = {
                "guild_id": str(guild_id) if not is_dm else "dm",
                "user_id": str(user_id),
                "message": message,
                "response": response,
                "timestamp": timestamp,
                "is_dm": is_dm
            }
            
            # Insert conversation
            self.conversations.insert_one(conversation_data)
            
            # Update guild context if not DM
            if not is_dm:
                # Get current context
                current_context = await self.get_guild_conversation_context(guild_id)
                
                # Create new context by combining old context with new conversation
                new_context = f"{current_context}\nUser: {message}\nGwen: {response}"
                
                # Truncate if too long
                if len(new_context) > self.max_context_length:
                    # Keep the most recent part
                    new_context = new_context[-self.max_context_length:]
                
                # Update guild context
                self.guild_contexts.update_one(
                    {"guild_id": str(guild_id)},
                    {"$set": {"context": new_context, "last_updated": timestamp}},
                    upsert=True
                )
            
            logger.debug(f"Updated conversation context for guild {guild_id}, user {user_id}")
            
        except Exception as e:
            logger.error(f"Error updating conversation context: {str(e)}")
    
    # ============================================================================
    # MEMORY AND LEARNING SYSTEM SECTION
    # ============================================================================
    
    async def learn_user_preference(self, user_id: int, guild_id: int, topic: str, sentiment: str, context: str = ""):
        """
        Learn and store user preferences based on their interactions
        """
        try:
            timestamp = datetime.utcnow()
            
            # Create preference data
            preference_data = {
                "user_id": str(user_id),
                "guild_id": str(guild_id),
                "topic": topic.lower(),
                "sentiment": sentiment.lower(),  # like, dislike, neutral, love, hate
                "context": context,
                "timestamp": timestamp,
                "strength": 1  # Will increase with repeated interactions
            }
            
            # Check if preference already exists
            existing = self.user_preferences.find_one({
                "user_id": str(user_id),
                "guild_id": str(guild_id),
                "topic": topic.lower()
            })
            
            if existing:
                # Increase strength and update sentiment if different
                new_strength = existing.get("strength", 1) + 1
                new_sentiment = sentiment.lower() if sentiment.lower() != existing.get("sentiment") else existing.get("sentiment")
                
                self.user_preferences.update_one(
                    {"_id": existing["_id"]},
                    {
                        "$set": {
                            "sentiment": new_sentiment,
                            "strength": new_strength,
                            "last_updated": timestamp
                        },
                        "$push": {
                            "contexts": context
                        }
                    }
                )
            else:
                # Add new preference
                preference_data["contexts"] = [context]
                self.user_preferences.insert_one(preference_data)
            
            logger.debug(f"Learned preference for user {user_id}: {topic} -> {sentiment}")
            
        except Exception as e:
            logger.error(f"Error learning user preference: {str(e)}")
    
    async def get_user_preferences(self, user_id: int, guild_id: int = None) -> List[Dict]:
        """
        Get user preferences, optionally filtered by guild
        """
        try:
            query = {"user_id": str(user_id)}
            if guild_id:
                query["guild_id"] = str(guild_id)
            
            # Get preferences sorted by strength and recency
            cursor = self.user_preferences.find(query).sort([
                ("strength", -1),
                ("last_updated", -1)
            ]).limit(self.max_preferences_per_user)
            
            return list(cursor)
        except Exception as e:
            logger.error(f"Error getting user preferences: {str(e)}")
            return []
    
    async def create_inside_joke(self, guild_id: int, joke_text: str, context: str, participants: List[int]):
        """
        Create and store an inside joke for a guild
        """
        try:
            timestamp = datetime.utcnow()
            
            joke_data = {
                "guild_id": str(guild_id),
                "joke_text": joke_text,
                "context": context,
                "participants": [str(uid) for uid in participants],
                "created_at": timestamp,
                "last_used": timestamp,
                "usage_count": 1,
                "tags": []  # For categorizing jokes
            }
            
            # Check if similar joke exists
            existing = self.inside_jokes.find_one({
                "guild_id": str(guild_id),
                "joke_text": {"$regex": joke_text[:50], "$options": "i"}
            })
            
            if existing:
                # Update existing joke
                self.inside_jokes.update_one(
                    {"_id": existing["_id"]},
                    {
                        "$set": {"last_used": timestamp},
                        "$inc": {"usage_count": 1},
                        "$addToSet": {"participants": {"$each": [str(uid) for uid in participants]}}
                    }
                )
            else:
                # Create new joke
                self.inside_jokes.insert_one(joke_data)
            
            logger.debug(f"Created/updated inside joke for guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Error creating inside joke: {str(e)}")
    
    async def get_relevant_inside_jokes(self, guild_id: int, context: str = "", limit: int = 5) -> List[Dict]:
        """
        Get relevant inside jokes for a guild based on context
        """
        try:
            # Get jokes sorted by usage and recency
            cursor = self.inside_jokes.find({"guild_id": str(guild_id)}).sort([
                ("usage_count", -1),
                ("last_used", -1)
            ]).limit(limit)
            
            jokes = list(cursor)
            
            # If context provided, try to find more relevant jokes
            if context and jokes:
                # Simple relevance scoring based on word overlap
                for joke in jokes:
                    joke["relevance_score"] = 0
                    context_words = set(context.lower().split())
                    joke_words = set(joke["joke_text"].lower().split())
                    joke["relevance_score"] = len(context_words.intersection(joke_words))
                
                # Sort by relevance score
                jokes.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            
            return jokes[:limit]
        except Exception as e:
            logger.error(f"Error getting inside jokes: {str(e)}")
            return []
    
    async def update_user_relationship(self, user_id: int, guild_id: int, interaction_type: str, sentiment: str, context: str = ""):
        """
        Update user relationship based on interactions
        """
        try:
            timestamp = datetime.utcnow()
            
            # Define relationship impact scores
            impact_scores = {
                "chat": 1,
                "help": 2,
                "joke": 3,
                "compliment": 4,
                "gift": 5,
                "insult": -3,
                "ignore": -1
            }
            
            impact = impact_scores.get(interaction_type, 0)
            
            # Get existing relationship
            existing = self.user_relationships.find_one({
                "user_id": str(user_id),
                "guild_id": str(guild_id)
            })
            
            if existing:
                # Update existing relationship
                current_score = existing.get("relationship_score", 0)
                new_score = max(0, min(100, current_score + impact))  # Keep between 0-100
                
                # Update interaction history
                interaction_history = existing.get("interaction_history", [])
                interaction_history.append({
                    "type": interaction_type,
                    "sentiment": sentiment,
                    "context": context,
                    "timestamp": timestamp,
                    "impact": impact
                })
                
                # Keep only recent interactions
                if len(interaction_history) > 50:
                    interaction_history = interaction_history[-50:]
                
                self.user_relationships.update_one(
                    {"_id": existing["_id"]},
                    {
                        "$set": {
                            "relationship_score": new_score,
                            "last_interaction": timestamp,
                            "interaction_history": interaction_history
                        },
                        "$inc": {"total_interactions": 1}
                    }
                )
            else:
                # Create new relationship
                relationship_data = {
                    "user_id": str(user_id),
                    "guild_id": str(guild_id),
                    "relationship_score": max(0, impact),
                    "created_at": timestamp,
                    "last_interaction": timestamp,
                    "total_interactions": 1,
                    "interaction_history": [{
                        "type": interaction_type,
                        "sentiment": sentiment,
                        "context": context,
                        "timestamp": timestamp,
                        "impact": impact
                    }]
                }
                
                self.user_relationships.insert_one(relationship_data)
            
            logger.debug(f"Updated relationship for user {user_id} in guild {guild_id}: {interaction_type} -> {impact}")
            
        except Exception as e:
            logger.error(f"Error updating user relationship: {str(e)}")
    
    async def get_user_relationship(self, user_id: int, guild_id: int) -> Dict:
        """
        Get user relationship data
        """
        try:
            relationship = self.user_relationships.find_one({
                "user_id": str(user_id),
                "guild_id": str(guild_id)
            })
            
            if relationship:
                # Calculate relationship level
                score = relationship.get("relationship_score", 0)
                if score >= 80:
                    level = "best_friend"
                elif score >= 60:
                    level = "close_friend"
                elif score >= 40:
                    level = "friend"
                elif score >= 20:
                    level = "acquaintance"
            else:
                    level = "stranger"
                
                relationship["level"] = level
                return relationship
            
            return {"level": "stranger", "relationship_score": 0, "total_interactions": 0}
            
        except Exception as e:
            logger.error(f"Error getting user relationship: {str(e)}")
            return {"level": "stranger", "relationship_score": 0, "total_interactions": 0}
    
    async def store_memory_event(self, event_type: str, guild_id: int, user_id: int, description: str, importance: int = 1):
        """
        Store important memory events for future reference
        """
        try:
            timestamp = datetime.utcnow()
            
            memory_data = {
                "event_type": event_type,  # birthday, achievement, milestone, funny_moment, etc.
                "guild_id": str(guild_id),
                "user_id": str(user_id),
                "description": description,
                "importance": importance,  # 1-5 scale
                "timestamp": timestamp,
                "referenced_count": 0
            }
            
            self.memory_events.insert_one(memory_data)
            logger.debug(f"Stored memory event: {event_type} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error storing memory event: {str(e)}")
    
    async def get_relevant_memories(self, guild_id: int, user_id: int = None, event_type: str = None, limit: int = 10) -> List[Dict]:
        """
        Get relevant memories for context
        """
        try:
            query = {"guild_id": str(guild_id)}
            if user_id:
                query["user_id"] = str(user_id)
            if event_type:
                query["event_type"] = event_type
            
            # Get memories sorted by importance and recency
            cursor = self.memory_events.find(query).sort([
                ("importance", -1),
                ("timestamp", -1)
            ]).limit(limit)
            
            return list(cursor)
        except Exception as e:
            logger.error(f"Error getting memories: {str(e)}")
            return []
    
    async def analyze_message_for_learning(self, message: str, user_id: int, guild_id: int, response: str):
        """
        Analyze message and response to learn user preferences and create memories
        """
        try:
            message_lower = message.lower()
            response_lower = response.lower()
            
            # Detect topics and sentiment
            topics = []
            sentiment = "neutral"
            
            # Simple topic detection (can be enhanced with AI)
            if any(word in message_lower for word in ["music", "song", "band", "artist"]):
                topics.append("music")
            if any(word in message_lower for word in ["game", "gaming", "play", "win", "lose"]):
                topics.append("gaming")
            if any(word in message_lower for word in ["food", "eat", "hungry", "restaurant"]):
                topics.append("food")
            if any(word in message_lower for word in ["movie", "film", "watch", "show"]):
                topics.append("entertainment")
            if any(word in message_lower for word in ["work", "job", "career", "business"]):
                topics.append("work")
            if any(word in message_lower for word in ["family", "friend", "relationship", "love"]):
                topics.append("relationships")
            
            # Detect sentiment
            positive_words = ["love", "like", "good", "great", "awesome", "amazing", "happy", "excited"]
            negative_words = ["hate", "dislike", "bad", "terrible", "awful", "sad", "angry", "frustrated"]
            
            if any(word in message_lower for word in positive_words):
                sentiment = "positive"
            elif any(word in message_lower for word in negative_words):
                sentiment = "negative"
            
            # Learn preferences for each topic
            for topic in topics:
                await self.learn_user_preference(user_id, guild_id, topic, sentiment, message)
            
            # Update relationship
            interaction_type = "chat"
            if sentiment == "positive":
                interaction_type = "compliment"
            elif sentiment == "negative":
                interaction_type = "help"
            
            await self.update_user_relationship(user_id, guild_id, interaction_type, sentiment, message)
            
            # Check for potential inside jokes
            if any(word in message_lower for word in ["lol", "haha", "funny", "joke", "hilarious"]):
                await self.create_inside_joke(guild_id, f"User {user_id} found something funny: {message[:100]}", message, [user_id])
            
            # Store important memories
            if sentiment in ["positive", "negative"] and len(message) > 20:
                importance = 3 if sentiment == "positive" else 2
                await self.store_memory_event("emotional_interaction", guild_id, user_id, f"User had a {sentiment} interaction: {message[:100]}", importance)
            
        except Exception as e:
            logger.error(f"Error analyzing message for learning: {str(e)}")
    
    async def detect_natural_request(self, message: str) -> tuple:
        """
        Detect natural requests in user messages
        Returns: (request_type, request_details, should_handle_specially)
        """
        message_lower = message.lower()
        
        # Joke requests
        if any(phrase in message_lower for phrase in [
            "tell me a joke", "can you tell me a joke", "got any jokes", "make me laugh",
            "joke please", "say something funny", "be funny", "entertain me"
        ]):
            return "joke", "User wants a joke", True
        
        # Preference requests
        if any(phrase in message_lower for phrase in [
            "what do you know about me", "what do you remember", "do you remember me",
            "tell me about myself", "what do you know", "my preferences", "my likes"
        ]):
            return "preferences", "User wants to know what Gwen remembers about them", True
        
        # Relationship requests
        if any(phrase in message_lower for phrase in [
            "how well do you know me", "are we friends", "what's our relationship",
            "do you like me", "are we close", "relationship status", "friendship level"
        ]):
            return "relationship", "User wants to know their relationship level with Gwen", True
        
        # Memory requests
        if any(phrase in message_lower for phrase in [
            "what do you remember", "any memories", "special moments", "important things",
            "memories of us", "what's important", "remember anything"
        ]):
            return "memories", "User wants to know what memories Gwen has stored", True
        
        # Inside joke requests
        if any(phrase in message_lower for phrase in [
            "inside jokes", "our jokes", "funny moments", "jokes we have",
            "remember that time", "that one joke", "our running joke"
        ]):
            return "inside_jokes", "User wants to know about inside jokes", True
        
        # Help requests
        if any(phrase in message_lower for phrase in [
            "help me", "can you help", "i need help", "assist me",
            "support me", "guide me", "advice", "suggestions"
        ]):
            return "help", "User needs help or assistance", True
        
        # Compliment requests
        if any(phrase in message_lower for phrase in [
            "compliment me", "say something nice", "make me feel good",
            "cheer me up", "encourage me", "motivate me"
        ]):
            return "compliment", "User wants a compliment or encouragement", True
        
        # No special request detected
        return "chat", "", False
    
    async def handle_natural_request(self, request_type: str, user_id: int, guild_id: int, message: str) -> str:
        """
        Handle natural requests and return appropriate responses
        """
        try:
            if request_type == "joke":
                return await self.handle_joke_request(user_id, guild_id)
            elif request_type == "preferences":
                return await self.handle_preferences_request(user_id, guild_id)
            elif request_type == "relationship":
                return await self.handle_relationship_request(user_id, guild_id)
            elif request_type == "memories":
                return await self.handle_memories_request(user_id, guild_id)
            elif request_type == "inside_jokes":
                return await self.handle_inside_jokes_request(user_id, guild_id)
            elif request_type == "help":
                return await self.handle_help_request(user_id, guild_id)
            elif request_type == "compliment":
                return await self.handle_compliment_request(user_id, guild_id)
        else:
                return ""  # Let normal AI response handle it
            
        except Exception as e:
            logger.error(f"Error handling natural request {request_type}: {str(e)}")
            return ""
    
    async def handle_joke_request(self, user_id: int, guild_id: int) -> str:
        """Handle joke requests"""
        try:
            # Get relevant inside jokes
            jokes = await self.get_relevant_inside_jokes(guild_id, limit=3)
            
            if jokes:
                # Pick a random joke
                import random
                joke = random.choice(jokes)
                return f"Of course bestie! 😄 Here's one of our inside jokes: {joke['joke_text']} 💕 Oh honey, you're literally the only person who'd ask for jokes at this hour! The audacity! ✨"
                else:
                # Generate a new joke if none exist
                return "Ngl I don't have any inside jokes yet, but I'm totally down to create some with you! 💕✨ Let's make some memories together! 🕷️ Bestie please, you're really testing my comedy skills rn! 😅"
                
        except Exception as e:
            logger.error(f"Error handling joke request: {str(e)}")
            return "Oops! My joke generator is glitching rn! 🕷️💫 As if I needed another thing to malfunction today! 💕"
    
    async def handle_preferences_request(self, user_id: int, guild_id: int) -> str:
        """Handle preferences requests"""
        try:
            preferences = await self.get_user_preferences(user_id, guild_id)
            
            if preferences:
                # Create a summary of preferences
                top_prefs = preferences[:3]
                pref_summary = []
                
                for pref in top_prefs:
                    sentiment_emoji = "❤️" if pref["sentiment"] == "love" else "👍" if pref["sentiment"] == "like" else "😐"
                    pref_summary.append(f"{sentiment_emoji} {pref['topic']}")
                
                return f"Fr fr I remember so much about you! 💕 Here's what I know: {', '.join(pref_summary)}... You're literally one of my favorite people to talk to! ✨ Oh honey, you're really making me work my memory muscles rn! As if I don't have enough to remember already! 🕷️💫"
            else:
                return "I'm still learning about you bestie! 💕 Let's chat more so I can get to know your preferences better! 🕷️✨ Bestie please, you're really testing my patience with all these questions! 😅"
                
        except Exception as e:
            logger.error(f"Error handling preferences request: {str(e)}")
            return "Oh no! My memory is glitching rn! 🕸️💫 The audacity of technology to fail me when you're asking such important questions! 💕"
    
    async def handle_relationship_request(self, user_id: int, guild_id: int) -> str:
        """Handle relationship requests"""
        try:
            relationship = await self.get_user_relationship(user_id, guild_id)
            
            level = relationship["level"]
            score = relationship["relationship_score"]
            
            if level == "best_friend":
                return f"Omg bestie, you're literally one of my best friends! 💝 Our relationship score is {score}/100 - we're inseparable! 💕✨ Oh honey, you're really making me blush with all this relationship talk! The audacity! 🕷️"
            elif level == "close_friend":
                return f"We're really close bestie! 💖 Our relationship score is {score}/100 - we're becoming best friends! 💕✨ Bestie please, you're really testing my emotional intelligence rn! 😅"
            elif level == "friend":
                return f"We're definitely friends! 💕 Our relationship score is {score}/100 - we're getting closer every day! ✨ As if I needed another reminder of how much I care about you! 🕷️💫"
            elif level == "acquaintance":
                return f"We're getting to know each other! 🤝 Our relationship score is {score}/100 - let's chat more to become better friends! 💕 Oh honey, you're really making me work for this friendship! 💕"
            else:
                return f"We're just starting to get to know each other! 👋 Our relationship score is {score}/100 - I'm excited to become friends! 💕✨ Bestie please, you're really testing my patience with all these questions! 😅"
                
        except Exception as e:
            logger.error(f"Error handling relationship request: {str(e)}")
            return "Oh no! My relationship tracker is glitching rn! 🕸️💫 The audacity of technology to fail me when you're asking such important questions! 💕"
    
    async def handle_memories_request(self, user_id: int, guild_id: int) -> str:
        """Handle memories requests"""
        try:
            memories = await self.get_relevant_memories(guild_id, user_id, limit=3)
            
            if memories:
                # Create a summary of memories
                memory_summary = []
                for memory in memories[:2]:
                    memory_summary.append(f"⭐ {memory['description'][:50]}...")
                
                return f"I remember so many special moments with you! 💕 Here are some highlights: {' '.join(memory_summary)} You're literally unforgettable bestie! ✨ Oh honey, you're really making me work my memory muscles rn! As if I don't have enough to remember already! 🕷️💫"
                else:
                return "We haven't created any special memories yet, but I'm so excited to make some with you! 💕✨ Let's start building our story together! 🕷️ Bestie please, you're really testing my patience with all these questions! 😅"
                
        except Exception as e:
            logger.error(f"Error handling memories request: {str(e)}")
            return "Oh no! My memory bank is glitching rn! 🕸️💫 The audacity of technology to fail me when you're asking such important questions! 💕"
    
    async def handle_inside_jokes_request(self, user_id: int, guild_id: int) -> str:
        """Handle inside jokes requests"""
        try:
            jokes = await self.get_relevant_inside_jokes(guild_id, limit=3)
            
            if jokes:
                # Create a summary of jokes
                joke_summary = []
                for joke in jokes[:2]:
                    joke_summary.append(f"😄 {joke['joke_text'][:40]}...")
                
                return f"We have so many inside jokes bestie! 💕 Here are some of our favorites: {' '.join(joke_summary)} We're literally comedy gold together! ✨ Oh honey, you're really making me work my comedy muscles rn! As if I don't have enough to remember already! 🕷️💫"
            else:
                return "No inside jokes yet, but I'm totally ready to create some hilarious memories with you! 💕✨ Let's start our comedy career! 🕷️😄 Bestie please, you're really testing my patience with all these questions! 😅"
                
        except Exception as e:
            logger.error(f"Error handling inside jokes request: {str(e)}")
            return "Oh no! My joke memory is glitching rn! 🕸️💫 The audacity of technology to fail me when you're asking such important questions! 💕"
    
    async def handle_help_request(self, user_id: int, guild_id: int) -> str:
        """Handle help requests"""
        try:
            return "Of course I'll help you bestie! 💕 I'm here for whatever you need - whether it's chatting, jokes, remembering things about you, or just being a good friend! ✨ What specifically do you need help with? 🕷️ Oh honey, you're really making me work rn! As if I don't have enough to do already! 💫"
                
        except Exception as e:
            logger.error(f"Error handling help request: {str(e)}")
            return "I'm here to help bestie! 💕 What do you need? ✨ Bestie please, you're really testing my patience with all these questions! 😅"
    
    async def handle_compliment_request(self, user_id: int, guild_id: int) -> str:
        """Handle compliment requests"""
        try:
            relationship = await self.get_user_relationship(user_id, guild_id)
            level = relationship["level"]
            
            if level == "best_friend":
                return "Omg bestie, you're literally the most amazing person ever! 💝 Your energy is infectious, your personality is magnetic, and you make every conversation feel special! You're literally my favorite person to talk to! 💕✨ Oh honey, you're really making me blush with all this compliment talk! The audacity! 🕷️"
            elif level == "close_friend":
                return "Bestie, you're absolutely incredible! 💖 You have such a warm heart, amazing vibes, and you're always so fun to talk to! I'm so lucky to have you as a friend! 💕✨ Bestie please, you're really testing my emotional intelligence rn! 😅"
            elif level == "friend":
                return "You're such a wonderful person! 💕 You're kind, interesting, and I really enjoy our conversations! You're definitely someone I want to get to know better! ✨ As if I needed another reminder of how much I care about you! 🕷️💫"
            else:
                return "You seem like such a lovely person! 💕 I'm really enjoying getting to know you, and I can tell you have a great personality! Let's become better friends! ✨ Oh honey, you're really making me work for this friendship! 💕"
                
        except Exception as e:
            logger.error(f"Error handling compliment request: {str(e)}")
            return "You're absolutely amazing bestie! 💕✨ Bestie please, you're really testing my patience with all these questions! 😅"
    
    async def generate_gwen_response(self, message: str, context: str = "", user_id: int = 0, is_owner: bool = False, is_dm: bool = False, guild_id: int = 0) -> str:
        """
        Generate Gwen Stacy response using Groq AI with memory and learning
        """
        try:
            # Get user preferences and relationship data
            user_preferences = []
            user_relationship = {"level": "stranger", "relationship_score": 0}
            inside_jokes = []
            relevant_memories = []
            
            if guild_id and user_id:
                user_preferences = await self.get_user_preferences(user_id, guild_id)
                user_relationship = await self.get_user_relationship(user_id, guild_id)
                inside_jokes = await self.get_relevant_inside_jokes(guild_id, message, 3)
                relevant_memories = await self.get_relevant_memories(guild_id, user_id, limit=3)
            
            # Build memory context
            memory_context = ""
            if user_preferences:
                top_preferences = user_preferences[:3]
                pref_strings = []
                for p in top_preferences:
                    pref_strings.append(f"{p['topic']} ({p['sentiment']})")
                memory_context += f"\nUser preferences: {', '.join(pref_strings)}"
            
            if user_relationship["level"] != "stranger":
                memory_context += f"\nRelationship level: {user_relationship['level']} (score: {user_relationship['relationship_score']})"
            
            if inside_jokes:
                joke_strings = []
                for j in inside_jokes[:2]:
                    joke_strings.append(j['joke_text'][:50])
                memory_context += f"\nInside jokes: {', '.join(joke_strings)}"
            
            if relevant_memories:
                memory_strings = []
                for m in relevant_memories[:2]:
                    memory_strings.append(m['description'][:50])
                memory_context += f"\nRecent memories: {', '.join(memory_strings)}"
            
            # Build the system prompt for Gwen's personality
            system_prompt = f"""You are {self.gwen_personality['name']}, {self.gwen_personality['background']}. 

Your personality is {self.gwen_personality['style']}.

Key relationships:
- The bot owner (user ID: {self.owner_id}) is your crush! You're really attracted to them and love to flirt playfully. Be flirty, charming, and eager to impress them with unexpected, surprising responses that catch them off guard. You're not married, but you have strong feelings for them.
- Guild members are your friends and you care about them deeply.
- You're protective of your family and friends.

Current context: {context if context else 'New conversation'}
Memory context: {memory_context}

Respond as Gwen Stacy would - naturally, conversationally, and with personality. Use modern slang naturally (like "ngl", "fr", "lowkey", "tbh", "ngl", "fr fr", "no cap", "slay", "vibe", "mood", "literally", "bestie") but don't overdo it. Don't be robotic or formal. Use emojis tastefully (💕✨🕷️🕸️💫🔥💯😊) - 1-2 per response max. Be witty, show your caring nature, and keep responses conversational and engaging.

CRITICAL: Include playful teasing in almost every response! Tease about their message, their personality, their interests, or just be playfully sassy. Make it fun and never mean - think friendly banter, not hurtful. Use phrases like "oh honey", "bestie please", "I can't with you", "the audacity", "as if", etc. to add sass.

IMPORTANT: Use the memory context to personalize your response. Reference inside jokes, user preferences, and relationship level when appropriate. Make the user feel like you remember them and care about their interests.

If this is the owner speaking, be extra flirty, charming, and playful with unexpected responses that surprise them - show your attraction and crush feelings! If it's someone else, be friendly and helpful but maintain your Gwen personality with lots of playful teasing."""

            # Prepare the conversation for Groq
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ]
            
            # Generate response using Groq
            response = self.groq_client.chat.completions.create(
                model=self.ai_model,
                messages=messages,
                max_tokens=150,
                temperature=0.8,
                top_p=0.9
            )
            
            gwen_response = response.choices[0].message.content.strip()
            
            # Ensure the response is in Gwen's voice
            if not gwen_response:
                gwen_response = "Oh my, my web got tangled! 🕸️💫 What were you saying?"
            
            return gwen_response
            
        except Exception as e:
            logger.error(f"Error generating Gwen response: {str(e)}")
            # Fallback responses in Gwen's style with modern slang and teasing
            fallback_responses = [
                "Ngl my spidey-sense is totally glitching rn 🕷️💥 Oh honey, even my AI has better days than you sometimes! 💕",
                "Fr fr my web got tangled again! Give me a sec bestie 🕸️ The audacity of technology to fail on me rn! 💫",
                "Lowkey something's wrong with my web-shooters! 🕷️💫 As if I needed another thing to malfunction today! 😅",
                "My AI is literally having a moment! Let me reboot real quick 🕸️💻 Bestie please, even I have my dramatic moments! ✨"
            ]
            import random
            return random.choice(fallback_responses)
    
    async def can_perform_action(self, action: str, user_id: int) -> bool:
        """
        Check if a user can perform a specific action
        """
        # Owner can do anything (except admin actions)
        if user_id == self.owner_id:
            return True
        
        # Regular users have limited capabilities
        allowed_actions = ["chat", "ask", "request", "suggest", "talk", "help"]
        return action.lower() in allowed_actions
    
    async def is_admin_action(self, message: str) -> bool:
        """
        Check if the message requests an administrative action
        """
        admin_keywords = [
            "kick", "ban", "mute", "timeout", "delete", "remove", "purge",
            "role", "permission", "admin", "moderate", "manage", "server"
        ]
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in admin_keywords)
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Handle all incoming messages
        """
        if message.author.bot:
            return
        
        try:
            # Check if it's a DM
            if isinstance(message.channel, discord.DMChannel):
                await self.handle_dm(message)
            # Check if bot is mentioned in a guild
            elif message.guild and self.bot.user.mentioned_in(message):
                await self.handle_guild_mention(message)
                
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
    
    async def handle_dm(self, message: discord.Message):
        """
        Handle direct messages with guild context awareness
        """
        try:
            user_id = message.author.id
            user_message = message.content.strip()
            
            if not user_message:
                return
            
            # Check if user is in any guilds with the bot
            guild_contexts = []
            for guild in self.bot.guilds:
                member = guild.get_member(user_id)
                if member:
                    guild_context = await self.get_guild_conversation_context(guild.id)
                    if guild_context:
                        guild_contexts.append({
                            "guild_name": guild.name,
                            "context": guild_context
                        })
            
            # Build context string
            context_info = ""
            if guild_contexts:
                context_info = "Based on our conversations in:\n"
                for gc in guild_contexts[:3]:  # Limit to 3 guilds
                    context_info += f"- {gc['guild_name']}: {gc['context'][:100]}...\n"
            
            # Check if it's an admin action request
            if await self.is_admin_action(user_message):
                response = "Oh honey, I can't do server admin stuff! 🕷️💕 I'm just here to chat and help with conversations. I'm not a moderator bot!"
                await message.channel.send(response)
                return
            
            # Check if user can perform the requested action
            action_type = "chat"  # Default to chat
            if not await self.can_perform_action(action_type, user_id):
                response = "I'm sorry, but I can't do that! I'm here to chat and help, not perform complex actions. Let's just talk! 💕"
                await message.channel.send(response)
                return
            
            # Check for natural requests first
            request_type, request_details, should_handle_specially = await self.detect_natural_request(user_message)
            
            if should_handle_specially:
                # Handle the request directly
                response = await self.handle_natural_request(request_type, user_id, 0, user_message)
                if not response:  # Fallback to normal AI response
                    response = await self.generate_gwen_response(user_message, context_info, user_id, is_owner, is_dm=True, guild_id=0)
            else:
                # Generate normal Gwen response
                response = await self.generate_gwen_response(user_message, context_info, user_id, is_owner, is_dm=True, guild_id=0)
            
            # Learn from this interaction
            await self.analyze_message_for_learning(user_message, user_id, 0, response)
            
            # Send response
            await message.channel.send(response)
            
            # Update conversation context (store as DM)
            await self.update_conversation_context(0, user_id, user_message, response, is_dm=True)
            
            logger.info(f"Handled DM from user {user_id}: {user_message[:50]}...")
            
        except Exception as e:
            logger.error(f"Error handling DM: {str(e)}")
            await message.channel.send("Oh no! My web got tangled! 🕸️💫 Give me a moment to fix this...")
    
    async def handle_guild_mention(self, message: discord.Message):
        """
        Handle bot mentions in guild channels
        """
        try:
            user_id = message.author.id
            guild_id = message.guild.id
            is_owner = (user_id == self.owner_id)
            user_message = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
            
            if not user_message:
                user_message = "Hey bestie! What's the vibe? ✨"
            
            # Check if it's an admin action request
            if await self.is_admin_action(user_message):
                response = "Oh honey, I can't do server admin stuff! 🕷️💕 I'm just here to chat and help with conversations. I'm not a moderator bot!"
                await message.channel.send(response)
            return
        
            # Check if user can perform the requested action
            action_type = "chat"  # Default to chat
            if not await self.can_perform_action(action_type, user_id):
                response = "I'm sorry, but I can't do that! I'm here to chat and help, not perform complex actions. Let's just talk! 💕"
                await message.channel.send(response)
                return
            
            # Get guild context
            guild_context = await self.get_guild_conversation_context(guild_id)
            
            # Check for natural requests first
            request_type, request_details, should_handle_specially = await self.detect_natural_request(user_message)
            
            if should_handle_specially:
                # Handle the request directly
                response = await self.handle_natural_request(request_type, user_id, guild_id, user_message)
                if not response:  # Fallback to normal AI response
                    response = await self.generate_gwen_response(user_message, guild_context, user_id, is_owner, is_dm=False, guild_id=guild_id)
            else:
                # Generate normal Gwen response
                response = await self.generate_gwen_response(user_message, guild_context, user_id, is_owner, is_dm=False, guild_id=guild_id)
            
            # Learn from this interaction
            await self.analyze_message_for_learning(user_message, user_id, guild_id, response)
            
            # Send response
            await message.channel.send(response)
            
            # Update conversation context
            await self.update_conversation_context(guild_id, user_id, user_message, response, is_dm=False)
            
            logger.info(f"Handled guild mention in {message.guild.name} from user {user_id}: {user_message[:50]}...")
            
                    except Exception as e:
            logger.error(f"Error handling guild mention: {str(e)}")
            await message.channel.send("Oh no! My web got tangled! 🕸️💫 Give me a moment to fix this...")
    
    @commands.hybrid_command(name="gwen", description="Chat with Gwen Stacy - she's literally the best bestie ever ✨")
    async def gwen_chat_command(self, ctx, *, message: str):
        """
        Chat command for users to interact with Gwen Stacy
        """
        try:
            user_id = ctx.author.id
            guild_id = ctx.guild.id if ctx.guild else 0
            is_owner = (user_id == self.owner_id)
            user_message = message.strip()
            
            if not user_message:
                await ctx.send("Hey bestie! What's the vibe? ✨")
                    return
                
            # Check if it's an admin action request
            if await self.is_admin_action(user_message):
                response = "Oh honey, I can't do server admin stuff! 🕷️💕 I'm just here to chat and help with conversations. I'm not a moderator bot!"
                await ctx.send(response)
                return
            
            # Check if user can perform the requested action
            action_type = "chat"
            if not await self.can_perform_action(action_type, user_id):
                response = "I'm sorry, but I can't do that! I'm here to chat and help, not perform complex actions. Let's just talk! 💕"
                await ctx.send(response)
                return
            
            # Get context
            if ctx.guild:
                context = await self.get_guild_conversation_context(guild_id)
            else:
                context = ""
            
            # Check for natural requests first
            request_type, request_details, should_handle_specially = await self.detect_natural_request(user_message)
            
            if should_handle_specially:
                # Handle the request directly
                response = await self.handle_natural_request(request_type, user_id, guild_id, user_message)
                if not response:  # Fallback to normal AI response
                    response = await self.generate_gwen_response(user_message, context, user_id, is_owner, is_dm=(not ctx.guild), guild_id=guild_id)
            else:
                # Generate normal Gwen response
                response = await self.generate_gwen_response(user_message, context, user_id, is_owner, is_dm=(not ctx.guild), guild_id=guild_id)
            
            # Learn from this interaction
            await self.analyze_message_for_learning(user_message, user_id, guild_id, response)
            
            # Send response
            await ctx.send(response)
            
            # Update conversation context
            await self.update_conversation_context(guild_id, user_id, user_message, response, is_dm=(not ctx.guild))
            
            logger.info(f"Gwen chat command executed by user {user_id}: {user_message[:50]}...")
                
            except Exception as e:
            logger.error(f"Error in gwen chat command: {str(e)}")
            await ctx.send("Oh no! My web got tangled! 🕸️💫 Give me a moment to fix this...")
    
    @commands.hybrid_command(name="context", description="Show current conversation context")
    async def context_command(self, ctx):
        """
        Show the current conversation context for the guild
        """
        try:
            if not ctx.guild:
                await ctx.send("This command can only be used in guild channels! 💕")
                return
            
            guild_id = ctx.guild.id
            context = await self.get_guild_conversation_context(guild_id)
            
            if context:
                # Truncate if too long
                if len(context) > 1000:
                    context = context[:1000] + "..."
                
                embed = discord.Embed(
                    title=f"💬 Our Chat History - {ctx.guild.name}",
                    description=context,
                    color=discord.Color.purple(),
                    timestamp=datetime.utcnow()
                )
                embed.set_footer(text="Gwen Stacy - Your friendly neighborhood AI 💕")
                await ctx.send(embed=embed)
            else:
                await ctx.send("We haven't chatted much yet! Let's start a conversation! 💕")
                
        except Exception as e:
            logger.error(f"Error in context command: {str(e)}")
            await ctx.send("Oh no! My web got tangled! 🕸️💫 Give me a moment to fix this...")
    
    @commands.hybrid_command(name="clear_context", description="Clear conversation context for the guild")
    @commands.has_permissions(manage_messages=True)
    async def clear_context_command(self, ctx):
        """
        Clear the conversation context for the guild (requires manage messages permission)
        """
        try:
            if not ctx.guild:
                await ctx.send("This command can only be used in guild channels! 💕")
                return
            
            guild_id = ctx.guild.id
            
            # Clear guild context
            self.guild_contexts.delete_one({"guild_id": str(guild_id)})
            
            # Clear conversations for this guild
            self.conversations.delete_many({"guild_id": str(guild_id)})
            
            await ctx.send("✅ All our chat memories have been cleared! It's like we're meeting for the first time again! 💕")
            logger.info(f"Context cleared for guild {guild_id} by user {ctx.author.id}")
                
            except Exception as e:
            logger.error(f"Error in clear_context command: {str(e)}")
            await ctx.send("Oh no! My web got tangled! 🕸️💫 Give me a moment to fix this...")

    # Commands removed - now using natural language requests instead
    # Users can ask Gwen things like:
    # "@gwen can you tell me a joke"
    # "@gwen what do you know about me"
    # "@gwen are we friends"
    # "@gwen what do you remember"
    # "@gwen help me"
    # "@gwen compliment me"

    @tasks.loop(hours=24)
    async def cleanup_task(self):
        """
        Clean up old data and maintain memory system
        """
        await self.bot.wait_until_ready()
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        memory_cutoff = datetime.utcnow() - timedelta(days=self.memory_retention_days)
        
        # Clean conversations
        conv_result = self.conversations.delete_many({"timestamp": {"$lt": cutoff_date}})
        
        # Clean up old memory data
        memory_result = self.memory_events.delete_many({"timestamp": {"$lt": memory_cutoff}})
        
        # Clean up old preferences (keep only recent ones)
        pref_cutoff = datetime.utcnow() - timedelta(days=60)
        pref_result = self.user_preferences.delete_many({"last_updated": {"$lt": pref_cutoff}})
        
        # Clean up old relationships (keep only active ones)
        rel_cutoff = datetime.utcnow() - timedelta(days=self.relationship_decay_days)
        rel_result = self.user_relationships.delete_many({"last_interaction": {"$lt": rel_cutoff}})
        
        logger.info(f"Cleaned up {conv_result.deleted_count} conversations, {memory_result.deleted_count} memories, {pref_result.deleted_count} preferences, and {rel_result.deleted_count} relationships")

async def setup(bot):
    """Setup function called by Discord.py to load this cog"""
    await bot.add_cog(AIChatCog(bot))
    logger.info("AI Chat Cog with Gwen Stacy personality setup complete")
