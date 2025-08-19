#!/usr/bin/env python3
"""
Timezone Utility Module

This module provides timezone functionality for the Discord bot.
It defines the IST (Indian Standard Time) timezone that is used
throughout the application for consistent time handling.

The module uses pytz for timezone handling, which provides
reliable timezone calculations and daylight saving time support.
"""

import pytz

# ============================================================================
# TIMEZONE DEFINITIONS SECTION
# ============================================================================

# Define IST (Indian Standard Time) timezone
# This is used throughout the bot for consistent time handling
# IST is UTC+5:30 and doesn't observe daylight saving time
IST = pytz.timezone('Asia/Kolkata')

def get_current_time():
    """Get current time in IST"""
    return datetime.now(IST)

def format_time(dt):
    """Format datetime for display"""
    return dt.strftime("%Y-%m-%d %H:%M:%S IST")
