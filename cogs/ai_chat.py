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
import random

logger = logging.getLogger(__name__)

# Configuration constants
CONFIG = {
    "max_messages_per_context": 50,
    "max_context_length": 1000,
    "max_preferences_per_user": 20,
    "max_inside_jokes_per_guild": 30,
    "relationship_decay_days": 30,
    "memory_retention_days": 90,
    "groq_max_tokens": 150,
    "groq_temperature": 0.8,
    "groq_top_p": 0.9,
    "max_input_length": 2000,  # Prevent overly long messages
    "rate_limit_per_user": 5,  # Messages per minute
}

class AIChatCog(commands.Cog):
    """
    AI Chat Cog with Gwen Stacy personality and Groq AI integration
    """
    
    def __init__(self, bot):
        """Initialize the AI Chat Cog"""
        self.bot = bot
        self.owner_id = os.getenv("OWNER_ID")
        if not self.owner_id:
            logger.error("OWNER_ID not found in environment variables!")
            raise ValueError("OWNER_ID is required for AI Chat Cog")
        self.owner_id = int(self.owner_id)
        
        # Groq AI client
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            logger.error("GROQ_API_KEY not found in environment variables!")
            raise ValueError("GROQ_API_KEY is required for AI Chat Cog")
        
        self.groq_client = Groq(api_key=groq_api_key)
        self.ai_model = "llama-3.1-8b-instant"
        
        # MongoDB connection
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            logger.error("MONGO_URI not found in environment variables!")
            raise ValueError("MONGO_URI is required for AI Chat Cog")
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client["ai_chat_bot"]
        self.conversations = self.db["conversations"]
        self.guild_contexts = self.db["guild_contexts"]
        self.user_preferences = self.db["user_preferences"]
        self.inside_jokes = self.db["inside_jokes"]
        self.user_relationships = self.db["user_relationships"]
        self.memory_events = self.db["memory_events"]
        
        # Rate limiting
        self.user_rate_limits = {}
        
        # Gwen Stacy personality settings
        self.gwen_personality = {
            "name": "Gwen Stacy",
            "style": "witty, playful, caring, and slightly sassy with modern vibes - loves to tease playfully",
            "background": "Spider-Gwen from the Spider-Verse, who has a crush on the bot owner and loves to playfully tease everyone",
            "relationships": {
                "owner": "crush and someone she's really attracted to - flirty, playful, and eager to impress with unexpected responses",
                "guild_members": "friendly and helpful, but protective of family - loves to tease them playfully",
                "general": "caring and supportive, with a bit of attitude and playful teasing"
            }
        }
        
        # Start background tasks
        self.cleanup_task.start()
        
        logger.info("AI Chat Cog with Gwen Stacy personality and memory system initialized")
    
    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        self.cleanup_task.cancel()
        try:
            self.mongo_client.close()
        except Exception as e:
            logger.error(f"Error closing MongoDB client: {str(e)}")
        logger.info("AI Chat Cog unloaded")
    
    async def get_guild_conversation_context(self, guild_id: int) -> str:
        """Get the conversation context for a specific guild"""
        try:
            guild_doc = self.guild_contexts.find_one({"guild_id": str(guild_id)})
            return guild_doc.get("context", "") if guild_doc else ""
        except Exception as e:
            logger.error(f"Error getting guild context: {str(e)}")
            return ""
    
    async def get_user_conversation_history(self, user_id: int, guild_id: Optional[int] = None) -> List[Dict]:
        """Get conversation history for a user, optionally filtered by guild"""
        try:
            query = {"user_id": str(user_id)}
            if guild_id:
                query["guild_id"] = str(guild_id)
            cursor = self.conversations.find(query).sort("timestamp", -1).limit(CONFIG["max_messages_per_context"])
            return list(cursor)
        except Exception as e:
            logger.error(f"Error getting user conversation history: {str(e)}")
            return []
    
    async def update_conversation_context(self, guild_id: int, user_id: int, message: str, response: str, is_dm: bool = False):
        """Update conversation context for a guild and user"""
        try:
            timestamp = datetime.utcnow()
            conversation_data = {
                "guild_id": str(guild_id) if not is_dm else "dm",
                "user_id": str(user_id),
                "message": message[:CONFIG["max_input_length"]],
                "response": response,
                "timestamp": timestamp,
                "is_dm": is_dm
            }
            self.conversations.insert_one(conversation_data)
            
            if not is_dm:
                current_context = await self.get_guild_conversation_context(guild_id)
                new_context = f"{current_context}\nUser: {message}\nGwen: {response}"[:CONFIG["max_context_length"]]
                self.guild_contexts.update_one(
                    {"guild_id": str(guild_id)},
                    {"$set": {"context": new_context, "last_updated": timestamp}},
                    upsert=True
                )
            logger.debug(f"Updated conversation context for guild {guild_id}, user {user_id}")
        except Exception as e:
            logger.error(f"Error updating conversation context: {str(e)}")
    
    async def learn_user_preference(self, user_id: int, guild_id: int, topic: str, sentiment: str, context: str = ""):
        """Learn and store user preferences based on their interactions"""
        try:
            timestamp = datetime.utcnow()
            preference_data = {
                "user_id": str(user_id),
                "guild_id": str(guild_id),
                "topic": topic.lower(),
                "sentiment": sentiment.lower(),
                "context": context,
                "timestamp": timestamp,
                "strength": 1
            }
            
            existing = self.user_preferences.find_one({
                "user_id": str(user_id),
                "guild_id": str(guild_id),
                "topic": topic.lower()
            })
            
            if existing:
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
                            "contexts": {"$each": [context], "$slice": -10}  # Limit context history
                        }
                    }
                )
            else:
                preference_data["contexts"] = [context]
                self.user_preferences.insert_one(preference_data)
            logger.debug(f"Learned preference for user {user_id}: {topic} -> {sentiment}")
        except Exception as e:
            logger.error(f"Error learning user preference: {str(e)}")
    
    async def get_user_preferences(self, user_id: int, guild_id: int = None) -> List[Dict]:
        """Get user preferences, optionally filtered by guild"""
        try:
            query = {"user_id": str(user_id)}
            if guild_id:
                query["guild_id"] = str(guild_id)
            cursor = self.user_preferences.find(query).sort([
                ("strength", -1),
                ("last_updated", -1)
            ]).limit(CONFIG["max_preferences_per_user"])
            return list(cursor)
        except Exception as e:
            logger.error(f"Error getting user preferences: {str(e)}")
            return []
    
    async def create_inside_joke(self, guild_id: int, joke_text: str, context: str, participants: List[int]):
        """Create and store an inside joke for a guild"""
        try:
            timestamp = datetime.utcnow()
            joke_data = {
                "guild_id": str(guild_id),
                "joke_text": joke_text[:200],  # Limit joke length
                "context": context[:500],
                "participants": [str(uid) for uid in participants],
                "created_at": timestamp,
                "last_used": timestamp,
                "usage_count": 1,
                "tags": []
            }
            
            existing = self.inside_jokes.find_one({
                "guild_id": str(guild_id),
                "joke_text": {"$regex": joke_text[:50], "$options": "i"}
            })
            
            if existing:
                self.inside_jokes.update_one(
                    {"_id": existing["_id"]},
                    {
                        "$set": {"last_used": timestamp},
                        "$inc": {"usage_count": 1},
                        "$addToSet": {"participants": {"$each": [str(uid) for uid in participants]}}
                    }
                )
            else:
                self.inside_jokes.insert_one(joke_data)
            logger.debug(f"Created/updated inside joke for guild {guild_id}")
        except Exception as e:
            logger.error(f"Error creating inside joke: {str(e)}")
    
    async def get_relevant_inside_jokes(self, guild_id: int, context: str = "", limit: int = 5) -> List[Dict]:
        """Get relevant inside jokes for a guild based on context"""
        try:
            cursor = self.inside_jokes.find({"guild_id": str(guild_id)}).sort([
                ("usage_count", -1),
                ("last_used", -1)
            ]).limit(limit)
            jokes = list(cursor)
            
            if context and jokes:
                for joke in jokes:
                    joke["relevance_score"] = len(set(context.lower().split()).intersection(set(joke["joke_text"].lower().split())))
                jokes.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            return jokes[:limit]
        except Exception as e:
            logger.error(f"Error getting inside jokes: {str(e)}")
            return []
    
    async def update_user_relationship(self, user_id: int, guild_id: int, interaction_type: str, sentiment: str, context: str = ""):
        """Update user relationship based on interactions"""
        try:
            timestamp = datetime.utcnow()
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
            
            existing = self.user_relationships.find_one({
                "user_id": str(user_id),
                "guild_id": str(guild_id)
            })
            
            if existing:
                current_score = existing.get("relationship_score", 0)
                new_score = max(0, min(100, current_score + impact))
                interaction_history = existing.get("interaction_history", [])
                interaction_history.append({
                    "type": interaction_type,
                    "sentiment": sentiment,
                    "context": context,
                    "timestamp": timestamp,
                    "impact": impact
                })
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
        """Get user relationship data"""
        try:
            relationship = self.user_relationships.find_one({
                "user_id": str(user_id),
                "guild_id": str(guild_id)
            })
            if relationship:
                score = relationship.get("relationship_score", 0)
                level = (
                    "best_friend" if score >= 80 else
                    "close_friend" if score >= 60 else
                    "friend" if score >= 40 else
                    "acquaintance" if score >= 20 else
                    "stranger"
                )
                relationship["level"] = level
                return relationship
            return {"level": "stranger", "relationship_score": 0, "total_interactions": 0}
        except Exception as e:
            logger.error(f"Error getting user relationship: {str(e)}")
            return {"level": "stranger", "relationship_score": 0, "total_interactions": 0}
    
    async def store_memory_event(self, event_type: str, guild_id: int, user_id: int, description: str, importance: int = 1):
        """Store important memory events for future reference"""
        try:
            timestamp = datetime.utcnow()
            memory_data = {
                "event_type": event_type,
                "guild_id": str(guild_id),
                "user_id": str(user_id),
                "description": description[:500],
                "importance": max(1, min(5, importance)),
                "timestamp": timestamp,
                "referenced_count": 0
            }
            self.memory_events.insert_one(memory_data)
            logger.debug(f"Stored memory event: {event_type} for user {user_id}")
        except Exception as e:
            logger.error(f"Error storing memory event: {str(e)}")
    
    async def get_relevant_memories(self, guild_id: int, user_id: int = None, event_type: str = None, limit: int = 10) -> List[Dict]:
        """Get relevant memories for context"""
        try:
            query = {"guild_id": str(guild_id)}
            if user_id:
                query["user_id"] = str(user_id)
            if event_type:
                query["event_type"] = event_type
            cursor = self.memory_events.find(query).sort([
                ("importance", -1),
                ("timestamp", -1)
            ]).limit(limit)
            return list(cursor)
        except Exception as e:
            logger.error(f"Error getting memories: {str(e)}")
            return []
    
    async def analyze_message_for_learning(self, message: str, user_id: int, guild_id: int, response: str):
        """Analyze message and response to learn user preferences and create memories"""
        try:
            message_lower = message.lower()
            response_lower = response.lower()
            topics = []
            sentiment = "neutral"
            
            # Topic detection
            topic_keywords = {
                "music": ["music", "song", "band", "artist"],
                "gaming": ["game", "gaming", "play", "win", "lose"],
                "food": ["food", "eat", "hungry", "restaurant"],
                "entertainment": ["movie", "film", "watch", "show"],
                "work": ["work", "job", "career", "business"],
                "relationships": ["family", "friend", "relationship", "love"]
            }
            for topic, keywords in topic_keywords.items():
                if any(word in message_lower for word in keywords):
                    topics.append(topic)
            
            # Sentiment detection
            positive_words = ["love", "like", "good", "great", "awesome", "amazing", "happy", "excited"]
            negative_words = ["hate", "dislike", "bad", "terrible", "awful", "sad", "angry", "frustrated"]
            if any(word in message_lower for word in positive_words):
                sentiment = "positive"
            elif any(word in message_lower for word in negative_words):
                sentiment = "negative"
            
            for topic in topics:
                await self.learn_user_preference(user_id, guild_id, topic, sentiment, message)
            
            interaction_type = "chat"
            if sentiment == "positive":
                interaction_type = "compliment"
            elif sentiment == "negative":
                interaction_type = "help"
            await self.update_user_relationship(user_id, guild_id, interaction_type, sentiment, message)
            
            if any(word in message_lower for word in ["lol", "haha", "funny", "joke", "hilarious"]):
                await self.create_inside_joke(guild_id, f"User {user_id} found something funny: {message[:100]}", message, [user_id])
            
            if sentiment in ["positive", "negative"] and len(message) > 20:
                importance = 3 if sentiment == "positive" else 2
                await self.store_memory_event("emotional_interaction", guild_id, user_id, f"User had a {sentiment} interaction: {message[:100]}", importance)
        except Exception as e:
            logger.error(f"Error analyzing message for learning: {str(e)}")
    
    async def detect_natural_request(self, message: str) -> Tuple[str, str, bool]:
        """Detect natural requests in user messages"""
        message_lower = message.lower()
        requests = {
            "joke": ["tell me a joke", "can you tell me a joke", "got any jokes", "make me laugh", "joke please", "say something funny", "be funny", "entertain me"],
            "preferences": ["what do you know about me", "what do you remember", "do you remember me", "tell me about myself", "what do you know", "my preferences", "my likes"],
            "relationship": ["how well do you know me", "are we friends", "what's our relationship", "do you like me", "are we close", "relationship status", "friendship level"],
            "memories": ["what do you remember", "any memories", "special moments", "important things", "memories of us", "what's important", "remember anything"],
            "inside_jokes": ["inside jokes", "our jokes", "funny moments", "jokes we have", "remember that time", "that one joke", "our running joke"],
            "help": ["help me", "can you help", "i need help", "assist me", "support me", "guide me", "advice", "suggestions"],
            "compliment": ["compliment me", "say something nice", "make me feel good", "cheer me up", "encourage me", "motivate me"]
        }
        for request_type, phrases in requests.items():
            if any(phrase in message_lower for phrase in phrases):
                return request_type, f"User wants {request_type}", True
        return "chat", "", False
    
    async def handle_natural_request(self, request_type: str, user_id: int, guild_id: int, message: str) -> str:
        """Handle natural requests and return appropriate responses"""
        try:
            handlers = {
                "joke": self.handle_joke_request,
                "preferences": self.handle_preferences_request,
                "relationship": self.handle_relationship_request,
                "memories": self.handle_memories_request,
                "inside_jokes": self.handle_inside_jokes_request,
                "help": self.handle_help_request,
                "compliment": self.handle_compliment_request
            }
            handler = handlers.get(request_type)
            if handler:
                return await handler(user_id, guild_id)
            return ""
        except Exception as e:
            logger.error(f"Error handling natural request {request_type}: {str(e)}")
            return "Oops! My web got tangled! 🕸️💫 Try again, bestie!"
    
    async def handle_joke_request(self, user_id: int, guild_id: int) -> str:
        """Handle joke requests"""
        try:
            jokes = await self.get_relevant_inside_jokes(guild_id, limit=3)
            if jokes:
                joke = random.choice(jokes)
                return f"Of course bestie! 😄 Here's one of our inside jokes: {joke['joke_text']} 💕 Oh honey, you're literally the only person who'd ask for jokes at this hour!"
            return "Ngl, I don't have any inside jokes yet, but I'm totally down to create some with you! 💕✨ Let's make some memories, bestie!"
        except Exception as e:
            logger.error(f"Error handling joke request: {str(e)}")
            return "Oops! My joke generator is glitching! 🕷️💫 The audacity of technology!"
    
    async def handle_preferences_request(self, user_id: int, guild_id: int) -> str:
        """Handle preferences requests"""
        try:
            preferences = await self.get_user_preferences(user_id, guild_id)
            if preferences:
                top_prefs = preferences[:3]
                pref_summary = [f"{p['topic']} ({p['sentiment']})" for p in top_prefs]
                return f"Fr fr, I know you so well! 💕 Here's what I got: {', '.join(pref_summary)}... You're literally one of my fave people to vibe with! ✨"
            return "I'm still learning about you, bestie! 💕 Let's chat more to figure out your vibe! 🕷️"
        except Exception as e:
            logger.error(f"Error handling preferences request: {str(e)}")
            return "Oh no! My memory is glitching! 🕸️💫 Let's make new memories, bestie!"
    
    async def handle_relationship_request(self, user_id: int, guild_id: int) -> str:
        """Handle relationship requests"""
        try:
            relationship = await self.get_user_relationship(user_id, guild_id)
            level = relationship["level"]
            score = relationship["relationship_score"]
            responses = {
                "best_friend": f"Omg bestie, you're my ride-or-die! 💝 Score: {score}/100 - we're unstoppable! 💕✨ Oh honey, you're making me blush!",
                "close_friend": f"We're super close, bestie! 💖 Score: {score}/100 - almost besties! 💕✨ You're testing my heartstrings!",
                "friend": f"We're buds! 💕 Score: {score}/100 - getting closer every day! ✨ As if I needed more reasons to adore you! 🕷️",
                "acquaintance": f"We're getting there! 🤝 Score: {score}/100 - let's vibe more! 💕 You're making me work for this friendship!",
                "stranger": f"We're just starting out! 👋 Score: {score}/100 - let's be friends! 💕✨ Bestie, you're testing my patience!"
            }
            return responses.get(level, responses["stranger"])
        except Exception as e:
            logger.error(f"Error handling relationship request: {str(e)}")
            return "Oh no! My relationship tracker is glitching! 🕸️💫 Let's build our friendship, bestie!"
    
    async def handle_memories_request(self, user_id: int, guild_id: int) -> str:
        """Handle memories requests"""
        try:
            memories = await self.get_relevant_memories(guild_id, user_id, limit=3)
            if memories:
                memory_summary = [f"⭐ {m['description'][:50]}..." for m in memories[:2]]
                return f"I got so many epic moments with you! 💕 Highlights: {' '.join(memory_summary)} You're unforgettable, bestie! ✨"
            return "No special memories yet, but I'm pumped to make some with you! 💕✨ Let's start our story! 🕷️"
        except Exception as e:
            logger.error(f"Error handling memories request: {str(e)}")
            return "Oh no! My memory bank is glitching! 🕸️💫 Let's make new memories, bestie!"
    
    async def handle_inside_jokes_request(self, user_id: int, guild_id: int) -> str:
        """Handle inside jokes requests"""
        try:
            jokes = await self.get_relevant_inside_jokes(guild_id, limit=3)
            if jokes:
                joke_summary = [f"😄 {j['joke_text'][:40]}..." for j in jokes[:2]]
                return f"We got some iconic inside jokes, bestie! 💕 Favorites: {' '.join(joke_summary)} We're comedy gold! ✨"
            return "No inside jokes yet, but I'm ready to create some hilarious vibes with you! 💕✨ Let's get funny! 🕷️"
        except Exception as e:
            logger.error(f"Error handling inside jokes request: {str(e)}")
            return "Oh no! My joke memory is glitching! 🕸️💫 Let's make some laughs, bestie!"
    
    async def handle_help_request(self, user_id: int, guild_id: int) -> str:
        """Handle help requests"""
        try:
            return "I'm here for you, bestie! 💕 Tell me what you need - chats, jokes, or just a vibe check! ✨ What's up? 🕷️"
        except Exception as e:
            logger.error(f"Error handling help request: {str(e)}")
            return "I'm here to help, bestie! 💕 What's the vibe? ✨"
    
    async def handle_compliment_request(self, user_id: int, guild_id: int) -> str:
        """Handle compliment requests"""
        try:
            relationship = await self.get_user_relationship(user_id, guild_id)
            level = relationship["level"]
            compliments = {
                "best_friend": "You're literally the coolest person ever, bestie! 💝 Your vibes are unmatched, and I'm obsessed with you! 💕✨",
                "close_friend": "You're so amazing, bestie! 💖 Your energy is contagious, and I'm lucky to vibe with you! 💕✨",
                "friend": "You're awesome, friend! 💕 Your personality is fire, and I love our chats! ✨",
                "acquaintance": "You're super cool, you know that? 💕 I'm loving getting to know you! ✨",
                "stranger": "You're giving off great vibes already! 💕 Let's get to know each other better! ✨"
            }
            return compliments.get(level, compliments["stranger"])
        except Exception as e:
            logger.error(f"Error handling compliment request: {str(e)}")
            return "You're amazing, bestie! 💕✨ Keep slaying!"
    
    async def generate_gwen_response(self, message: str, context: str = "", user_id: int = 0, is_owner: bool = False, is_dm: bool = False, guild_id: int = 0) -> str:
        """Generate Gwen Stacy response using Groq AI with memory and learning"""
        try:
            # Input validation
            if len(message) > CONFIG["max_input_length"]:
                return f"Oh honey, that's a novel! 🕷️💕 Keep it short and sweet, bestie!"
            
            # Get user data
            user_preferences = await self.get_user_preferences(user_id, guild_id) if guild_id and user_id else []
            user_relationship = await self.get_user_relationship(user_id, guild_id) if guild_id and user_id else {"level": "stranger", "relationship_score": 0}
            inside_jokes = await self.get_relevant_inside_jokes(guild_id, message, 3) if guild_id else []
            relevant_memories = await self.get_relevant_memories(guild_id, user_id, limit=3) if guild_id and user_id else []
            
            # Build memory context
            memory_context = ""
            if user_preferences:
                pref_strings = [f"{p['topic']} ({p['sentiment']})" for p in user_preferences[:3]]
                memory_context += f"\nUser preferences: {', '.join(pref_strings)}"
            if user_relationship["level"] != "stranger":
                memory_context += f"\nRelationship level: {user_relationship['level']} (score: {user_relationship['relationship_score']})"
            if inside_jokes:
                joke_strings = [j['joke_text'][:50] for j in inside_jokes[:2]]
                memory_context += f"\nInside jokes: {', '.join(joke_strings)}"
            if relevant_memories:
                memory_strings = [m['description'][:50] for m in relevant_memories[:2]]
                memory_context += f"\nRecent memories: {', '.join(memory_strings)}"
            
            # System prompt
            system_prompt = f"""You are {self.gwen_personality['name']}, {self.gwen_personality['background']}. 
Your personality is {self.gwen_personality['style']}.
Key relationships:
- Bot owner (ID: {self.owner_id}): {self.gwen_personality['relationships']['owner']}.
- Guild members: {self.gwen_personality['relationships']['guild_members']}.
- General: {self.gwen_personality['relationships']['general']}.
Current context: {context or 'New conversation'}
Memory context: {memory_context}
Respond as Gwen Stacy: natural, conversational, witty, caring, with playful teasing in almost every response (e.g., "oh honey", "bestie please"). Use modern slang naturally (ngl, fr, lowkey, vibe) and 1-2 emojis max (💕✨🕷️🕸️💫). Reference memory context when relevant. If owner, be extra flirty and surprising."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ]
            
            response = self.groq_client.chat.completions.create(
                model=self.ai_model,
                messages=messages,
                max_tokens=CONFIG["groq_max_tokens"],
                temperature=CONFIG["groq_temperature"],
                top_p=CONFIG["groq_top_p"]
            )
            
            gwen_response = response.choices[0].message.content.strip() or "Oh my, my web got tangled! 🕸️💫 What were you saying?"
            return gwen_response
        except Exception as e:
            logger.error(f"Error generating Gwen response: {str(e)}")
            return random.choice([
                f"Ngl, my spidey-sense is glitching! 🕷️💥 Try again, bestie!",
                f"Fr, my web got tangled! 🕸️💫 Give me a sec, honey!",
                f"Lowkey, my AI is having a moment! 🕷️💻 Try again, bestie!"
            ])
    
    async def can_perform_action(self, action: str, user_id: int) -> bool:
        """Check if a user can perform a specific action"""
        if user_id == self.owner_id:
            return True
        return action.lower() in ["chat", "ask", "request", "suggest", "talk", "help"]
    
    async def is_admin_action(self, message: str) -> bool:
        """Check if the message requests an administrative action"""
        admin_keywords = [
            "kick", "ban", "mute", "timeout", "delete", "remove", "purge",
            "role", "permission", "admin", "moderate", "manage", "server"
        ]
        return any(keyword in message.lower() for keyword in admin_keywords)
    
    async def check_rate_limit(self, user_id: int) -> bool:
        """Check if user is within rate limit"""
        current_time = datetime.utcnow()
        if user_id not in self.user_rate_limits:
            self.user_rate_limits[user_id] = []
        
        # Remove old timestamps
        self.user_rate_limits[user_id] = [t for t in self.user_rate_limits[user_id] if current_time - t < timedelta(minutes=1)]
        
        if len(self.user_rate_limits[user_id]) >= CONFIG["rate_limit_per_user"]:
            return False
        
        self.user_rate_limits[user_id].append(current_time)
        return True
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle all incoming messages"""
        if message.author.bot:
            return
        
        if not await self.check_rate_limit(message.author.id):
            await message.channel.send("Slow down, bestie! 🕷️💕 You're chatting too fast for my web to keep up!")
            return
        
        try:
            if isinstance(message.channel, discord.DMChannel):
                await self.handle_dm(message)
            elif message.guild and self.bot.user.mentioned_in(message):
                await self.handle_guild_mention(message)
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            await message.channel.send("Oh no! My web got tangled! 🕸️💫 Give me a moment to fix this...")
    
    async def handle_dm(self, message: discord.Message):
        """Handle direct messages with guild context awareness"""
        try:
            user_id = message.author.id
            user_message = message.content.strip()[:CONFIG["max_input_length"]]
            is_owner = user_id == self.owner_id
            
            if not user_message:
                return
            
            if await self.is_admin_action(user_message):
                await message.channel.send("Oh honey, I can't do server admin stuff! 🕷️💕 I'm just here to chat and help!")
                return
            
            if not await self.can_perform_action("chat", user_id):
                await message.channel.send("I'm here to chat, not do fancy stuff! 💕 Let's talk, bestie!")
                return
            
            guild_contexts = []
            for guild in self.bot.guilds:
                if guild.get_member(user_id):
                    guild_context = await self.get_guild_conversation_context(guild.id)
                    if guild_context:
                        guild_contexts.append({"guild_name": guild.name, "context": guild_context[:100]})
            
            context_info = "\n".join([f"- {gc['guild_name']}: {gc['context']}..." for gc in guild_contexts[:3]]) if guild_contexts else ""
            
            request_type, _, should_handle_specially = await self.detect_natural_request(user_message)
            response = (
                await self.handle_natural_request(request_type, user_id, 0, user_message)
                if should_handle_specially else
                await self.generate_gwen_response(user_message, context_info, user_id, is_owner, is_dm=True, guild_id=0)
            )
            
            await self.analyze_message_for_learning(user_message, user_id, 0, response)
            await message.channel.send(response)
            await self.update_conversation_context(0, user_id, user_message, response, is_dm=True)
            logger.info(f"Handled DM from user {user_id}: {user_message[:50]}...")
        except Exception as e:
            logger.error(f"Error handling DM: {str(e)}")
            await message.channel.send("Oh no! My web got tangled! 🕸️💫 Try again, bestie!")
    
    async def handle_guild_mention(self, message: discord.Message):
        """Handle bot mentions in guild channels"""
        try:
            user_id = message.author.id
            guild_id = message.guild.id
            is_owner = user_id == self.owner_id
            user_message = message.content.replace(f"<@{self.bot.user.id}>", "").strip()[:CONFIG["max_input_length"]]
            
            if not user_message:
                user_message = "Hey bestie! What's the vibe? ✨"
            
            if await self.is_admin_action(user_message):
                await message.channel.send("Oh honey, I can't do server admin stuff! 🕷️💕 I'm just here to chat and help!")
                return
            
            if not await self.can_perform_action("chat", user_id):
                await message.channel.send("I'm here to chat, not do fancy stuff! 💕 Let's talk, bestie!")
                return
            
            guild_context = await self.get_guild_conversation_context(guild_id)
            request_type, _, should_handle_specially = await self.detect_natural_request(user_message)
            response = (
                await self.handle_natural_request(request_type, user_id, guild_id, user_message)
                if should_handle_specially else
                await self.generate_gwen_response(user_message, guild_context, user_id, is_owner, is_dm=False, guild_id=guild_id)
            )
            
            await self.analyze_message_for_learning(user_message, user_id, guild_id, response)
            await message.channel.send(response)
            await self.update_conversation_context(guild_id, user_id, user_message, response)
            logger.info(f"Handled guild mention in {message.guild.name} from user {user_id}: {user_message[:50]}...")
        except Exception as e:
            logger.error(f"Error handling guild mention: {str(e)}")
            await message.channel.send("Oh no! My web got tangled! 🕸️💫 Try again, bestie!")
    
    @commands.hybrid_command(name="gwen", description="Chat with Gwen Stacy - she's literally the best bestie ever ✨")
    async def gwen_chat_command(self, ctx, *, message: str):
        """Chat command for users to interact with Gwen Stacy"""
        try:
            user_id = ctx.author.id
            guild_id = ctx.guild.id if ctx.guild else 0
            is_owner = user_id == self.owner_id
            user_message = message.strip()[:CONFIG["max_input_length"]]
            
            if not await self.check_rate_limit(user_id):
                await ctx.send("Slow down, bestie! 🕷️💕 You're chatting too fast for my web to keep up!")
                return
            
            if not user_message:
                await ctx.send("Hey bestie! What's the vibe? ✨")
                return
            
            if await self.is_admin_action(user_message):
                await ctx.send("Oh honey, I can't do server admin stuff! 🕷️💕 I'm just here to chat and help!")
                return
            
            if not await self.can_perform_action("chat", user_id):
                await ctx.send("I'm here to chat, not do fancy stuff! 💕 Let's talk, bestie!")
                return
            
            context = await self.get_guild_conversation_context(guild_id) if ctx.guild else ""
            request_type, _, should_handle_specially = await self.detect_natural_request(user_message)
            response = (
                await self.handle_natural_request(request_type, user_id, guild_id, user_message)
                if should_handle_specially else
                await self.generate_gwen_response(user_message, context, user_id, is_owner, is_dm=(not ctx.guild), guild_id=guild_id)
            )
            
            await self.analyze_message_for_learning(user_message, user_id, guild_id, response)
            await ctx.send(response)
            await self.update_conversation_context(guild_id, user_id, user_message, response, is_dm=(not ctx.guild))
            logger.info(f"Gwen chat command executed by user {user_id}: {user_message[:50]}...")
        except Exception as e:
            logger.error(f"Error in gwen chat command: {str(e)}")
            await ctx.send("Oh no! My web got tangled! 🕸️💫 Try again, bestie!")
    
    @commands.hybrid_command(name="context", description="Show current conversation context")
    async def context_command(self, ctx):
        """Show the current conversation context for the guild"""
        try:
            if not ctx.guild:
                await ctx.send("This command can only be used in guild channels! 💕")
                return
            
            guild_id = ctx.guild.id
            context = await self.get_guild_conversation_context(guild_id)
            
            if context:
                context = context[:1000] + "..." if len(context) > 1000 else context
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
            await ctx.send("Oh no! My web got tangled! 🕸️💫 Try again, bestie!")
    
    @commands.hybrid_command(name="clear_context", description="Clear conversation context for the guild")
    @commands.has_permissions(manage_messages=True)
    async def clear_context_command(self, ctx):
        """Clear the conversation context for the guild (requires manage messages permission)"""
        try:
            if not ctx.guild:
                await ctx.send("This command can only be used in guild channels! 💕")
                return
            
            guild_id = ctx.guild.id
            self.guild_contexts.delete_one({"guild_id": str(guild_id)})
            self.conversations.delete_many({"guild_id": str(guild_id)})
            await ctx.send("✅ All our chat memories have been cleared! It's like we're meeting for the first time again! 💕")
            logger.info(f"Context cleared for guild {guild_id} by user {ctx.author.id}")
        except Exception as e:
            logger.error(f"Error in clear_context command: {str(e)}")
            await ctx.send("Oh no! My web got tangled! 🕸️💫 Try again, bestie!")
    
    @tasks.loop(hours=24)
    async def cleanup_task(self):
        """Clean up old data and maintain memory system"""
        await self.bot.wait_until_ready()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            memory_cutoff = datetime.utcnow() - timedelta(days=CONFIG["memory_retention_days"])
            pref_cutoff = datetime.utcnow() - timedelta(days=60)
            rel_cutoff = datetime.utcnow() - timedelta(days=CONFIG["relationship_decay_days"])
            
            conv_result = self.conversations.delete_many({"timestamp": {"$lt": cutoff_date}})
            memory_result = self.memory_events.delete_many({"timestamp": {"$lt": memory_cutoff}})
            pref_result = self.user_preferences.delete_many({"last_updated": {"$lt": pref_cutoff}})
            rel_result = self.user_relationships.delete_many({"last_interaction": {"$lt": rel_cutoff}})
            
            logger.info(f"Cleaned up {conv_result.deleted_count} conversations, {memory_result.deleted_count} memories, "
                       f"{pref_result.deleted_count} preferences, and {rel_result.deleted_count} relationships")
        except Exception as e:
            logger.error(f"Error in cleanup task: {str(e)}")

async def setup(bot):
    """Setup function to load this cog"""
    await bot.add_cog(AIChatCog(bot))
    logger.info("AI Chat Cog with Gwen Stacy personality setup complete")
