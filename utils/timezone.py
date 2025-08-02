from datetime import datetime, timezone, timedelta

# Example for IST (India Standard Time)
class IST(datetime.tzinfo):
    def utcoffset(self, dt):
        return timedelta(hours=5, minutes=30)

    def dst(self, dt):
        return timedelta(0)

    def tzname(self, dt):
        return "IST"