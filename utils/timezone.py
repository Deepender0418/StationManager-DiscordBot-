#!/usr/bin/env python3
"""
Timezone utilities for Discord bot
"""

from datetime import datetime, timedelta, timezone

# Simple IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def get_current_time():
    """Get current time in IST"""
    return datetime.now(IST)

def format_time(dt):
    """Format datetime for display"""
    return dt.strftime("%Y-%m-%d %H:%M:%S IST")
