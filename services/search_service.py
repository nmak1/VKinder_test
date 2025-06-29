from typing import List, Dict
from database.manager import DatabaseManager
from services.vk_service import VKService
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self, vk_service: VKService, db_manager: DatabaseManager):
        self.vk = vk_service
        self.db = db_manager

    def find_matches(self, user_id: int, age_from: int, age_to: int) -> List[Dict]:
        user = self.db.get_user(user_id)
        if not user or not all([user.gender, user.city_id]):
            logger.error(f"Incomplete user data for {user_id}")
            return []

        try:
            candidates = self.vk.search_users(
                age_from=age_from,
                age_to=age_to,
                sex=user.gender,
                city_id=user.city_id,
                count=settings.SEARCH_LIMIT
            )

            return [
                candidate for candidate in candidates
                if not self.db.is_in_blacklist(user_id, candidate['id'])
            ]
        except Exception as e:
            logger.error(f"Search failed for {user_id}: {e}")
            return []

    def get_match_photos(self, vk_id: int) -> List[Dict]:
        try:
            return self.vk.get_user_photos(vk_id, settings.PHOTOS_LIMIT)
        except Exception as e:
            logger.error(f"Failed to get photos for {vk_id}: {e}")
            return []