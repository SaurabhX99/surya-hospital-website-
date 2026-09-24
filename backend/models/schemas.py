"""
Pydantic models for all API request bodies.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


# ── Appointments ─────────────────────────────────────────────────────
class AppointmentIn(BaseModel):
    name: str
    mobile: str
    department: Optional[str] = None
    doctor: Optional[str] = None
    date: Optional[str] = None
    message: Optional[str] = None


class StatusIn(BaseModel):
    status: str
    reason: Optional[str] = None


class PurgeIn(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    status: Optional[str] = None


# ── Doctors ──────────────────────────────────────────────────────────
class DoctorIn(BaseModel):
    name: str
    qualification: str
    specialty: str
    department: str
    experience: str
    timing: str
    photo: Optional[str] = None
    about: Optional[str] = None
    featured: bool = False
    active: bool = True


class DoctorUpdate(BaseModel):
    name: Optional[str] = None
    qualification: Optional[str] = None
    specialty: Optional[str] = None
    department: Optional[str] = None
    experience: Optional[str] = None
    timing: Optional[str] = None
    photo: Optional[str] = None
    about: Optional[str] = None
    featured: Optional[bool] = None
    active: Optional[bool] = None


# ── Departments ──────────────────────────────────────────────────────
class DepartmentIn(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    head_doctor: Optional[str] = None
    order: int = 0
    active: bool = True


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    head_doctor: Optional[str] = None
    order: Optional[int] = None
    active: Optional[bool] = None


# ── Blogs ────────────────────────────────────────────────────────────
class BlogIn(BaseModel):
    title: str
    author: str
    category: str
    drive_link: str
    excerpt: Optional[str] = None
    thumbnail: Optional[str] = None
    tags: Optional[str] = None
    published: bool = True


class BlogUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    excerpt: Optional[str] = None
    thumbnail: Optional[str] = None
    tags: Optional[str] = None
    published: Optional[bool] = None
    drive_link: Optional[str] = None


# ── Media & Gallery ──────────────────────────────────────────────────
class MediaIn(BaseModel):
    title: str
    type: str = "image"
    drive_link: str
    alt: Optional[str] = None
    show_in_gallery: bool = True
    order: int = 0


class MediaUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    drive_link: Optional[str] = None
    alt: Optional[str] = None
    show_in_gallery: Optional[bool] = None
    order: Optional[int] = None


class GalleryConfigIn(BaseModel):
    autoplay: Optional[bool] = None
    interval: Optional[int] = None
    transition: Optional[str] = None
    show_captions: Optional[bool] = None


# ── Testimonials ─────────────────────────────────────────────────────
class TestimonialIn(BaseModel):
    name: str
    text: str
    rating: int = 5
    approved: bool = False


class TestimonialUpdate(BaseModel):
    name: Optional[str] = None
    text: Optional[str] = None
    rating: Optional[int] = None
    approved: Optional[bool] = None


# ── Offers ───────────────────────────────────────────────────────────
class OfferIn(BaseModel):
    text: str
    active: bool = True
    order: int = 0


class OfferUpdate(BaseModel):
    text: Optional[str] = None
    active: Optional[bool] = None
    order: Optional[int] = None


# ── Insurance ────────────────────────────────────────────────────────
class InsuranceIn(BaseModel):
    name: str
    logo_drive_link: Optional[str] = None
    active: bool = True
    order: int = 0


class InsuranceUpdate(BaseModel):
    name: Optional[str] = None
    logo_drive_link: Optional[str] = None
    active: Optional[bool] = None
    order: Optional[int] = None


# ── Partners ─────────────────────────────────────────────────────────
class PartnerIn(BaseModel):
    name: str
    logo_drive_link: Optional[str] = None
    active: bool = True
    order: int = 0


class PartnerUpdate(BaseModel):
    name: Optional[str] = None
    logo_drive_link: Optional[str] = None
    active: Optional[bool] = None
    order: Optional[int] = None


# ── Hero Stats ───────────────────────────────────────────────────────
class StatIn(BaseModel):
    label: str
    count: int
    suffix: str = '+'
    icon_key: str = 'patients'
    order: int = 0
    active: bool = True


class StatUpdate(BaseModel):
    label: Optional[str] = None
    count: Optional[int] = None
    suffix: Optional[str] = None
    icon_key: Optional[str] = None
    order: Optional[int] = None
    active: Optional[bool] = None


# ── Facilities ───────────────────────────────────────────────────────
class FacilityIn(BaseModel):
    name: str
    icon_url: Optional[str] = None
    short_desc: str = ""
    description: str = ""
    category: str = "general"
    color: str = "#0A4D8C"
    order: int = 0
    active: bool = True


class FacilityUpdate(BaseModel):
    name: Optional[str] = None
    icon_url: Optional[str] = None
    short_desc: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None
    order: Optional[int] = None
    active: Optional[bool] = None


# ── FAQs ─────────────────────────────────────────────────────────────
class FaqIn(BaseModel):
    question: str
    answer: str
    order: int = 0
    active: bool = True


class FaqUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    order: Optional[int] = None
    active: Optional[bool] = None


# ── Awards & Recognition ─────────────────────────────────────────────
class AwardIn(BaseModel):
    title: str
    description: str = ""
    order: int = 0
    active: bool = True


class AwardUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    order: Optional[int] = None
    active: Optional[bool] = None


# ── SMS Config ───────────────────────────────────────────────────────
class SmsConfigIn(BaseModel):
    """Full SMS configuration — supports Twilio and Gupshup providers."""
    enabled:           bool = False
    provider:          str  = "twilio"
    account_sid:       Optional[str] = None
    auth_token:        Optional[str] = None
    gupshup_api_key:   Optional[str] = None
    gupshup_app_name:  Optional[str] = None
    from_number:       Optional[str] = None
    template: str = (
        "Dear {name}, your appointment has been received. "
        "Ref: {appointment_id}. Dept: {department}. "
        "Date: {date}. We will call you shortly to confirm."
    )


class SmsTestIn(BaseModel):
    phone: str


# ── Site Config ──────────────────────────────────────────────────────
class SiteConfigIn(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    award_images: Optional[List[str]] = None


# ── Auth ─────────────────────────────────────────────────────────────
class LoginIn(BaseModel):
    email: str
    password: str


class MFAVerifyIn(BaseModel):
    pre_token: str
    code: str


# ── Admin Users ──────────────────────────────────────────────────────
class UserCreateIn(BaseModel):
    email: str
    name: str
    password: str
    role: str = "ADMIN"


class UserUpdateIn(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
