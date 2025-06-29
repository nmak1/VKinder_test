import pytest
from unittest.mock import MagicMock
from services.search_service import SearchService
from database.models import User


@pytest.fixture
def mock_services():
    vk_service = MagicMock()
    db_manager = MagicMock()
    return vk_service, db_manager


def test_find_matches_success(mock_services):
    vk_mock, db_mock = mock_services

    # Настраиваем моки
    test_user = User(
        telegram_id=123,
        gender=2,
        city_id=1
    )
    db_mock.get_user.return_value = test_user
    db_mock.is_in_blacklist.return_value = False
    vk_mock.search_users.return_value = [
        {'id': 1, 'first_name': 'Test'}
    ]

    service = SearchService(vk_mock, db_mock)
    results = service.find_matches(123, 20, 30)

    assert len(results) == 1
    assert results[0]['first_name'] == 'Test'
    vk_mock.search_users.assert_called_once()