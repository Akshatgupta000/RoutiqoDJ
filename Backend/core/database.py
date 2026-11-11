import datetime
from django.utils import timezone


def now_utc() -> datetime.datetime:
    """Returns the current UTC datetime."""
    return timezone.now()
