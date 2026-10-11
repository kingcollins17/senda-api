from datetime import datetime
from zoneinfo import ZoneInfo

def now() -> datetime:
    """Returns the current time in the Africa/Lagos timezone as a naive datetime object."""
    dt = datetime.now(ZoneInfo("Africa/Lagos"))
    return dt.replace(tzinfo=None)
