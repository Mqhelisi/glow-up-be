"""Availability calculation: given a date and a service, what slots are free?"""
from datetime import datetime, timedelta, date as date_cls, time as time_cls
from sqlalchemy import and_, func
from extensions import db
from models import Booking, BlockedDate, Setting, Service


# Days of week mapping (Mon=0)
DAY_NAMES = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}


def _get_setting(key, default=""):
    s = db.session.get(Setting, key)
    return s.value if s else default


def get_settings():
    return {
        "working_hours_start": _get_setting("working_hours_start", "09:00"),
        "working_hours_end": _get_setting("working_hours_end", "18:00"),
        "working_days": _get_setting("working_days", "MON,TUE,WED,THU,FRI,SAT"),
        "buffer_minutes": int(_get_setting("buffer_minutes", "15")),
        "slot_increment_minutes": int(_get_setting("slot_increment_minutes", "15")),
        "cancel_window_hours": int(_get_setting("cancel_window_hours", "12")),
    }


def _parse_hhmm(s):
    h, m = s.split(":")
    return time_cls(int(h), int(m))


def is_blocked_day(d):
    return BlockedDate.query.filter_by(date=d).first() is not None


def is_working_day(d, settings):
    return DAY_NAMES[d.weekday()] in settings["working_days"]


def get_blocked_intervals(d):
    """Return list of (start, end) datetime tuples that block availability for date d.
    Includes pending and confirmed bookings (not declined/cancelled/no_show)."""
    day_start = datetime.combine(d, time_cls(0, 0))
    day_end = datetime.combine(d, time_cls(23, 59, 59))

    bookings = Booking.query.filter(
        and_(
            Booking.start_at >= day_start,
            Booking.start_at <= day_end,
            Booking.status.in_(["pending", "confirmed"]),
        )
    ).all()

    return [(b.start_at, b.end_at) for b in bookings]


def compute_slots(d, service_id):
    """Compute available slot start times for the given date and service.

    Returns a list of ISO datetime strings (naive, treated as CAT local).
    Returns [] if the day is blocked, non-working, or has no slots that fit.
    """
    settings = get_settings()
    service = db.session.get(Service, service_id)
    if not service or not service.is_active:
        return []

    if is_blocked_day(d):
        return []
    if not is_working_day(d, settings):
        return []

    duration = service.duration_minutes
    buffer = settings["buffer_minutes"]
    increment = settings["slot_increment_minutes"]

    work_start = datetime.combine(d, _parse_hhmm(settings["working_hours_start"]))
    work_end = datetime.combine(d, _parse_hhmm(settings["working_hours_end"]))

    blocked = get_blocked_intervals(d)

    # Generate candidate slots
    slots = []
    cursor = work_start
    now = datetime.now()  # CAT local clock for "no past slots"
    min_lead = timedelta(minutes=30)  # at least 30 min lead time

    while cursor + timedelta(minutes=duration) <= work_end:
        slot_start = cursor
        slot_end = cursor + timedelta(minutes=duration)

        # Skip past slots
        if d == now.date() and slot_start < now + min_lead:
            cursor += timedelta(minutes=increment)
            continue

        # Check overlap with any blocked interval, applying buffer
        ok = True
        for b_start, b_end in blocked:
            # New booking conflicts if it overlaps with [b_start - buffer, b_end + buffer]
            block_with_buf_start = b_start - timedelta(minutes=buffer)
            block_with_buf_end = b_end + timedelta(minutes=buffer)
            if slot_start < block_with_buf_end and slot_end > block_with_buf_start:
                ok = False
                break

        if ok:
            slots.append(slot_start.isoformat(timespec="minutes"))
        cursor += timedelta(minutes=increment)

    return slots


def day_summary(d, service_id):
    """Return a summary for a single date: full / partial / blocked / closed / available."""
    settings = get_settings()
    if is_blocked_day(d):
        return "blocked"
    if not is_working_day(d, settings):
        return "closed"
    slots = compute_slots(d, service_id)
    if not slots:
        return "full"
    return "available"


def is_slot_available(start_at_dt, service_id):
    """Check whether a specific start datetime is still available for booking.

    Used when actually creating the booking to prevent race conditions.
    """
    d = start_at_dt.date()
    slots = compute_slots(d, service_id)
    target = start_at_dt.isoformat(timespec="minutes")
    return target in slots
