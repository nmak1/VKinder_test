import requests
import time
from functools import lru_cache
from datetime import datetime
from typing import Dict, List, Optional
import logging
from config.settings import settings

logger = logging.getLogger(__name__)


class VKService:
    def __init__(self, token: str = settings.VK_TOKEN, version: str = '5.131'):
        self.token = token
        self.version = version
        self.base_url = 'https://api.vk.com/method/'


    def _make_request(self, method: str, params: Dict) -> Dict:
        params.update({'access_token': self.token, 'v': self.version})
        time.sleep(settings.REQUEST_DELAY)

        try:
            response = requests.get(f"{self.base_url}{method}", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if 'error' in data:
                error = data['error']
                logger.error(f"VK API error {error.get('error_code')}: {error.get('error_msg')}")
                raise Exception(f"VK API error: {error.get('error_msg')}")

            return data.get('response', {})
        except Exception as e:
            logger.error(f"Request to VK API failed: {e}")
            raise

    @lru_cache(maxsize=100)
    def get_user_info(self, user_id: int) -> Optional[Dict]:
        params = {'user_ids': user_id, 'fields': 'sex,bdate,city'}
        try:
            response = self._make_request('users.get', params)
            return response[0] if response else None
        except Exception:
            return None

    def search_users(self, age_from: int, age_to: int, sex: int, city_id: int, count: int = 50) -> List[Dict]:
        params = {
            'count': min(count, 1000),
            'age_from': age_from,
            'age_to': age_to,
            'sex': 3 - sex,
            'city': city_id,
            'has_photo': 1,
            'fields': 'photo_max_orig,city,bdate'
        }
        try:
            response = self._make_request('users.search', params)
            return response.get('items', [])
        except Exception:
            return []

    def get_user_photos(self, user_id: int, count: int = 3) -> List[Dict]:
        params = {
            'owner_id': user_id,
            'album_id': 'profile',
            'extended': 1,
            'count': count
        }
        try:
            response = self._make_request('photos.get', params)
            photos = response.get('items', [])
            return sorted(
                photos,
                key=lambda x: x.get('likes', {}).get('count', 0),
                reverse=True
            )[:count]
        except Exception:
            return []

    def calculate_age_from_bdate(self, param):
        pass