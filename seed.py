"""Seed initial data so the app is testable on first run."""
import secrets
from datetime import datetime, date as date_cls, timedelta, time as time_cls
from extensions import db
from models import (
    Service, Customer, Booking, PortfolioImage, Review, Setting
)


DEFAULT_SETTINGS = {
    "working_hours_start": "09:00",
    "working_hours_end": "18:00",
    "working_days": "MON,TUE,WED,THU,FRI,SAT",
    "buffer_minutes": "15",
    "slot_increment_minutes": "15",
    "cancel_window_hours": "12",
}


SEED_SERVICES = [
    # Acrylics
    {"name": "Acrylic Full Set",     "category": "Acrylics",  "duration_minutes": 90, "price_usd": 55.00, "description": "Sculpted acrylic extensions with shape and length of your choice.", "sort_order": 10},
    {"name": "Acrylic Refill",       "category": "Acrylics",  "duration_minutes": 60, "price_usd": 40.00, "description": "Refill of existing acrylics with reshape and polish.", "sort_order": 11},
    {"name": "Acrylic Removal",      "category": "Acrylics",  "duration_minutes": 30, "price_usd": 15.00, "description": "Safe soak-off removal with cuticle care.", "sort_order": 12},
    # Gel
    {"name": "Gel Overlay",          "category": "Gel",       "duration_minutes": 45, "price_usd": 35.00, "description": "Strengthening gel overlay on natural nails.", "sort_order": 20},
    {"name": "Gel Manicure",         "category": "Gel",       "duration_minutes": 60, "price_usd": 45.00, "description": "Full manicure finished with long-lasting gel polish.", "sort_order": 21},
    {"name": "Gel Polish Change",    "category": "Gel",       "duration_minutes": 30, "price_usd": 25.00, "description": "Quick colour change on existing gel.", "sort_order": 22},
    # Nail Art
    {"name": "Nail Art (per nail)",  "category": "Nail Art",  "duration_minutes": 15, "price_usd":  5.00, "description": "Custom hand-painted designs, charms, chrome.", "sort_order": 30},
    {"name": "Full Set Nail Art",    "category": "Nail Art",  "duration_minutes": 60, "price_usd": 50.00, "description": "Ten nails of intricate art — your inspo, my craft.", "sort_order": 31},
    # Pedicure
    {"name": "Classic Pedicure",     "category": "Pedicure",  "duration_minutes": 45, "price_usd": 35.00, "description": "Soak, scrub, cuticle care, regular polish.", "sort_order": 40},
    {"name": "Spa Pedicure",         "category": "Pedicure",  "duration_minutes": 75, "price_usd": 50.00, "description": "Full pampering — mask, massage, hot towel finish.", "sort_order": 41},
]


# Picsum returns random tasteful photos. Replace these with real nail photos
# via the admin panel once you have them.
def _img(seed, w=800, h=800):
    return f"https://picsum.photos/seed/glam-{seed}/{w}/{h}"


SEED_PORTFOLIO = [
    {"image_url": _img("blush01"),    "caption": "Soft blush almonds",         "category": "Gel",      "sort_order": 1},
    {"image_url": _img("rose02"),     "caption": "Rose chrome stilettos",      "category": "Acrylics", "sort_order": 2},
    {"image_url": _img("nude03"),     "caption": "Nude gloss minimal",         "category": "Gel",      "sort_order": 3},
    {"image_url": _img("art04"),      "caption": "French with hearts",         "category": "Nail Art", "sort_order": 4},
    {"image_url": _img("ped05"),      "caption": "Cherry red toes",            "category": "Pedicure", "sort_order": 5},
    {"image_url": _img("acryl06"),    "caption": "Long coffin set",            "category": "Acrylics", "sort_order": 6},
    {"image_url": _img("art07"),      "caption": "Floral hand-painted art",    "category": "Nail Art", "sort_order": 7},
    {"image_url": _img("gel08"),      "caption": "Glazed-donut chrome",        "category": "Gel",      "sort_order": 8},
    {"image_url": _img("ped09"),      "caption": "Spa pedi with art",          "category": "Pedicure", "sort_order": 9},
    {"image_url": _img("acryl10"),    "caption": "Ombré pink ballerina",       "category": "Acrylics", "sort_order": 10},
    {"image_url": _img("art11"),      "caption": "Animal print accent",        "category": "Nail Art", "sort_order": 11},
    {"image_url": _img("gel12"),      "caption": "Cat-eye gel finish",         "category": "Gel",      "sort_order": 12},
]


SEED_REVIEWS = [
    {"author": "Avery T.",   "text": "Absolutely obsessed with my acrylics! She took her time and the shape is perfect. Lasted me 4 weeks no chips.", "rating": 5},
    {"author": "Naomi S.",   "text": "I came in with a Pinterest reference and walked out with literally the exact thing. So talented.",                "rating": 5},
    {"author": "Priya K.",   "text": "The studio vibe is gorgeous and she's so welcoming. Booking was so easy too — no calling and back-and-forth.",   "rating": 5},
    {"author": "Jordan R.",  "text": "First time getting gel and now I'm hooked. Truly the best in town, hands down.",                                   "rating": 5},
]


def seed_if_empty():
    """Populate the DB with starter data if it's empty."""
    # Settings — always ensure defaults exist
    for k, v in DEFAULT_SETTINGS.items():
        if not db.session.get(Setting, k):
            db.session.add(Setting(key=k, value=v))

    if Service.query.count() == 0:
        for s in SEED_SERVICES:
            db.session.add(Service(is_active=True, **s))

    if PortfolioImage.query.count() == 0:
        for p in SEED_PORTFOLIO:
            db.session.add(PortfolioImage(**p))

    if Review.query.count() == 0:
        for r in SEED_REVIEWS:
            db.session.add(Review(**r))

    db.session.commit()

    # Sample bookings for admin demo (only if there are no bookings yet)
    if Booking.query.count() == 0:
        gel_mani = Service.query.filter_by(name="Gel Manicure").first()
        acrylic = Service.query.filter_by(name="Acrylic Full Set").first()
        if gel_mani and acrylic:
            today = date_cls.today()
            tomorrow = today + timedelta(days=1)

            c1 = Customer(name="Sarah Lee", phone="+1 555 234 5678", whatsapp="+15552345678")
            db.session.add(c1)
            db.session.flush()

            start1 = datetime.combine(tomorrow, time_cls(11, 0))
            db.session.add(Booking(
                customer_id=c1.id,
                service_id=gel_mani.id,
                start_at=start1,
                end_at=start1 + timedelta(minutes=gel_mani.duration_minutes),
                status="pending",
                note="I'd love a soft pink colour please ✨",
                cancel_token=secrets.token_urlsafe(24),
            ))

            c2 = Customer(name="Maya Chen", phone="+1 555 111 2222", whatsapp="+15551112222")
            db.session.add(c2)
            db.session.flush()

            day2 = today + timedelta(days=2)
            start2 = datetime.combine(day2, time_cls(14, 0))
            db.session.add(Booking(
                customer_id=c2.id,
                service_id=acrylic.id,
                start_at=start2,
                end_at=start2 + timedelta(minutes=acrylic.duration_minutes),
                status="confirmed",
                note="Coffin shape, nude with white tips",
                cancel_token=secrets.token_urlsafe(24),
                confirmed_at=datetime.utcnow(),
            ))

            db.session.commit()
