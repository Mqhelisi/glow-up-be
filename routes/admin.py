"""Admin (auth-protected) routes."""
from datetime import datetime, date as date_cls, timedelta
from flask import Blueprint, request, jsonify, current_app
from extensions import db
from models import (
    Service, Booking, BlockedDate, Setting, PortfolioImage, Review, WhatsappLog
)
from auth import make_admin_token, admin_required
from whatsapp import notify_customer_confirmed, notify_customer_declined

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


# ---------- Auth ----------

@bp.post("/login")
def login():
    data = request.get_json(force=True, silent=True) or {}
    password = (data.get("password") or "").strip()
    if password != current_app.config["ADMIN_PASSWORD"]:
        return jsonify({"error": "Wrong password"}), 401
    return jsonify({"token": make_admin_token()})


@bp.get("/me")
@admin_required
def me():
    return jsonify({"ok": True})


# ---------- Bookings ----------

@bp.get("/bookings")
@admin_required
def list_bookings():
    status = request.args.get("status")  # optional filter
    from_str = request.args.get("from")
    to_str = request.args.get("to")

    q = Booking.query
    if status:
        q = q.filter(Booking.status == status)
    if from_str:
        try:
            d = datetime.strptime(from_str, "%Y-%m-%d")
            q = q.filter(Booking.start_at >= d)
        except ValueError:
            pass
    if to_str:
        try:
            d = datetime.strptime(to_str, "%Y-%m-%d") + timedelta(days=1)
            q = q.filter(Booking.start_at < d)
        except ValueError:
            pass

    bookings = q.order_by(Booking.start_at.asc()).all()
    return jsonify([b.to_dict() for b in bookings])


@bp.post("/bookings/<int:booking_id>/confirm")
@admin_required
def confirm_booking(booking_id):
    booking = db.session.get(Booking, booking_id)
    if not booking:
        return jsonify({"error": "Not found"}), 404
    if booking.status != "pending":
        return jsonify({"error": f"Booking is {booking.status}, can only confirm pending"}), 400

    booking.status = "confirmed"
    booking.confirmed_at = datetime.utcnow()

    # Build cancel link for the customer's frontend route
    origin = current_app.config.get("FRONTEND_BASE_URL") or (
        current_app.config["CORS_ORIGINS"][0] if current_app.config["CORS_ORIGINS"] else "http://localhost:5173"
    )
    cancel_link = f"{origin}/cancel/{booking.cancel_token}"
    currency = current_app.config["SITE_CONFIG"]["operations"].get("currency_symbol", "$")
    notify_customer_confirmed(booking, cancel_link, currency_symbol=currency)

    db.session.commit()
    return jsonify(booking.to_dict())


@bp.post("/bookings/<int:booking_id>/decline")
@admin_required
def decline_booking(booking_id):
    data = request.get_json(force=True, silent=True) or {}
    reason = (data.get("reason") or "").strip()

    booking = db.session.get(Booking, booking_id)
    if not booking:
        return jsonify({"error": "Not found"}), 404
    if booking.status not in ("pending", "confirmed"):
        return jsonify({"error": f"Cannot decline a {booking.status} booking"}), 400

    booking.status = "declined"
    notify_customer_declined(booking, reason or None)
    db.session.commit()
    return jsonify(booking.to_dict())


@bp.post("/bookings/<int:booking_id>/no-show")
@admin_required
def no_show_booking(booking_id):
    booking = db.session.get(Booking, booking_id)
    if not booking:
        return jsonify({"error": "Not found"}), 404
    booking.status = "no_show"
    db.session.commit()
    return jsonify(booking.to_dict())


@bp.post("/bookings/<int:booking_id>/complete")
@admin_required
def complete_booking(booking_id):
    booking = db.session.get(Booking, booking_id)
    if not booking:
        return jsonify({"error": "Not found"}), 404
    booking.status = "completed"
    db.session.commit()
    return jsonify(booking.to_dict())


# ---------- Services ----------

@bp.get("/services")
@admin_required
def admin_list_services():
    services = Service.query.order_by(Service.sort_order.asc(), Service.id.asc()).all()
    return jsonify([s.to_dict() for s in services])


@bp.post("/services")
@admin_required
def admin_create_service():
    data = request.get_json(force=True) or {}
    s = Service(
        name=data["name"],
        description=data.get("description", ""),
        duration_minutes=int(data["duration_minutes"]),
        price_usd=float(data["price_usd"]),
        category=data.get("category", "General"),
        is_active=bool(data.get("is_active", True)),
        sort_order=int(data.get("sort_order", 0)),
    )
    db.session.add(s)
    db.session.commit()
    return jsonify(s.to_dict()), 201


@bp.put("/services/<int:service_id>")
@admin_required
def admin_update_service(service_id):
    data = request.get_json(force=True) or {}
    s = db.session.get(Service, service_id)
    if not s:
        return jsonify({"error": "Not found"}), 404
    for f in ("name", "description", "category"):
        if f in data:
            setattr(s, f, data[f])
    if "duration_minutes" in data:
        s.duration_minutes = int(data["duration_minutes"])
    if "price_usd" in data:
        s.price_usd = float(data["price_usd"])
    if "is_active" in data:
        s.is_active = bool(data["is_active"])
    if "sort_order" in data:
        s.sort_order = int(data["sort_order"])
    db.session.commit()
    return jsonify(s.to_dict())


