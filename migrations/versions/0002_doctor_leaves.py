"""Add doctor leave requests and appointment cancellation details.

Revision ID: 0002_doctor_leaves
Revises: 0001_initial_schema
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_doctor_leaves"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "doctor_leaves",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("doctor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=9), nullable=False),
        sa.Column("requested_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_doctor_leave_positive_duration"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_doctor_leave_status",
        ),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_doctor_leaves_doctor_id", "doctor_leaves", ["doctor_id"], unique=False)
    op.create_index("ix_doctor_leaves_status", "doctor_leaves", ["status"], unique=False)
    op.create_index(
        "ix_doctor_leaves_doctor_window",
        "doctor_leaves",
        ["doctor_id", "starts_at", "ends_at"],
        unique=False,
    )

    op.add_column("appointments", sa.Column("cancelled_at", sa.DateTime(timezone=True)))
    op.add_column("appointments", sa.Column("cancelled_by_role", sa.String(length=7)))
    op.add_column("appointments", sa.Column("cancellation_reason", sa.String(length=500)))


def downgrade() -> None:
    op.drop_column("appointments", "cancellation_reason")
    op.drop_column("appointments", "cancelled_by_role")
    op.drop_column("appointments", "cancelled_at")
    op.drop_index("ix_doctor_leaves_doctor_window", table_name="doctor_leaves")
    op.drop_index("ix_doctor_leaves_status", table_name="doctor_leaves")
    op.drop_index("ix_doctor_leaves_doctor_id", table_name="doctor_leaves")
    op.drop_table("doctor_leaves")
