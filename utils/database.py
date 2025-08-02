import logging

logger = logging.getLogger(__name__)

async def get_guild_config(collection, guild_id):
    try:
        return await collection.find_one({"guild_id": guild_id})
    except Exception as e:
        logger.error(f"Error getting guild config for {guild_id}: {str(e)}")
        return None
    
async def get_guild_members(guild):
    """Get all members in a guild"""
    return [{"id": str(m.id), "name": m.name} for m in guild.members]

async def update_guild_config(collection, guild_id, updates):
    try:
        result = await collection.update_one(
            {"guild_id": guild_id},
            {"$set": updates},
            upsert=True
        )
        return result.acknowledged
    except Exception as e:
        logger.error(f"Error updating guild config for {guild_id}: {str(e)}")
        return False