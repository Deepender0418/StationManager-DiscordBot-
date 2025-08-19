#!/usr/bin/env python3
"""
Database Utility Module

This module provides database utility functions for the Discord bot.
It contains helper functions for common database operations,
particularly for retrieving guild configurations and handling
database queries efficiently.

The module is designed to work with MongoDB collections and provides
a consistent interface for database operations across the bot.
"""

import logging

logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE UTILITY FUNCTIONS SECTION
# ============================================================================

async def get_guild_config(guild_configs_collection, guild_id: str):
    """
    Retrieve guild configuration from the database
    
    This function fetches the configuration settings for a specific guild
    from the MongoDB collection. It's used throughout the bot to get
    channel configurations, welcome messages, and other guild-specific settings.
    
    Args:
        guild_configs_collection: MongoDB collection containing guild configs
        guild_id: The Discord guild ID as a string
        
    Returns:
        dict: Guild configuration dictionary, or None if not found
        
    Example:
        config = await get_guild_config(bot.guild_configs, "123456789")
        if config:
            welcome_channel = config.get('welcome_channel_id')
    """
    try:
        # Query the database for the guild configuration
        # The guild_id is stored as a string in the database for consistency
        config = await guild_configs_collection.find_one({"guild_id": guild_id})
        
        if config:
            logger.debug(f"Retrieved config for guild {guild_id}")
            return config
        else:
            logger.debug(f"No config found for guild {guild_id}")
            return None
            
    except Exception as e:
        # Log database errors but don't crash the bot
        logger.error(f"Error retrieving config for guild {guild_id}: {str(e)}")
        return None

async def update_guild_config(collection, guild_id: str, updates: dict) -> bool:
    """Update guild configuration"""
    try:
        # Filter out None values
        filtered_updates = {k: v for k, v in updates.items() if v is not None}
        
        if not filtered_updates:
            return True
        
        result = await collection.update_one(
            {"guild_id": guild_id},
            {"$set": filtered_updates},
            upsert=True
        )
        
        return result.acknowledged
    except Exception as e:
        error_msg = str(e)
        if "Cannot use MongoClient after close" in error_msg:
            logger.error(f"MongoDB connection closed while updating guild config for {guild_id}. This may be due to a temporary disconnect.")
        else:
            logger.error(f"Error updating guild config for {guild_id}: {error_msg}")
        return False
