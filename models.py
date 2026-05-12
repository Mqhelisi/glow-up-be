"""SQLAlchemy models."""
from datetime import datetime
from extensions import db


class Service(db.Model):
    __tablename__ = "services"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    duration_minutes = db.Column(db.Integer, nullable=False)
    price_usd = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(60), default="General")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description or "",
            "duration_minutes": self.duration_minutes,
            "price_usd": float(self.price_usd),
            "category": self.category or "General",
            "is_active": self.is_active,
            "sort_order": self.sort_order or 0,
        }


class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    whatsapp = db.Column(db.String(40))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship("Booking", back_populates="customer")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "whatsapp": self.whatsapp or self.phone,
        }


class Booking(db.Model):
    __tablename__ = "bookings"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False)
    start_at = db.Column(db.DateTime, nullable=False)  # Stored in CAT (naive local)
    end_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)
    # status values: pending, confirmed, declined, cancelled, no_show, completed
    note = db.Column(db.Text, default="")
    cancel_token = db.Column(db.String(64), unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)

    customer = db.relationship("Customer", back_populates="bookings")
    service = db.relationship("Service")

    def to_dict(self, include_customer=True, include_service=True):
        out = {
            "id": self.id,
            "customer_id": self.customer_id,
            "service_id": self.service_id,
            "start_at": self.start_at.isoformat() if self.start_at else None,
            "end_at": self.end_at.isoformat() if self.end_at else None,
            "status": self.status,
            "note": self.note or "",
            "cancel_token": self.cancel_token,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
        }
        if include_customer and self.customer:
            out["customer"] = self.customer.to_dict()
        if include_service and self.service:
            out["service"] = self.service.to_dict()
        return out


class BlockedDate(db.Model):
    __tablename__ = "blocked_dates"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    reason = db.Column(db.String(200), default="")

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "reason": self.reason or "",
        }


class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.Text, default="")


class PortfolioImage(db.Model):
    __tablename__ = "portfolio_images"
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(500), nullable=False)
    caption = db.Column(db.String(200), default="")
    category = db.Column(db.String(60), default="All")
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "image_url": self.image_url,
            "caption": self.caption or "",
            "category": self.category or "All",
            "sort_order": self.sort_order or 0,
        }


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(120), default="Anonymous")
    text = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, default=5)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "author": self.author or "Anonymous",
            "text": self.text,
            "rating": self.rating or 5,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class WhatsappLog(db.Model):
    __tablename__ = "whatsapp_log"
    id = db.Column(db.Integer, primary_key=True)
    to_number = db.Column(db.String(40), nullable=False)
    message = db.Column(db.Text, nullable=False)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=True)
    kind = db.Column(db.String(40), default="info")
    # kinds: admin_new_booking, customer_confirmed, customer_declined,
    #        customer_cancelled, admin_cancellation
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "to_number": self.to_number,
            "message": self.message,
            "booking_id": self.booking_id,
            "kind": self.kind,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
