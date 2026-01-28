"""
Ticket Service - Integration with your ticketing system
"""
import os
import httpx
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class TicketService:
    """Handles ticket creation in your ticketing system"""
    
    def __init__(self):
        self.api_url = os.getenv("TICKETING_API_URL", "")
        self.api_key = os.getenv("TICKETING_API_KEY", "")
        self.enabled = bool(self.api_url and self.api_key)
        
        if self.enabled:
            logger.info("✅ Ticketing system integration enabled")
        else:
            logger.warning("⚠️ Ticketing system not configured (mock mode)")
    
    async def create_ticket(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create ticket in ticketing system
        
        Args:
            ticket_data: Dict containing ticket information
            
        Returns:
            Dict with success status and ticket_id
        """
        
        if not self.enabled:
            # Mock mode - just log
            logger.info(f"📋 MOCK: Would create ticket with data:")
            logger.info(f"   Customer: {ticket_data.get('customer_name')}")
            logger.info(f"   Issue: {ticket_data.get('issue_type')}")
            logger.info(f"   Priority: {ticket_data.get('priority')}")
            
            return {
                "success": True,
                "ticket_id": ticket_data.get("ticket_id"),
                "mode": "mock"
            }
        
        # Real API call to your ticketing system
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Map AI data to your ticketing system format
            payload = self._map_ticket_data(ticket_data)
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_url}/tickets",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                
                logger.info(f"✅ Ticket created in ticketing system: {result.get('id')}")
                
                return {
                    "success": True,
                    "ticket_id": result.get("id"),
                    "mode": "production"
                }
        
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Ticketing API Error: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "error": f"API error: {e.response.status_code}"
            }
        
        except Exception as e:
            logger.error(f"❌ Failed to create ticket: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _map_ticket_data(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map AI-generated ticket data to your ticketing system format
        
        CUSTOMIZE THIS based on your ticketing system API
        """
        
        # Example mapping - adjust to your system
        return {
            "title": f"Gangguan: {ticket_data.get('issue_type')}",
            "description": ticket_data.get("description"),
            "customer": {
                "id": ticket_data.get("customer_id"),
                "name": ticket_data.get("customer_name"),
                "phone": ticket_data.get("phone"),
                "address": ticket_data.get("address")
            },
            "category": ticket_data.get("issue_type"),
            "priority": ticket_data.get("priority"),
            "status": "open",
            "source": "whatsapp_ai",
            "created_at": ticket_data.get("created_at", datetime.now().isoformat())
        }
    
    async def get_ticket(self, ticket_id: str) -> Dict[str, Any]:
        """Get ticket details from ticketing system"""
        
        if not self.enabled:
            return {"error": "Ticketing system not configured"}
        
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.api_url}/tickets/{ticket_id}",
                    headers=headers
                )
                response.raise_for_status()
                
                return response.json()
        
        except Exception as e:
            logger.error(f"❌ Failed to get ticket {ticket_id}: {e}")
            return {"error": str(e)}
    
    async def update_ticket(self, ticket_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update ticket in ticketing system"""
        
        if not self.enabled:
            return {"error": "Ticketing system not configured"}
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.patch(
                    f"{self.api_url}/tickets/{ticket_id}",
                    headers=headers,
                    json=updates
                )
                response.raise_for_status()
                
                logger.info(f"✅ Ticket {ticket_id} updated")
                return response.json()
        
        except Exception as e:
            logger.error(f"❌ Failed to update ticket {ticket_id}: {e}")
            return {"error": str(e)}
