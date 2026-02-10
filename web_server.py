#!/usr/bin/env python3
"""
Web Server Module - Flask Web Interface for Bot Management

This module provides a web interface for managing the Discord bot.
It includes functionality to:
- Serve a web dashboard for bot configuration
- Display bot status and information
- Manage guild configurations through a web interface
- View and edit birthday records
- Provide a user-friendly way to configure the bot

The web interface runs alongside the Discord bot and provides
an alternative way to manage bot settings without using Discord commands.
"""

import os
import asyncio
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from utils.database import get_guild_config, update_guild_config
from datetime import datetime, timedelta
from utils.timezone import IST

logger = logging.getLogger(__name__)

# ============================================================================
# SECURITY CONFIGURATION CONSTANTS
# ============================================================================
ASYNC_TIMEOUT_SECONDS = 30  # Timeout for async operations
LOGIN_RATE_LIMIT = "5 per minute"  # Max login attempts per minute
API_RATE_LIMIT = "30 per minute"  # Max API calls per minute

def create_app(bot):
    """
    Create and configure the Flask web application
    
    This function sets up the Flask app with all necessary routes,
    templates, and bot integration. The web interface provides
    a user-friendly way to manage bot configurations.
    
    Args:
        bot: The Discord bot instance to integrate with
        
    Returns:
        Flask: Configured Flask application
    """
    
    # ============================================================================
    # FLASK APP CONFIGURATION SECTION
    # ============================================================================
    
    # Create Flask application
    app = Flask(__name__)
    
    # SECURITY: Require ADMIN_SECRET to be set, no defaults
    admin_secret = os.getenv('ADMIN_SECRET')
    if not admin_secret:
        raise ValueError(
            "ADMIN_SECRET environment variable is required! "
            "Please set a strong password in your .env file."
        )
    
    app.secret_key = admin_secret  # Use admin secret as session key
    
    # Session lifetime (default: 1 day)
    try:
        session_minutes = int(os.getenv('WEB_SESSION_MINUTES', '1440'))
    except ValueError:
        session_minutes = 1440
    app.permanent_session_lifetime = timedelta(minutes=session_minutes)
    
    # Store bot instance for use in routes
    app.bot = bot
    
    # ============================================================================
    # SECURITY MIDDLEWARE SECTION
    # ============================================================================
    
    # Initialize rate limiter
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://"
    )
    
    # Initialize CSRF protection
    csrf = CSRFProtect(app)
    
    def run_async(coro):
        """Run async function in bot's event loop"""
        try:
            # Try to use bot's event loop first
            if hasattr(bot, 'loop') and bot.loop and not bot.loop.is_closed():
                if bot.loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(coro, bot.loop)
                    return future.result(timeout=ASYNC_TIMEOUT_SECONDS)
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
    
    # ============================================================================
    # ROUTE DEFINITIONS SECTION
    # ============================================================================

    @app.before_request
    def require_login():
        """Protect all routes with a simple admin login based on ADMIN_SECRET."""
        try:
            # Allow public assets and login route
            path = request.path or '/'
            if path.startswith('/static') or path.startswith('/favicon') or path == '/healthz':
                return None
            if path == '/login':
                return None

            # Header-based auth fallback (useful for reverse proxies)
            header_secret = request.headers.get('X-Admin-Secret')
            if header_secret and header_secret == admin_secret:
                session['auth'] = True
                session.permanent = True

            if not session.get('auth'):
                return redirect(url_for('login', next=path))
        except Exception as e:
            logger.error(f"Auth check error: {str(e)}")
            return redirect(url_for('login'))

    @app.route('/healthz')
    def healthz():
        """Public health endpoint for uptime pings/monitors."""
        try:
            return jsonify({
                'status': 'ok',
                'bot': 'online' if bot.is_ready() else 'offline',
                'guilds': len(bot.guilds)
            })
        except Exception:
            return jsonify({'status': 'error'}), 500

    @app.route('/login', methods=['GET', 'POST'])
    @limiter.limit(LOGIN_RATE_LIMIT)
    def login():
        """Simple password form to gate access to the dashboard with rate limiting."""
        try:
            if request.method == 'POST':
                provided = request.form.get('password', '')
                if provided and provided == admin_secret:
                    session['auth'] = True
                    session.permanent = True
                    dest = request.args.get('next') or url_for('index')
                    logger.info(f"Successful login from {get_remote_address()}")
                    return redirect(dest)
                else:
                    logger.warning(f"Failed login attempt from {get_remote_address()}")
                    flash('Invalid password', 'error')
            return render_template('login.html')
        except Exception as e:
            logger.error(f"Login error: {str(e)}", exc_info=True)
            return render_template('login.html'), 500

    @app.route('/logout')
    def logout():
        try:
            session.pop('auth', None)
            flash('You have been logged out', 'success')
        except Exception:
            pass
        return redirect(url_for('login'))
    
    @app.route('/')
    def index():
        """
        Main dashboard page
        
        This route displays the main dashboard with:
        - Bot status and information
        - Quick access to different sections
        - Overview of bot functionality
        
        Returns:
            str: Rendered HTML template
        """
        try:
            # Get bot information
            bot_info = {
                'name': bot.user.name if bot.user else 'Unknown',
                'guilds': len(bot.guilds),
                'status': 'Online' if bot.is_ready() else 'Offline',
                'uptime': get_bot_uptime()
            }

            # Build guild list
            guilds = []
            for guild in bot.guilds:
                guild_info = {
                    'id': str(guild.id),
                    'name': guild.name,
                    'member_count': guild.member_count,
                    'icon_url': str(guild.icon.url) if guild.icon else None
                }
                guilds.append(guild_info)
            
            return render_template('index.html', bot=bot_info, guilds=guilds)
            
        except Exception as e:
            logger.error(f"Error in index route: {str(e)}")
            return "Error loading dashboard", 500
    
    @app.route('/config')
    def config_page():
        """Redirect to home where guild selection is shown"""
        try:
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Error in config route: {str(e)}")
            return "Error loading configuration page", 500
    
    @app.route('/config/<guild_id>', methods=['GET', 'POST'])
    def guild_config(guild_id):
        """Server configuration page"""
        if request.method == 'POST':
            updates = {
                "welcome_channel_id": request.form.get('welcome_channel'),
                "log_channel_id": request.form.get('log_channel'),
                "announcement_channel_id": request.form.get('announcement_channel'),
                "birthday_channel_id": request.form.get('birthday_channel'),
                "events_channel_id": request.form.get('events_channel')
            }
            
            success = run_async(update_guild_config(bot.guild_configs, guild_id, updates))
            
            if success:
                flash('Configuration updated successfully!', 'success')
            else:
                flash('Failed to update configuration', 'error')
                
            return redirect(url_for('guild_config', guild_id=guild_id))
        
        config = run_async(get_guild_config(bot.guild_configs, guild_id))
        guild = None
        channels = []
        
        # Check if bot is ready and get guild info
        if hasattr(bot, 'is_ready') and bot.is_ready():
            try:
                guild = bot.get_guild(int(guild_id))
                if guild:
                    channels = [{"id": str(c.id), "name": c.name} for c in guild.text_channels]
            except (ValueError, AttributeError) as e:
                logger.error(f"Error getting guild info: {str(e)}")
        
        return render_template('config.html', 
                             guild_id=guild_id,
                             guild_name=guild.name if guild else "Unknown Server",
                             config=config,
                             channels=channels)
    
    @app.route('/birthdays')
    def birthdays_page():
        """
        Birthday management page
        
        This route displays the birthday management page where users can:
        - View all birthday records
        - Add new birthdays
        - Edit existing birthdays
        - Delete birthday records
        
        Returns:
            str: Rendered HTML template
        """
        try:
            # Get all guilds for selection
            guilds = []
            for guild in bot.guilds:
                guild_info = {
                    'id': guild.id,
                    'name': guild.name
                }
                guilds.append(guild_info)
            
            return render_template('birthdays.html', guilds=guilds)
            
        except Exception as e:
            logger.error(f"Error in birthdays route: {str(e)}")
            return "Error loading birthdays page", 500
    
    @app.route('/birthdays/<guild_id>')
    def manage_birthdays(guild_id):
        """Birthday management page"""
        try:
            config = run_async(get_guild_config(bot.guild_configs, str(guild_id)))
            
            # Get guild and members
            guild = None
            members = []
            
            # Get birthdays first to filter out members who already have birthdays
            async def fetch_birthdays():
                cursor = bot.birthdays.find({"guild_id": int(guild_id)})
                return await cursor.to_list(length=None)
            
            birthdays = run_async(fetch_birthdays()) or []
            existing_user_ids = {str(bday.get('user_id')) for bday in birthdays}
            
            # Check if bot is ready and get guild info
            if hasattr(bot, 'is_ready') and bot.is_ready():
                guild = bot.get_guild(int(guild_id))
                
                if guild:
                    # Get all members, excluding bots and those with existing birthdays
                    # Limit to 100 members for performance (lazy loading)
                    for member in guild.members:
                        if not member.bot and str(member.id) not in existing_user_ids:
                            members.append({
                                'id': str(member.id),
                                'name': member.display_name
                            })
                            
                            # Limit to 100 for performance
                            if len(members) >= 100:
                                break
                    
                    # Sort members alphabetically
                    members.sort(key=lambda x: x['name'].lower())
                    
                    # Populate names for existing birthdays efficiently
                    for bday in birthdays:
                        member = guild.get_member(int(bday['user_id']))
                        if member:
                            bday['member_name'] = member.display_name
                            bday['member_avatar'] = member.avatar.url if member.avatar else member.default_avatar.url
                        else:
                            bday['member_name'] = "Unknown Member"
                            bday['member_avatar'] = None
                else:
                    logger.warning(f"Guild {guild_id} not found")
            
            # Format birthdays for template
            for bday in birthdays:
                bday["_id"] = str(bday["_id"])
                bday["custom_message"] = bday.get("custom_message") or ""
                if 'member_name' not in bday:
                     bday['member_name'] = "Unknown Member"

                
            return render_template('birthdays.html', 
                                guild_id=guild_id,
                                guild_name=guild.name if guild else "Unknown Server",
                                config=config,
                                members=members,
                                birthdays=birthdays,
                                total_members=len(guild.members) if guild else 0)
        except Exception as e:
            logger.error(f"Error in manage_birthdays: {str(e)}", exc_info=True)
            return f"Error: {str(e)}", 500
    
    # ============================================================================
    # API ROUTES SECTION
    # ============================================================================
    
    @app.route('/api/guilds')
    def api_guilds():
        """
        API endpoint to get guild information
        
        This endpoint provides JSON data about all guilds
        the bot is in, including member counts and icons.
        
        Returns:
            JSON: Guild information
        """
        try:
            guilds = []
            for guild in bot.guilds:
                guild_info = {
                    'id': str(guild.id),
                    'name': guild.name,
                    'member_count': guild.member_count,
                    'icon_url': str(guild.icon.url) if guild.icon else None
                }
                guilds.append(guild_info)
            
            return jsonify(guilds)
            
        except Exception as e:
            logger.error(f"Error in api_guilds: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/config/<guild_id>')
    def api_guild_config(guild_id):
        """
        API endpoint to get guild configuration
        
        This endpoint retrieves the configuration for a specific guild
        from the database and returns it as JSON.
        
        Args:
            guild_id: The Discord guild ID
            
        Returns:
            JSON: Guild configuration data
        """
        try:
            # Get guild configuration from database
            config = bot.guild_configs.find_one({"guild_id": str(guild_id)})
            
            if config:
                # Convert ObjectId to string for JSON serialization
                config['_id'] = str(config['_id'])
                return jsonify(config)
            else:
                return jsonify({})
                
        except Exception as e:
            logger.error(f"Error in api_guild_config: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/config/<guild_id>', methods=['POST'])
    def api_update_config(guild_id):
        """
        API endpoint to update guild configuration
        
        This endpoint updates the configuration for a specific guild
        in the database based on the provided JSON data.
        
        Args:
            guild_id: The Discord guild ID
            
        Returns:
            JSON: Success/error response
        """
        try:
            # Get JSON data from request
            data = request.get_json()
            
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Update configuration in database
            result = bot.guild_configs.update_one(
                {"guild_id": str(guild_id)},
                {"$set": data},
                upsert=True
            )
            
            if result.modified_count > 0 or result.upserted_id:
                return jsonify({'success': True, 'message': 'Configuration updated'})
            else:
                return jsonify({'error': 'No changes made'}), 400
                
        except Exception as e:
            logger.error(f"Error in api_update_config: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/birthdays/<guild_id>')
    def api_birthdays(guild_id):
        """
        API endpoint to get birthday records for a guild
        
        This endpoint retrieves all birthday records for a specific guild
        from the database and returns them as JSON.
        
        Args:
            guild_id: The Discord guild ID
            
        Returns:
            JSON: Birthday records
        """
        try:
            # Get birthday records from database
            cursor = bot.birthdays.find({"guild_id": int(guild_id)})
            birthdays = []
            
            async def get_birthdays():
                async for doc in cursor:
                    # Convert ObjectId to string for JSON serialization
                    doc['_id'] = str(doc['_id'])
                    birthdays.append(doc)
            
            # Note: This is a simplified version. In a real implementation,
            # you'd need to handle the async database operations properly
            return jsonify(birthdays)
            
        except Exception as e:
            logger.error(f"Error in api_birthdays: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/birthday', methods=['POST'])
    @limiter.limit(API_RATE_LIMIT)
    @csrf.exempt  # API endpoint, CSRF handled differently for APIs
    def api_set_birthday():
        """API endpoint to set birthday with input validation and rate limiting."""
        try:
            data = request.json
            if not data:
                return jsonify({"success": False, "error": "No data provided"}), 400
                
            guild_id = data.get('guild_id')
            user_id = data.get('user_id')
            date = data.get('date')
            custom_message = data.get('custom_message', '')
            
            # Validate required fields
            if not all([guild_id, user_id, date]):
                return jsonify({"success": False, "error": "Missing required parameters"}), 400
            
            # Validate and parse date
            try:
                month, day = map(int, date.split('-'))
                if month < 1 or month > 12 or day < 1 or day > 31:
                    return jsonify({"success": False, "error": "Invalid date: month must be 1-12, day must be 1-31"}), 400
            except (ValueError, AttributeError) as e:
                return jsonify({"success": False, "error": "Invalid date format. Use MM-DD"}), 400
            
            # Validate user_id and guild_id are numeric
            try:
                user_id_int = int(user_id)
                guild_id_int = int(guild_id)
            except (ValueError, TypeError):
                return jsonify({"success": False, "error": "Invalid user_id or guild_id"}), 400
            
            # Sanitize custom message (limit length)
            if 'custom_message' in data and data['custom_message']:
                custom_message = data['custom_message'].strip()
                if len(custom_message) > 500:
                    return jsonify({'error': 'Custom message too long (max 500 characters)'}), 400
            else:
                custom_message = None
                
            birthday = f"{month:02d}-{day:02d}"
            
            async def update_birthday():
                return await bot.birthdays.update_one(
                    {"user_id": user_id_int, "guild_id": guild_id_int},
                    {"$set": {"birthday": birthday, "custom_message": custom_message}},
                    upsert=True
                )
            
            result = run_async(update_birthday())
            
            if result:
                return jsonify({
                    "success": True,
                    "message": f"Birthday set to {date}",
                    "data": {"user_id": user_id, "birthday": birthday, "custom_message": custom_message}
                })
            else:
                return jsonify({"success": False, "error": "Database operation failed"}), 500
        except Exception as e:
            logger.error(f"Error setting birthday: {str(e)}", exc_info=True)
            return jsonify({"success": False, "error": "Internal server error"}), 500

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

    # ============================================================================
    # UTILITY FUNCTIONS SECTION
    # ============================================================================
    
    def get_bot_uptime():
        """
        Calculate bot uptime
        
        This function calculates how long the bot has been running
        since it was started.
        
        Returns:
            str: Formatted uptime string
        """
        try:
            # This would need to be implemented based on when the bot started
            # For now, return a placeholder
            return "Running"
        except Exception as e:
            logger.error(f"Error getting bot uptime: {str(e)}")
            return "Unknown"
    
    return app

def run_web_server(app):
    """
    Run the Flask web server using Waitress (production-ready)
    
    This function starts a production-ready WSGI server instead of Flask's
    development server. Waitress is more secure and performant for production use.
    
    Args:
        app: The Flask application to run
    """
    try:
        from waitress import serve
        
        port = int(os.getenv('WEB_PORT', 8080))
        host = os.getenv('WEB_HOST', '127.0.0.1')  # Default to localhost only
        
        logger.info("=" * 80)
        logger.info("🌐 STARTING WEB SERVER (PRODUCTION MODE)")
        logger.info("=" * 80)
        logger.info(f"Server: Waitress (Production WSGI)")
        logger.info(f"Host: {host}")
        logger.info(f"Port: {port}")
        logger.info(f"URL: http://{host}:{port}")
        logger.info("")
        
        if host == '0.0.0.0':
            logger.warning("⚠️  WARNING: Server is exposed to all network interfaces!")
            logger.warning("⚠️  This means the dashboard is accessible from other devices.")
            logger.warning("⚠️  For security, consider setting WEB_HOST=127.0.0.1 in .env")
            logger.warning("")
        else:
            logger.info("✅ Server is bound to localhost only (secure)")
            logger.info("")
        
        logger.info("=" * 80)
        
        # Start production server with security settings
        serve(
            app,
            host=host,
            port=port,
            threads=4,  # Number of worker threads
            channel_timeout=30,  # Timeout for requests
            cleanup_interval=30,  # Cleanup interval for idle connections
            asyncore_use_poll=True  # Use poll() instead of select() for better performance
        )
        
    except ImportError:
        logger.error("=" * 80)
        logger.error("❌ WAITRESS NOT INSTALLED")
        logger.error("=" * 80)
        logger.error("The production server (Waitress) is not installed.")
        logger.error("Please install dependencies: pip install -r requirements.txt")
        logger.error("")
        logger.error("Falling back to Flask development server (NOT FOR PRODUCTION!)")
        logger.error("=" * 80)
        
        # Fallback to Flask dev server
        port = int(os.getenv('WEB_PORT', 8080))
        host = os.getenv('WEB_HOST', '127.0.0.1')
        logger.info(f"Starting Flask development server on {host}:{port}")
        app.run(host=host, port=port, threaded=True, debug=False)
        
    except Exception as e:
        logger.error(f"❌ Web server error: {str(e)}", exc_info=True)
