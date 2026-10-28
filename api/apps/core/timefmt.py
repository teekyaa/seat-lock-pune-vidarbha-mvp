from zoneinfo import ZoneInfo

from django.conf import settings

IST = ZoneInfo(settings.DISPLAY_TIME_ZONE)


def ist(dt):
    """Format a UTC datetime for people: 'Fri 31 Oct, 9:00 pm IST'. Never relative wording (hard rule 6)."""
    local = dt.astimezone(IST)
    return local.strftime("%a %d %b, %I:%M %p IST").replace(" 0", " ").replace("AM", "am").replace("PM", "pm")


def hours_between(later, earlier):
    return (later - earlier).total_seconds() / 3600