@bp.delete("/services/<int:service_id>")
@admin_required
def admin_delete_service(service_id):
    s = db.session.get(Service, service_id)
    if not s:
        return jsonify({"error": "Not found"}), 404
    s.is_active = False
    db.session.commit()
    return jsonify({"ok": True})


# ---------- Blocked dates ----------

@bp.get("/blocked-dates")
@admin_required
def list_blocked():
    rows = BlockedDate.query.order_by(BlockedDate.date.asc()).all()
    return jsonify([r.to_dict() for r in rows])


@bp.post("/blocked-dates")
@admin_required
def add_blocked():
    data = request.get_json(force=True) or {}
    try:
        d = datetime.strptime(data["date"], "%Y-%m-%d").date()
    except (KeyError, ValueError):
        return jsonify({"error": "date YYYY-MM-DD required"}), 400
    if BlockedDate.query.filter_by(date=d).first():
        return jsonify({"error": "Already blocked"}), 400
    row = BlockedDate(date=d, reason=data.get("reason", ""))
    db.session.add(row)
    db.session.commit()
    return jsonify(row.to_dict()), 201


@bp.delete("/blocked-dates/<int:bid>")
@admin_required
def remove_blocked(bid):
    row = db.session.get(BlockedDate, bid)
    if not row:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(row)
    db.session.commit()
    return jsonify({"ok": True})


# ---------- Settings ----------

@bp.get("/settings")
@admin_required
def get_settings_route():
    rows = Setting.query.all()
    return jsonify({r.key: r.value for r in rows})


@bp.put("/settings")
@admin_required
def update_settings_route():
    data = request.get_json(force=True) or {}
    for k, v in data.items():
        row = db.session.get(Setting, k)
        if row:
            row.value = str(v)
        else:
            db.session.add(Setting(key=k, value=str(v)))
    db.session.commit()
    rows = Setting.query.all()
    return jsonify({r.key: r.value for r in rows})


# ---------- Portfolio ----------

@bp.get("/portfolio")
@admin_required
def admin_list_portfolio():
    rows = PortfolioImage.query.order_by(PortfolioImage.sort_order.asc(), PortfolioImage.id.asc()).all()
    return jsonify([r.to_dict() for r in rows])


@bp.post("/portfolio")
@admin_required
def admin_add_portfolio():
    data = request.get_json(force=True) or {}
    if not data.get("image_url"):
        return jsonify({"error": "image_url required"}), 400
    row = PortfolioImage(
        image_url=data["image_url"],
        caption=data.get("caption", ""),
        category=data.get("category", "All"),
        sort_order=int(data.get("sort_order", 0)),
    )
    db.session.add(row)
    db.session.commit()
    return jsonify(row.to_dict()), 201


@bp.put("/portfolio/<int:pid>")
@admin_required
def admin_update_portfolio(pid):
    row = db.session.get(PortfolioImage, pid)
    if not row:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json(force=True) or {}
    for f in ("image_url", "caption", "category"):
        if f in data:
            setattr(row, f, data[f])
    if "sort_order" in data:
        row.sort_order = int(data["sort_order"])
    db.session.commit()
    return jsonify(row.to_dict())


@bp.delete("/portfolio/<int:pid>")
@admin_required
def admin_delete_portfolio(pid):
    row = db.session.get(PortfolioImage, pid)
    if not row:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(row)
    db.session.commit()
    return jsonify({"ok": True})


# ---------- Reviews ----------

@bp.get("/reviews")
@admin_required
def admin_list_reviews():
    return jsonify([r.to_dict() for r in Review.query.order_by(Review.created_at.desc()).all()])


@bp.post("/reviews")
@admin_required
def admin_add_review():
    data = request.get_json(force=True) or {}
    if not data.get("text"):
        return jsonify({"error": "text required"}), 400
    row = Review(
        author=data.get("author", "Anonymous"),
        text=data["text"],
        rating=int(data.get("rating", 5)),
    )
    db.session.add(row)
    db.session.commit()
    return jsonify(row.to_dict()), 201


@bp.delete("/reviews/<int:rid>")
@admin_required
def admin_delete_review(rid):
    row = db.session.get(Review, rid)
    if not row:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(row)
    db.session.commit()
    return jsonify({"ok": True})


# ---------- WhatsApp log (for the mock) ----------

@bp.get("/whatsapp-log")
@admin_required
def whatsapp_log():
    rows = WhatsappLog.query.order_by(WhatsappLog.created_at.desc()).limit(200).all()
    return jsonify([r.to_dict() for r in rows])


# ---------- Dashboard summary ----------

@bp.get("/dashboard")
@admin_required
def dashboard():
    today = date_cls.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = today_start + timedelta(days=1)
    week_end = today_start + timedelta(days=7)

    pending = Booking.query.filter_by(status="pending").count()
    today_bookings = Booking.query.filter(
        Booking.start_at >= today_start,
        Booking.start_at < today_end,
        Booking.status.in_(["pending", "confirmed"]),
    ).count()
    week_bookings = Booking.query.filter(
        Booking.start_at >= today_start,
        Booking.start_at < week_end,
        Booking.status.in_(["pending", "confirmed"]),
    ).count()

    return jsonify({
        "pending_count": pending,
        "today_count": today_bookings,
        "week_count": week_bookings,
    })
