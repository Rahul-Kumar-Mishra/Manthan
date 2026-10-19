from app.common.enums import AppointmentStatus


def test_appointment_status_values() -> None:
    assert AppointmentStatus.SCHEDULED == "scheduled"
