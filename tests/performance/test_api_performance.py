import pytest


@pytest.mark.skip(reason="Performance budgets are set after deployment topology is defined")
def test_api_response_time_budget() -> None:
    raise NotImplementedError
