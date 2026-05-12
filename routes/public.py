"""Public (customer-facing) routes."""
import secrets
from datetime import datetime, date as date_cls, timedelta
from flask import Blueprint, request, jsonify, current_app
from extensions import db
from models import Service, Customer, Booking, PortfolioImage, Review, Setting
from availability import compute_slots, day_summary, is_slot_available, get_settings
from whatsapp import notify_admin_new_booking, notify_customer_cancelled, notify_admin_cancellation

bp = Blueprint("public", __name__, url_prefix="/api")


@bp.get("/site")
def site_info():
    """Returns the full persona config (from config.json) + booking settings.
    Frontend uses this to render branding, copy, contact info, etc."""
    cfg = current_app.config["SITE_CONFIG"]
    return jsonify({
        # Top-level convenience fields used by the frontend
        "site_name": current_app.config["SITE_NAME"],
        "site_city": current_app.config["SITE_CITY"],
        "timezone": current_app.config["TIMEZONE"],

        # Full persona blocks for any component to consume
        "site": cfg["site"],
        "tech": cfg["tech"],
        "operations": cfg["operations"],
        "messaging": cfg["messaging"],

        # Booking-engine settings (working hours, buffer, etc.)
        "settings": get_settings(),
    })


@bp.get("/services")
def list_services():
    services = (
        Service.query.filter_by(is_active=True)
        .order_by(Service.sort_order.asc(), Service.id.asc())
        .all()
    )
    return jsonify([s.to_dict() for s in services])


@bp.get("/portfolio")
def list_portfolio():
    category = request.args.get("category")
    q = PortfolioImage.query
    if category and category != "All":
        q = q.filter_by(category=category)
    images = q.order_by(PortfolioImage.sort_order.asc(), PortfolioImage.id.asc()).all()
    return jsonify([i.to_dict() for i in images])


@bp.get("/reviews")
def list_reviews():
    reviews = Review.query.order_by(Review.created_at.desc()).all()
    return jsonify([r.to_dict() for r in reviews])


@bp.get("/availability")
def availability_for_day():
    """Return available slot start times for a date and service."""
    date_str = request.args.get("date")
    service_id = request.args.get("service_id", type=int)
    if not date_str or not service_id:
        return jsonify({"error": "date and service_id required"}), 400
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400

    slots = compute_slots(d, service_id)
    return jsonify({"date": d.isoformat(), "service_id": service_id, "slots": slots})


@bp.get("/availability/days")
def availability_summary():
    """Return per-day availability summary across a date range."""
    service_id = request.args.get("service_id", type=int)
    days_ahead = request.args.get("days", default=30, type=int)
    if not service_id:
        return jsonify({"error": "service_id required"}), 400

    today = date_cls.today()
    out = []
    for i in range(days_ahead):
        d = today + timedelta(days=i)
        out.append({"date": d.isoformat(), "status": day_summary(d, service_id)})
    return jsonify(out)


@bp.post("/bookings")
def create_booking():
    """Customer creates a booking request. Idempotency: re-checks availability."""
    data = request.get_json(force=True, silent=True) or {}
    required = ["service_id", "start_at", "name", "phone"]
    for f in required:
        if not data.get(f):
            return jsonify({"error": f"{f} is required"}), 400

    service = db.session.get(Service, int(data["service_id"]))
    if not service or not service.is_active:
        return jsonify({"error": "Service not available"}), 400

    try:
        start_at = datetime.fromisoformat(data["start_at"])
        # Drop seconds to align with our slot granularity
        start_at = start_at.replace(second=0, microsecond=0)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid start_at"}), 400

    # Re-verify availability inside the transaction
    if not is_slot_available(start_at, service.id):
        # Return updated slot list so the frontend can refresh
        fresh_slots = compute_slots(start_at.date(), service.id)
        return jsonify({
            "error": "slot_taken",
            "message": "Sorry, that slot was just taken. Please pick another.",
            "fresh_slots": fresh_slots,
        }), 409

    end_at = start_at + timedelta(minutes=service.duration_minutes)

    customer = Customer(
        name=data["name"].strip(),
        phone=data["phone"].strip(),
        whatsapp=(data.get("whatsapp") or data["phone"]).strip(),
    )
    db.session.add(customer)
    db.session.flush()

    booking = Booking(
        customer_id=customer.id,
        service_id=service.id,
        start_at=start_at,
        end_at=end_at,
        note=(data.get("note") or "").strip(),
        status="pending",
        cancel_token=secrets.token_urlsafe(24),
    )
    db.session.add(booking)
    db.session.flush()

    # Mock WhatsApp notification to admin
    currency = current_app.config["SITE_CONFIG"]["operations"].get("currency_symbol", "$")
    notify_admin_new_booking(booking, current_app.config["NAIL_TECH_PHONE"], currency_symbol=currency)

    db.session.commit()

    return jsonify({
        "ok": True,
        "booking": booking.to_dict(),
        "message": "Request sent! She'll confirm on WhatsApp within 1 hour.",
    }), 201


@bp.get("/bookings/cancel/<token>")
def get_cancel_info(token):
    """Look up a booking by cancel token (used by the cancellation page)."""
    booking = Booking.query.filter_by(cancel_token=token).first()
    if not booking:
        return jsonify({"error": "Invalid cancellation link"}), 404

    settings = get_settings()
    cancel_window = timedelta(hours=settings["cancel_window_hours"])
    can_cancel = (
        booking.status in ("pending", "confirmed")
        and booking.start_at - datetime.now() > cancel_window
    )

    return jsonify({
        "booking": booking.to_dict(),
        "can_cancel": can_cancel,
        "cancel_window_hours": settings["cancel_window_hours"],
    })


@bp.post("/bookings/cancel/<token>")
def cancel_booking(token):
    booking = Booking.query.filter_by(cancel_token=token).first()
    if not booking:
        return jsonify({"error": "Invalid cancellation link"}), 404

    if booking.status in ("cancelled", "declined"):
        return jsonify({"error": "Already cancelled"}), 400

    settings = get_settings()
    cancel_window = timedelta(hours=settings["cancel_window_hours"])
    if booking.start_at - datetime.now() <= cancel_window:
        return jsonify({
            "error": f"Cancellations must be made at least {settings['cancel_window_hours']} hours in advance"
        }), 400

    booking.status = "cancelled"
    booking.cancelled_at = datetime.utcnow()

    # Notify both parties (mock)
    notify_admin_cancellation(booking, current_app.config["NAIL_TECH_PHONE"])
    notify_customer_cancelled(booking)

    db.session.commit()
    return jsonify({"ok": True, "booking": booking.to_dict()})
