def test_patient_service_module_is_available() -> None:
    from app.modules.patients import service

    assert service is not None
