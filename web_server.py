from flask import Flask, render_template, request, redirect, url_for, jsonify
import asyncio
import os
import logging
from utils import database
from bson import ObjectId

logger = logging.getLogger(__name__)

def create_app(bot):
    app = Flask(__name__)
    app.secret_key = os.getenv('ADMIN_SECRET', 'default-secret')
    app.bot = bot
    
    # Improved bot loop handling
    def get_bot_loop():
        if hasattr(bot, 'loop') and bot.loop.is_running():
            return bot.loop
        return asyncio.new_event_loop()
    
    # Enhanced async runner
    def run_async(coro):
        loop = get_bot_loop()
        
        if loop.is_running():
            # Properly handle coroutine objects
            if asyncio.iscoroutine(coro):
                future = asyncio.run_coroutine_threadsafe(coro, loop)
                return future.result()
            else:
                raise TypeError("A coroutine object is required")
        else:
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
    
    @app.route('/')
    def home():
        return "Discord Bot is Alive!"
    
    @app.route('/config/<guild_id>', methods=['GET', 'POST'])
    def guild_config(guild_id):
        if request.method == 'POST':
            updates = {
                "welcome_channel_id": request.form.get('welcome_channel'),
                "log_channel_id": request.form.get('log_channel'),
                "announcement_channel_id": request.form.get('announcement_channel')
            }
            run_async(
                database.update_guild_config(bot.guild_configs, guild_id, updates)
            )
            return redirect(url_for('guild_config', guild_id=guild_id))
        
        config = run_async(
            database.get_guild_config(bot.guild_configs, guild_id)
        )
        guild = bot.get_guild(int(guild_id)) if bot.is_ready() else None
        channels = [{"id": str(c.id), "name": c.name} for c in guild.text_channels] if guild else []
        
        return render_template('config.html', 
                             guild_id=guild_id,
                             guild_name=guild.name if guild else "Unknown Server",
                             config=config,
                             channels=channels)
    
    @app.route('/birthdays/<guild_id>')
    def manage_birthdays(guild_id):
        try:
            # Get current config
            config = run_async(
                database.get_guild_config(bot.guild_configs, str(guild_id))
            )
            
            # Get guild information
            guild = None
            if bot.is_ready():
                guild = bot.get_guild(int(guild_id))
            
            # Get all members
            members = []
            if guild:
                members = [{"id": str(m.id), "name": m.display_name} for m in guild.members]
            
            # FIX: Properly handle Motor cursor
            async def fetch_birthdays():
                cursor = bot.birthdays.find({"guild_id": int(guild_id)})
                return await cursor.to_list(length=None)
        
            birthdays = run_async(fetch_birthdays())
            
            for bday in birthdays:
                bday["_id"] = str(bday["_id"])
                # Add custom_message if exists
                bday["custom_message"] = bday.get("custom_message", "")
                
            return render_template('birthdays.html', 
                                guild_id=guild_id,
                                guild_name=guild.name if guild else "Unknown Server",
                                config=config,
                                members=members,
                                birthdays=birthdays)
        except Exception as e:
            logger.error(f"Error in manage_birthdays: {str(e)}", exc_info=True)
            return f"Error: {str(e)}", 500
    
    @app.route('/api/birthday', methods=['POST'])
    def api_set_birthday():
        data = request.json
        guild_id = data.get('guild_id')
        user_id = data.get('user_id')
        date = data.get('date')
        custom_message = data.get('custom_message', None)  # New field
        
        if not all([guild_id, user_id, date]):
            return jsonify({"success": False, "error": "Missing parameters"}), 400
        
        try:
            month, day = map(int, date.split('-'))
            if month < 1 or month > 12 or day < 1 or day > 31:
                return jsonify({"success": False, "error": "Invalid date format"}), 400
                
            birthday = f"{month:02d}-{day:02d}"
            
            # Create update data with optional custom message
            update_data = {"birthday": birthday}
            if custom_message:
                update_data["custom_message"] = custom_message
            
            async def update_birthday():
                return await bot.birthdays.update_one(
                    {"user_id": int(user_id), "guild_id": int(guild_id)},
                    {"$set": update_data},
                    upsert=True
                )
            
            result = run_async(update_birthday())
            
            return jsonify({
                "success": True,
                "message": f"Birthday set to {date}" + (" with custom message" if custom_message else ""),
                "data": {
                    "user_id": user_id,
                    "birthday": birthday,
                    "custom_message": custom_message
                }
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/birthday', methods=['DELETE'])
    def api_delete_birthday():
        data = request.json
        guild_id = data.get('guild_id')
        user_id = data.get('user_id')
        
        if not all([guild_id, user_id]):
            return jsonify({"success": False, "error": "Missing parameters"}), 400
        
        try:
            # FIX: Proper async handling
            async def delete_birthday():
                return await bot.birthdays.delete_one(
                    {"user_id": int(user_id), "guild_id": int(guild_id)}
                )
            
            result = run_async(delete_birthday())
            
            if result.deleted_count > 0:
                return jsonify({"success": True, "message": "Birthday deleted"})
            else:
                return jsonify({"success": False, "error": "No record found"}), 404
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/birthday_message', methods=['POST'])
    def api_set_birthday_message():
        data = request.json
        guild_id = data.get('guild_id')
        message = data.get('message')
        
        if not guild_id or message is None:
            return jsonify({"success": False, "error": "Missing parameters"}), 400
        
        try:
            # FIX: Proper async handling
            async def update_message():
                return await bot.guild_configs.update_one(
                    {"guild_id": str(guild_id)},
                    {"$set": {"birthday_message": message}},
                    upsert=True
                )
            
            result = run_async(update_message())
            
            return jsonify({
                "success": True,
                "message": "Custom birthday message updated"
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    return app

def run_web_server(app):
    try:
        logger.info("Starting Flask web server on port 8080")
        app.run(host='0.0.0.0', port=8080)
    except Exception as e:
        logger.error(f"Web server error: {str(e)}")