#!/usr/bin/env python3
"""
Database utilities for Discord bot
"""

import logging

logger = logging.getLogger(__name__)

async def get_guild_config(collection, guild_id: str):
    """Get guild configuration"""
    try:
        return await collection.find_one({"guild_id": guild_id})
    except Exception as e:
        error_msg = str(e)
        if "Cannot use MongoClient after close" in error_msg:
            logger.error(f"MongoDB connection closed while getting guild config for {guild_id}. This may be due to a temporary disconnect.")
        else:
            logger.error(f"Error getting guild config for {guild_id}: {error_msg}")
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
