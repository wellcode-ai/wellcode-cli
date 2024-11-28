from datetime import date, datetime, timezone


def ensure_datetime(dt) -> datetime:
    """Ensure datetime has timezone information"""
    if dt is None:
        return None

    # If it's already a datetime
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    # If it's a string or date, convert to datetime
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    elif isinstance(dt, date):
        dt = datetime.combine(dt, datetime.min.time())

    # Ensure timezone
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt
