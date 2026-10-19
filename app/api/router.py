"""API layout.

/api/v1/...          customers (patients) and the public catalogue
/api/v1/doctor/...   the signed-in doctor's own workspace
/api/v1/admin/...    staff administration; every route needs an admin account,
                     and each area needs its module (see app.modules.access)
"""

from fastapi import APIRouter, Depends

from app.common.enums import UserRole
from app.db.health import router as health_router
from app.modules.access.router import router as access_router
from app.modules.appointments import router as appointments
from app.modules.auth.dependencies import require_roles
from app.modules.auth.router import router as auth_router
from app.modules.branches import router as branches
from app.modules.doctors import router as doctors
from app.modules.hospitals import router as hospitals
from app.modules.lab import router as lab
from app.modules.leaves import router as leaves
from app.modules.patients import router as patients
from app.modules.payments import router as payments
from app.modules.pharmacy import router as pharmacy
from app.modules.staff import router as staff

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])

# ---- customers & public catalogue: /api/v1/... ----
api_router.include_router(hospitals.router, prefix="/hospitals", tags=["catalogue"])
api_router.include_router(branches.router, tags=["catalogue"])
api_router.include_router(doctors.router, prefix="/doctors", tags=["catalogue"])
api_router.include_router(pharmacy.catalog_router, prefix="/medicines", tags=["catalogue"])
api_router.include_router(lab.catalog_router, prefix="/lab-tests", tags=["catalogue"])

api_router.include_router(patients.router, prefix="/profile", tags=["customer"])
api_router.include_router(appointments.book_router, prefix="/book", tags=["customer"])
api_router.include_router(pharmacy.book_router, prefix="/book", tags=["customer"])
api_router.include_router(lab.book_router, prefix="/book", tags=["customer"])
api_router.include_router(pharmacy.cart_router, prefix="/cart", tags=["customer"])
api_router.include_router(appointments.my_router, prefix="/my/appointments", tags=["customer"])
api_router.include_router(pharmacy.my_orders_router, prefix="/my/orders", tags=["customer"])
api_router.include_router(lab.my_router, prefix="/my/lab-tests", tags=["customer"])
api_router.include_router(payments.my_router, prefix="/my/payments", tags=["customer"])

# ---- doctors: /api/v1/doctor/... ----
doctor = APIRouter(prefix="/doctor", tags=["doctor"])
doctor.include_router(doctors.doctor_router)
doctor.include_router(patients.doctor_router)
doctor.include_router(appointments.doctor_router, prefix="/appointments")
doctor.include_router(leaves.doctor_router, prefix="/leaves")
api_router.include_router(doctor)

# ---- administration: /api/v1/admin/... ----
admin = APIRouter(prefix="/admin", dependencies=[Depends(require_roles(UserRole.ADMIN))])
admin.include_router(access_router, prefix="/access", tags=["admin: access"])
admin.include_router(hospitals.admin_router, prefix="/hospitals", tags=["admin: network"])
admin.include_router(branches.admin_router, tags=["admin: network"])
admin.include_router(doctors.admin_router, prefix="/doctors", tags=["admin: doctors"])
admin.include_router(leaves.admin_router, prefix="/leaves", tags=["admin: doctors"])
admin.include_router(patients.admin_router, prefix="/patients", tags=["admin: patients"])
admin.include_router(
    appointments.admin_router, prefix="/appointments", tags=["admin: appointments"]
)
admin.include_router(pharmacy.admin_medicines_router, prefix="/medicines", tags=["admin: pharmacy"])
admin.include_router(
    pharmacy.admin_orders_router, prefix="/medicine-orders", tags=["admin: pharmacy"]
)
admin.include_router(lab.admin_tests_router, prefix="/lab-tests", tags=["admin: lab"])
admin.include_router(lab.admin_bookings_router, prefix="/lab-bookings", tags=["admin: lab"])
admin.include_router(payments.admin_router, prefix="/payments", tags=["admin: payments"])
admin.include_router(staff.admin_router, prefix="/staff", tags=["admin: staff"])
api_router.include_router(admin)
