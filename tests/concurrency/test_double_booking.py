from sqlalchemy.dialects.postgresql import ExcludeConstraint

from app.modules.appointments.models import Appointment


def test_database_enforces_doctor_appointment_overlap_constraints() -> None:
    constraints = Appointment.__table__.constraints

    assert any(
        isinstance(constraint, ExcludeConstraint)
        and constraint.name == "ex_appointment_doctor_no_overlap"
        for constraint in constraints
    )
    assert any(
        index.name == "uq_appointment_doctor_start" and index.unique
        for index in Appointment.__table__.indexes
    )
