from enum import StrEnum


class AppointmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class UserRole(StrEnum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    PATIENT = "patient"


class LeaveStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class Module(StrEnum):
    """Administrative areas. Holding a module lets a staff account manage it and grant it on."""

    DOCTORS = "doctors"
    PATIENTS = "patients"
    APPOINTMENTS = "appointments"
    PHARMACY = "pharmacy"
    LAB = "lab"
    STAFF = "staff"
    PAYMENTS = "payments"
    NETWORK = "network"


class AppointmentMode(StrEnum):
    IN_PERSON = "in_person"
    ONLINE = "online"


class PaymentStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class PaymentPurpose(StrEnum):
    MEDICINE_ORDER = "medicine_order"
    ONLINE_CONSULTATION = "online_consultation"


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    PACKED = "packed"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class LabBookingStatus(StrEnum):
    BOOKED = "booked"
    SAMPLE_COLLECTED = "sample_collected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CollectionType(StrEnum):
    LAB_VISIT = "lab_visit"
    HOME = "home"


class StaffStatus(StrEnum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    LEFT = "left"


class StockMovementReason(StrEnum):
    RESTOCK = "restock"
    SALE = "sale"
    ORDER_CANCELLED = "order_cancelled"
    ADJUSTMENT = "adjustment"
    EXPIRED = "expired"
