import pytest
from unittest.mock import patch, MagicMock
from services.vk_service import VKService
from config.settings import settings


@pytest.fixture
def vk_service():
    return VKService(token="test_token")


@patch('services.vk_service.requests.get')
def test_get_user_info_success(mock_get, vk_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'response': [{'id': 1, 'first_name': 'Test'}]
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = vk_service.get_user_info(1)
    assert result['id'] == 1
    assert result['first_name'] == 'Test'


@patch('services.vk_service.requests.get')
def test_get_user_info_failure(mock_get, vk_service):
    mock_get.side_effect = Exception("API error")
    result = vk_service.get_user_info(1)
    assert result is None