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
        logger.error(f"Error getting guild config for {guild_id}: {str(e)}")
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
        logger.error(f"Error updating guild config for {guild_id}: {str(e)}")
        return False
