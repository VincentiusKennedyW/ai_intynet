"""
Qiscus Service - Handle all Qiscus API interactions
"""

import os
import logging
import httpx
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Configuration
QISCUS_APP_ID = os.getenv("QISCUS_APP_ID", "")
QISCUS_SECRET_KEY = os.getenv("QISCUS_SECRET_KEY", "")
QISCUS_BASE_URL = os.getenv("QISCUS_BASE_URL")
QISCUS_SEND_URL = os.getenv("QISCUS_SEND_MESSAGE_URL")
TAG_ID_AI_ESCALATED = os.getenv("TAG_ID_AI_ESCALATED", "0")
TAG_EXPIRY_DAYS = int(os.getenv("TAG_EXPIRY_DAYS", "2"))


class QiscusService:
    """Handles all Qiscus API operations"""

    TAG_AI_ESCALATED = "Direspon AI"

    def __init__(self):
        self.app_id = QISCUS_APP_ID
        self.secret_key = QISCUS_SECRET_KEY
        self.base_url = QISCUS_BASE_URL
        self.send_url = QISCUS_SEND_URL
        self.tag_id_escalated = TAG_ID_AI_ESCALATED
        self.tag_expiry_days = TAG_EXPIRY_DAYS

    def _get_headers(self) -> dict:
        """Get common headers for Qiscus API"""
        return {
            "Qiscus-App-Id": self.app_id,
            "Qiscus-Secret-Key": self.secret_key,
        }

    async def send_message(self, room_id: str, message: str, customer_id: str) -> bool:
        """Send message to Qiscus room"""
        if not message:
            logger.info("📭 No message to send")
            return True

        try:
            headers = {
                **self._get_headers(),
                "Content-Type": "application/json",
            }

            payload = {
                "to": customer_id,
                "type": "text",
                "text": {"body": message},
                "room_id": room_id,
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.send_url, json=payload, headers=headers
                )

                if response.status_code == 200:
                    logger.info(f"✅ Message sent to room {room_id}")
                    return True
                else:
                    logger.error(
                        f"❌ Qiscus error: {response.status_code} - {response.text}"
                    )
                    return False

        except Exception as e:
            logger.error(f"❌ Failed to send message: {e}")
            return False

    async def get_room_tags(self, room_id: str) -> List[Dict[str, Any]]:
        """
        Get all tags for a room.
        Returns list of tags: [{"id": 123, "name": "Tag Name", "room_tag_created": "..."}, ...]
        """
        try:
            url = f"{self.base_url}/room_tags/{room_id}"
            headers = self._get_headers()

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    tags = data.get("data", [])
                    logger.info(f"🏷️ Room {room_id} has {len(tags)} tags")
                    return tags
                else:
                    logger.error(f"❌ Failed to get tags: {response.status_code}")
                    return []

        except Exception as e:
            logger.error(f"❌ Error getting tags: {e}")
            return []

    async def check_escalated_tag(self, room_id: str) -> Tuple[bool, bool, Optional[str]]:
        """
        Check if room has the escalated tag and if it's expired.
        
        Returns:
            Tuple of (has_tag, is_expired, tag_id)
            - has_tag: True if escalated tag exists
            - is_expired: True if tag is older than TAG_EXPIRY_DAYS
            - tag_id: The tag ID for removal (if needed)
        """
        tags = await self.get_room_tags(room_id)
        
        for tag in tags:
            tag_id = str(tag.get("id", ""))
            tag_name = tag.get("name", "")
            
            # Check by ID or name
            if tag_id == str(self.tag_id_escalated) or tag_name == self.TAG_AI_ESCALATED:
                # Check if expired (older than X days)
                created_at_str = tag.get("room_tag_created", "")
                is_expired = False
                
                if created_at_str:
                    try:
                        # Parse: "2024-10-22T04:42:30"
                        created_at = datetime.fromisoformat(created_at_str)
                        expiry_date = created_at + timedelta(days=self.tag_expiry_days)
                        is_expired = datetime.now() > expiry_date
                        
                        if is_expired:
                            logger.info(f"🏷️ Tag expired! Created: {created_at_str}, Expiry: {self.tag_expiry_days} days")
                    except Exception as e:
                        logger.error(f"❌ Error parsing tag date: {e}")
                
                logger.info(f"🏷️ Room {room_id} has escalated tag (expired: {is_expired})")
                return True, is_expired, tag_id
        
        logger.info(f"🏷️ Room {room_id} has NO escalated tag")
        return False, False, None

    async def has_escalated_tag(self, room_id: str) -> bool:
        """Simple check if room has escalated tag (ignoring expiry)"""
        has_tag, _, _ = await self.check_escalated_tag(room_id)
        return has_tag

    async def add_room_tag(self, room_id: str, tag: str) -> bool:
        """Add tag to a Qiscus room."""
        try:
            url = f"{self.base_url}/room_tags/{room_id}"
            headers = self._get_headers()

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    url, headers=headers, data={"tag": tag}
                )

                if response.status_code == 200:
                    logger.info(f"🏷️ Tag '{tag}' added to room {room_id}")
                    return True
                else:
                    logger.error(
                        f"❌ Failed to add tag: {response.status_code} - {response.text}"
                    )
                    return False

        except Exception as e:
            logger.error(f"❌ Error adding tag: {e}")
            return False

    async def remove_room_tag(self, room_id: str, tag_id: str) -> bool:
        """Remove tag from a Qiscus room by tag ID"""
        try:
            url = f"{self.base_url}/room_tags/{room_id}/{tag_id}"
            headers = self._get_headers()

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.delete(url, headers=headers)

                if response.status_code == 200:
                    logger.info(f"🏷️ Tag ID {tag_id} removed from room {room_id}")
                    return True
                else:
                    logger.error(f"❌ Failed to remove tag: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"❌ Error removing tag: {e}")
            return False

    async def mark_ai_escalated(self, room_id: str) -> bool:
        """Mark room as escalated (needs human follow-up)"""
        return await self.add_room_tag(room_id, self.TAG_AI_ESCALATED)


# Singleton instance
qiscus_service = QiscusService()
