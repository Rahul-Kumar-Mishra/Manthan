def test_doctor_service_module_is_available() -> None:
    from app.modules.doctors import service

    assert service is not None
