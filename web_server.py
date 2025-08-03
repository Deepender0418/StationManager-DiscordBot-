#!/usr/bin/env python3
"""
Web Server - Flask interface for bot management
"""

import os
import asyncio
import logging
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from utils.database import get_guild_config, update_guild_config

logger = logging.getLogger(__name__)

def create_app(bot):
    """Create Flask application"""
    app = Flask(__name__)
    app.secret_key = os.getenv('ADMIN_SECRET', 'default-secret')
    app.bot = bot
    
    def run_async(coro):
        """Run async function in bot's event loop"""
        try:
            # Try to use bot's event loop first
            if hasattr(bot, 'loop') and bot.loop and not bot.loop.is_closed():
                if bot.loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(coro, bot.loop)
                    return future.result(timeout=30)
                else:
                    return asyncio.run(coro)
            else:
                # Create a new event loop for this thread
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    return loop.run_until_complete(coro)
                except RuntimeError:
                    # No event loop in current thread, create one
                    return asyncio.run(coro)
        except Exception as e:
            logger.error(f"Async error: {str(e)}")
            return None
    
    @app.route('/')
    def home():
        """Home page"""
        return "Discord Bot is Alive! 🚀"
    
    @app.route('/config/<guild_id>', methods=['GET', 'POST'])
    def guild_config(guild_id):
        """Server configuration page"""
        if request.method == 'POST':
            updates = {
                "welcome_channel_id": request.form.get('welcome_channel'),
                "log_channel_id": request.form.get('log_channel'),
                "announcement_channel_id": request.form.get('announcement_channel')
            }
            
            success = run_async(update_guild_config(bot.guild_configs, guild_id, updates))
            
            if success:
                flash('Configuration updated successfully!', 'success')
            else:
                flash('Failed to update configuration', 'error')
                
            return redirect(url_for('guild_config', guild_id=guild_id))
        
        config = run_async(get_guild_config(bot.guild_configs, guild_id))
        guild = bot.get_guild(int(guild_id)) if bot.is_ready() else None
        channels = [{"id": str(c.id), "name": c.name} for c in guild.text_channels] if guild else []
        
        return render_template('config.html', 
                             guild_id=guild_id,
                             guild_name=guild.name if guild else "Unknown Server",
                             config=config,
                             channels=channels)
    
    @app.route('/birthdays/<guild_id>')
    def manage_birthdays(guild_id):
        """Birthday management page"""
        try:
            config = run_async(get_guild_config(bot.guild_configs, str(guild_id)))
            guild = bot.get_guild(int(guild_id)) if bot.is_ready() else None
            members = [{"id": str(m.id), "name": m.display_name} for m in guild.members] if guild else []
            
            # Get birthdays
            async def fetch_birthdays():
                cursor = bot.birthdays.find({"guild_id": int(guild_id)})
                return await cursor.to_list(length=None)
            
            birthdays = run_async(fetch_birthdays()) or []
            
            for bday in birthdays:
                bday["_id"] = str(bday["_id"])
                bday["custom_message"] = bday.get("custom_message", "")
                
            return render_template('birthdays.html', 
                                guild_id=guild_id,
                                guild_name=guild.name if guild else "Unknown Server",
                                config=config,
                                members=members,
                                birthdays=birthdays)
        except Exception as e:
            logger.error(f"Error in manage_birthdays: {str(e)}")
            return f"Error: {str(e)}", 500
    
    @app.route('/api/birthday', methods=['POST'])
    def api_set_birthday():
        """API endpoint to set birthday"""
        data = request.json
        guild_id = data.get('guild_id')
        user_id = data.get('user_id')
        date = data.get('date')
        custom_message = data.get('custom_message')
        
        if not all([guild_id, user_id, date]):
            return jsonify({"success": False, "error": "Missing parameters"}), 400
        
        try:
            month, day = map(int, date.split('-'))
            if month < 1 or month > 12 or day < 1 or day > 31:
                return jsonify({"success": False, "error": "Invalid date format"}), 400
                
            birthday = f"{month:02d}-{day:02d}"
            
            async def update_birthday():
                return await bot.birthdays.update_one(
                    {"user_id": int(user_id), "guild_id": int(guild_id)},
                    {"$set": {"birthday": birthday, "custom_message": custom_message}},
                    upsert=True
                )
            
            result = run_async(update_birthday())
            
            return jsonify({
                "success": True,
                "message": f"Birthday set to {date}",
                "data": {"user_id": user_id, "birthday": birthday, "custom_message": custom_message}
            })
        except Exception as e:
            logger.error(f"Error setting birthday: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/birthday', methods=['DELETE'])
    def api_delete_birthday():
        """API endpoint to delete birthday"""
        data = request.json
        guild_id = data.get('guild_id')
        user_id = data.get('user_id')
        
        if not all([guild_id, user_id]):
            return jsonify({"success": False, "error": "Missing parameters"}), 400
        
        try:
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
            logger.error(f"Error deleting birthday: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/birthday_message', methods=['POST'])
    def api_set_birthday_message():
        """API endpoint to set birthday message"""
        data = request.json
        guild_id = data.get('guild_id')
        message = data.get('message')
        
        if not guild_id or message is None:
            return jsonify({"success": False, "error": "Missing parameters"}), 400
        
        try:
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
            logger.error(f"Error updating birthday message: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500

    return app

def run_web_server(app):
    """Start the web server"""
    try:
        port = int(os.getenv('WEB_PORT', 8080))
        host = os.getenv('WEB_HOST', '0.0.0.0')
        logger.info(f"Starting Flask web server on {host}:{port}")
        app.run(host=host, port=port, threaded=True)
    except Exception as e:
        logger.error(f"Web server error: {str(e)}")
