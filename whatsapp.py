"""Mock WhatsApp service.

Real Twilio integration is not enabled in this build. All messages are:
  1. Printed to stdout with a 📱 banner (visible in the Flask terminal)
  2. Saved to the whatsapp_log table (visible in the admin Notifications view)

To switch to real Twilio later, replace `_send` with a Twilio API call.
"""
from datetime import datetime
from extensions import db
from models import WhatsappLog


def _send(to_number, message, kind, booking_id=None):
    """Mock send: print + persist."""
    banner = f"\n{'═' * 60}\n📱  MOCK WHATSAPP  →  {to_number}\n{'─' * 60}\n{message}\n{'═' * 60}\n"
    print(banner, flush=True)

    log = WhatsappLog(
        to_number=to_number,
        message=message,
        booking_id=booking_id,
        kind=kind,
        created_at=datetime.utcnow(),
    )
    db.session.add(log)
    # Caller is responsible for committing (so it stays in the same txn as the booking)
    return log


def _format_dt(dt):
    """Format a datetime in a natural human style."""
    return dt.strftime("%-d %b %Y at %H:%M") if dt else "—"


def _format_time_range(start, end):
    return f"{start.strftime('%H:%M')} – {end.strftime('%H:%M')}"


def notify_admin_new_booking(booking, admin_phone, currency_symbol="$"):
    """Send a 'new booking request' message to the nail tech."""
    c = booking.customer
    s = booking.service
    msg = (
        "✨ New Booking Request ✨\n"
        f"\n"
        f"Name: {c.name}\n"
        f"Service: {s.name}\n"
        f"Date: {booking.start_at.strftime('%-d %b %Y')}\n"
        f"Time: {_format_time_range(booking.start_at, booking.end_at)}\n"
        f"Duration: {s.duration_minutes} min\n"
        f"Price: {currency_symbol}{s.price_usd:.2f}\n"
        f"Phone: {c.phone}\n"
        f"WhatsApp: {c.whatsapp or c.phone}\n"
        + (f"Note: {booking.note}\n" if booking.note else "")
        + f"\nOpen your admin panel to confirm or decline."
    )
    return _send(admin_phone, msg, "admin_new_booking", booking.id)


def notify_customer_confirmed(booking, cancel_link, currency_symbol="$"):
    """Confirmation message to the customer."""
    c = booking.customer
    s = booking.service
    msg = (
        f"Hey {c.name.split()[0]} 💅\n"
        f"\n"
        f"Your booking is confirmed!\n"
        f"\n"
        f"Service: {s.name}\n"
        f"Date: {booking.start_at.strftime('%A, %-d %b %Y')}\n"
        f"Time: {_format_time_range(booking.start_at, booking.end_at)}\n"
        f"Total: {currency_symbol}{s.price_usd:.2f}\n"
        f"\n"
        f"Need to cancel? Use this link (up to 12 hours before):\n"
        f"{cancel_link}\n"
        f"\n"
        f"Can't wait to see you! ✨"
    )
    return _send(c.whatsapp or c.phone, msg, "customer_confirmed", booking.id)


def notify_customer_declined(booking, reason=None):
    c = booking.customer
    s = booking.service
    msg = (
        f"Hey {c.name.split()[0]},\n"
        f"\n"
        f"Unfortunately I can't take your {s.name} booking on "
        f"{booking.start_at.strftime('%-d %b at %H:%M')}.\n"
        + (f"\nReason: {reason}\n" if reason else "")
        + f"\nPlease pick another slot — I'd still love to do your nails! 💕"
    )
    return _send(c.whatsapp or c.phone, msg, "customer_declined", booking.id)


def notify_admin_cancellation(booking, admin_phone):
    """Tell the nail tech a customer cancelled."""
    c = booking.customer
    s = booking.service
    msg = (
        "⚠️ Booking Cancelled\n"
        f"\n"
        f"Customer: {c.name}\n"
        f"Service: {s.name}\n"
        f"Was scheduled: {_format_dt(booking.start_at)}\n"
        f"Phone: {c.phone}\n"
        f"\nThis slot is now free again."
    )
    return _send(admin_phone, msg, "admin_cancellation", booking.id)


def notify_customer_cancelled(booking):
    """Acknowledge cancellation to customer."""
    c = booking.customer
    s = booking.service
    msg = (
        f"Hi {c.name.split()[0]},\n"
        f"\n"
        f"Your {s.name} booking on {_format_dt(booking.start_at)} has been cancelled.\n"
        f"\nHope to see you again soon! ✨"
    )
    return _send(c.whatsapp or c.phone, msg, "customer_cancelled", booking.id)
