"""Module access hierarchy, pharmacy, lab, payments, staff directory, on-call consults.

Revision ID: 0003_access_pharmacy_lab
Revises: 0002_doctor_leaves
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_access_pharmacy_lab"
down_revision = "0002_doctor_leaves"
branch_labels = None
depends_on = None

UUID = sa.Uuid(as_uuid=True)
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("is_md", sa.Boolean(), nullable=False, server_default=sa.false())
    )

    op.create_table(
        "module_grants",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module", sa.String(20), nullable=False),
        sa.Column("granted_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, nullable=False),
        sa.UniqueConstraint("user_id", "module", name="uq_module_grant_user_module"),
    )
    op.create_index("ix_module_grants_user_id", "module_grants", ["user_id"])
    op.create_index("ix_module_grants_module", "module_grants", ["module"])

    for name, column in [
        ("experience_years", sa.Integer()),
        ("qualifications", sa.String(300)),
        ("registration_number", sa.String(60)),
        ("languages", sa.String(200)),
        ("bio", sa.String(2000)),
        ("consultation_fee_paise", sa.Integer()),
        ("online_fee_paise", sa.Integer()),
    ]:
        op.add_column("doctors", sa.Column(name, column, nullable=True))
    op.add_column(
        "doctors",
        sa.Column("available_online", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.add_column(
        "appointments",
        sa.Column("mode", sa.String(9), nullable=False, server_default="in_person"),
    )
    op.add_column("appointments", sa.Column("contact_phone", sa.String(40)))
    op.add_column("appointments", sa.Column("fee_paise", sa.Integer()))
    op.add_column(
        "appointments",
        sa.Column("payment_status", sa.String(12), nullable=False, server_default="not_required"),
    )
    op.add_column("appointments", sa.Column("payment_id", UUID))

    op.create_table(
        "payments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("reference_id", UUID, nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("method", sa.String(20)),
        sa.Column("method_detail", sa.String(80)),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_reference", sa.String(80)),
        sa.Column("failure_reason", sa.String(200)),
        sa.Column("paid_at", TS),
        sa.Column("refunded_at", TS),
        sa.Column("created_at", TS, nullable=False),
        sa.CheckConstraint("amount_paise > 0", name="ck_payment_positive_amount"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_reference_id", "payments", ["reference_id"])
    op.create_index("ix_payments_status", "payments", ["status"])

    op.create_table(
        "medicines",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("generic_name", sa.String(160)),
        sa.Column("manufacturer", sa.String(160)),
        sa.Column("form", sa.String(40), nullable=False),
        sa.Column("strength", sa.String(60)),
        sa.Column("pack_size", sa.String(60)),
        sa.Column("category", sa.String(80)),
        sa.Column("description", sa.String(1000)),
        sa.Column("price_paise", sa.Integer(), nullable=False),
        sa.Column("requires_prescription", sa.Boolean(), nullable=False),
        sa.Column("stock_quantity", sa.Integer(), nullable=False),
        sa.Column("reorder_level", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
        sa.CheckConstraint("stock_quantity >= 0", name="ck_medicine_stock_non_negative"),
        sa.CheckConstraint("price_paise > 0", name="ck_medicine_positive_price"),
        sa.UniqueConstraint("name", "strength", "form", name="uq_medicine_name_strength_form"),
    )
    op.create_index("ix_medicines_name", "medicines", ["name"])
    op.create_index("ix_medicines_category", "medicines", ["category"])

    op.create_table(
        "stock_movements",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "medicine_id", UUID, sa.ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("change", sa.Integer(), nullable=False),
        sa.Column("quantity_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(20), nullable=False),
        sa.Column("batch_number", sa.String(60)),
        sa.Column("expiry_date", sa.String(10)),
        sa.Column("note", sa.String(300)),
        sa.Column("order_id", UUID),
        sa.Column("performed_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_stock_movements_medicine_id", "stock_movements", ["medicine_id"])

    op.create_table(
        "cart_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "medicine_id", UUID, sa.ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("added_at", TS, nullable=False),
        sa.UniqueConstraint("user_id", "medicine_id", name="uq_cart_user_medicine"),
        sa.CheckConstraint("quantity > 0", name="ck_cart_positive_quantity"),
    )
    op.create_index("ix_cart_items_user_id", "cart_items", ["user_id"])

    op.create_table(
        "medicine_orders",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("total_paise", sa.Integer(), nullable=False),
        sa.Column("delivery_address", sa.String(400), nullable=False),
        sa.Column("contact_phone", sa.String(40), nullable=False),
        sa.Column("payment_id", UUID),
        sa.Column("cancellation_reason", sa.String(300)),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
    )
    op.create_index("ix_medicine_orders_user_id", "medicine_orders", ["user_id"])
    op.create_index("ix_medicine_orders_status", "medicine_orders", ["status"])

    op.create_table(
        "medicine_order_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "order_id",
            UUID,
            sa.ForeignKey("medicine_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("medicine_id", UUID, sa.ForeignKey("medicines.id", ondelete="SET NULL")),
        sa.Column("medicine_name", sa.String(240), nullable=False),
        sa.Column("unit_price_paise", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
    )
    op.create_index("ix_medicine_order_items_order_id", "medicine_order_items", ["order_id"])

    op.create_table(
        "lab_tests",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("code", sa.String(30), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(80)),
        sa.Column("description", sa.String(1000)),
        sa.Column("sample_type", sa.String(60)),
        sa.Column("preparation", sa.String(300)),
        sa.Column("turnaround_hours", sa.Integer(), nullable=False),
        sa.Column("price_paise", sa.Integer(), nullable=False),
        sa.Column("home_collection", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.CheckConstraint("price_paise > 0", name="ck_lab_test_positive_price"),
    )
    op.create_index("ix_lab_tests_name", "lab_tests", ["name"])

    op.create_table(
        "lab_bookings",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("lab_test_id", UUID, sa.ForeignKey("lab_tests.id", ondelete="SET NULL")),
        sa.Column("test_name", sa.String(160), nullable=False),
        sa.Column("price_paise", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", TS, nullable=False),
        sa.Column("collection_type", sa.String(9), nullable=False),
        sa.Column("address", sa.String(400)),
        sa.Column("contact_phone", sa.String(40), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("result_note", sa.String(1000)),
        sa.Column("cancellation_reason", sa.String(300)),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_lab_bookings_user_id", "lab_bookings", ["user_id"])
    op.create_index("ix_lab_bookings_scheduled_at", "lab_bookings", ["scheduled_at"])
    op.create_index("ix_lab_bookings_status", "lab_bookings", ["status"])

    op.create_table(
        "staff_members",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("designation", sa.String(120), nullable=False),
        sa.Column("department", sa.String(120)),
        sa.Column("branch_id", UUID, sa.ForeignKey("branches.id", ondelete="SET NULL")),
        sa.Column("email", sa.String(254), unique=True),
        sa.Column("phone", sa.String(40)),
        sa.Column("employment_type", sa.String(20), nullable=False),
        sa.Column("joined_on", sa.Date()),
        sa.Column("left_on", sa.Date()),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), unique=True),
        sa.Column("notes", sa.String(1000)),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
    )
    op.create_index("ix_staff_members_full_name", "staff_members", ["full_name"])
    op.create_index("ix_staff_members_department", "staff_members", ["department"])
    op.create_index("ix_staff_members_status", "staff_members", ["status"])


def downgrade() -> None:
    for table in [
        "staff_members",
        "lab_bookings",
        "lab_tests",
        "medicine_order_items",
        "medicine_orders",
        "cart_items",
        "stock_movements",
        "medicines",
        "payments",
        "module_grants",
    ]:
        op.drop_table(table)
    for column in ["payment_id", "payment_status", "fee_paise", "contact_phone", "mode"]:
        op.drop_column("appointments", column)
    for column in [
        "available_online",
        "online_fee_paise",
        "consultation_fee_paise",
        "bio",
        "languages",
        "registration_number",
        "qualifications",
        "experience_years",
    ]:
        op.drop_column("doctors", column)
    op.drop_column("users", "is_md")
