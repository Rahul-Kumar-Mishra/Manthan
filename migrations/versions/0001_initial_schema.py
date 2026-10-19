"""Create the Level 1 hospital-management schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ExcludeConstraint

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=7), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'doctor', 'patient')", name="ck_user_role"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "hospitals",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hospitals_name", "hospitals", ["name"], unique=True)

    op.create_table(
        "branches",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("hospital_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hospital_id", "name", name="uq_branch_hospital_name"),
    )
    op.create_index("ix_branches_hospital_id", "branches", ["hospital_id"], unique=False)

    op.create_table(
        "doctors",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("branch_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("specialization", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_doctors_branch_id", "doctors", ["branch_id"], unique=False)
    op.create_index("ix_doctors_full_name", "doctors", ["full_name"], unique=False)
    op.create_index("ix_doctors_specialization", "doctors", ["specialization"], unique=False)

    op.create_table(
        "patients",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_patients_full_name", "patients", ["full_name"], unique=False)

    op.create_table(
        "appointments",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("patient_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("doctor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=9), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_appointment_positive_duration"),
        ExcludeConstraint(
            ("doctor_id", "="),
            (sa.text("tstzrange(starts_at, ends_at, '[)')"), "&&"),
            using="gist",
            name="ex_appointment_doctor_no_overlap",
            ops={"doctor_id": "gist_uuid_ops"},
            where=sa.text("status = 'scheduled'"),
        ),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appointments_doctor_id", "appointments", ["doctor_id"], unique=False)
    op.create_index("ix_appointments_patient_id", "appointments", ["patient_id"], unique=False)
    op.create_index("ix_appointments_starts_at", "appointments", ["starts_at"], unique=False)
    op.create_index("ix_appointments_status", "appointments", ["status"], unique=False)
    op.create_index(
        "uq_appointment_doctor_start",
        "appointments",
        ["doctor_id", "starts_at"],
        unique=True,
        postgresql_where=sa.text("status = 'scheduled'"),
    )


def downgrade() -> None:
    op.drop_index("uq_appointment_doctor_start", table_name="appointments")
    op.drop_index("ix_appointments_status", table_name="appointments")
    op.drop_index("ix_appointments_starts_at", table_name="appointments")
    op.drop_index("ix_appointments_patient_id", table_name="appointments")
    op.drop_index("ix_appointments_doctor_id", table_name="appointments")
    op.drop_table("appointments")
    op.drop_index("ix_patients_full_name", table_name="patients")
    op.drop_table("patients")
    op.drop_index("ix_doctors_specialization", table_name="doctors")
    op.drop_index("ix_doctors_full_name", table_name="doctors")
    op.drop_index("ix_doctors_branch_id", table_name="doctors")
    op.drop_table("doctors")
    op.drop_index("ix_branches_hospital_id", table_name="branches")
    op.drop_table("branches")
    op.drop_index("ix_hospitals_name", table_name="hospitals")
    op.drop_table("hospitals")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
