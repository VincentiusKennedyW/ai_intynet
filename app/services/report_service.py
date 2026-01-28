"""
Report Service - Integration with Incoming Reports API
Includes customer validation against Ticketing and Intynet systems
"""
import os
import httpx
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ReportService:
    """Handles incoming report creation and customer validation"""
    
    def __init__(self):
        self.api_url = os.getenv("TICKETING_API_URL", "")
        self.api_key = os.getenv("TICKETING_API_KEY", "")
        self.enabled = bool(self.api_url)
        
        if self.enabled:
            logger.info("✅ Ticketing API enabled")
        else:
            logger.info("⚠️ Ticketing API not configured (mock mode)")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get common headers for API requests"""
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    async def search_customer_in_ticketing(self, search_query: str) -> Dict[str, Any]:
        """
        Search customer in Ticketing system
        GET /customers/search?search={query}
        """
        if not self.enabled:
            logger.info(f"📋 MOCK: Would search customer in Ticketing: {search_query}")
            return {
                "success": True,
                "found": False,
                "data": None,
                "mode": "mock"
            }
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.api_url}/customers/search",
                    headers=self._get_headers(),
                    params={"search": search_query}
                )
                response.raise_for_status()
                
                result = response.json()
                customers = result.get("data", [])
                
                logger.info(f"🔍 Ticketing search '{search_query}': found {len(customers)} customer(s)")
                
                return {
                    "success": True,
                    "found": len(customers) > 0,
                    "data": customers[0] if customers else None,
                    "all_results": customers,
                    "mode": "production"
                }
        
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Ticketing search error: {e.response.status_code}")
            return {"success": False, "error": f"API error: {e.response.status_code}"}
        
        except Exception as e:
            logger.error(f"❌ Ticketing search failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def search_customer_in_intynet(self, search_query: str) -> Dict[str, Any]:
        """
        Search customer in Intynet system (via Ticketing API)
        GET /intynet/customers/search?search={query}
        """
        if not self.enabled:
            logger.info(f"📋 MOCK: Would search customer in Intynet: {search_query}")
            return {
                "success": True,
                "found": False,
                "data": None,
                "mode": "mock"
            }
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.api_url}/intynet/customers/search",
                    headers=self._get_headers(),
                    params={"search": search_query}
                )
                response.raise_for_status()
                
                result = response.json()
                customers = result.get("data", [])
                
                logger.info(f"🔍 Intynet search '{search_query}': found {len(customers)} customer(s)")
                
                return {
                    "success": True,
                    "found": len(customers) > 0,
                    "data": customers[0] if customers else None,
                    "all_results": customers,
                    "mode": "production"
                }
        
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Intynet search error: {e.response.status_code}")
            return {"success": False, "error": f"API error: {e.response.status_code}"}
        
        except Exception as e:
            logger.error(f"❌ Intynet search failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_intynet_customer_detail(self, customer_id: str) -> Dict[str, Any]:
        """
        Get customer detail from Intynet
        GET /intynet/customers/detail?id={id}
        """
        if not self.enabled:
            logger.info(f"📋 MOCK: Would get Intynet customer detail: {customer_id}")
            return {
                "success": True,
                "data": {
                    "id": customer_id,
                    "name": "Mock Customer",
                    "references_number": customer_id
                },
                "mode": "mock"
            }
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.api_url}/intynet/customers/detail",
                    headers=self._get_headers(),
                    params={"id": customer_id}
                )
                response.raise_for_status()
                
                result = response.json()
                
                logger.info(f"✅ Got Intynet customer detail: {customer_id}")
                
                return {
                    "success": True,
                    "data": result.get("data"),
                    "mode": "production"
                }
        
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Intynet detail error: {e.response.status_code}")
            return {"success": False, "error": f"API error: {e.response.status_code}"}
        
        except Exception as e:
            logger.error(f"❌ Intynet detail failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_customer_in_ticketing(self, intynet_customer: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create customer in Ticketing system from Intynet data
        POST /customers
        """
        if not self.enabled:
            logger.info(f"📋 MOCK: Would create customer in Ticketing from Intynet data")
            return {
                "success": True,
                "message": "Customer created (mock)",
                "mode": "mock"
            }
        
        # Map Intynet customer data to Ticketing format
        payload = {
            "references_number": intynet_customer.get("references_number") or intynet_customer.get("id"),
            "type": intynet_customer.get("type", "personal"),
            "name": intynet_customer.get("name", "Unknown"),
            "email": intynet_customer.get("email"),
            "phone_number": intynet_customer.get("phone") or intynet_customer.get("phone_number"),
            "nik": intynet_customer.get("nik"),
            "site_city": intynet_customer.get("city") or intynet_customer.get("site_city") or "Balikpapan",
            "site_name": intynet_customer.get("site_name") or intynet_customer.get("name") or "Site",
            "site_address": intynet_customer.get("address") or intynet_customer.get("site_address"),
            "profile_name": intynet_customer.get("profile_name") or intynet_customer.get("package") or "Default",
        }
        
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_url}/customers",
                    headers=self._get_headers(),
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                
                logger.info(f"✅ Customer created in Ticketing from Intynet data")
                
                return {
                    "success": True,
                    "message": result.get("message"),
                    "mode": "production"
                }
        
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Create customer error: {e.response.status_code} - {e.response.text}")
            return {"success": False, "error": f"API error: {e.response.status_code}", "details": e.response.text}
        
        except Exception as e:
            logger.error(f"❌ Create customer failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def validate_customer(self, customer_ref_id: str) -> Dict[str, Any]:
        """
        Validate customer ID with the following flow:
        1. Search in Ticketing system
        2. If not found, search in Intynet
        3. If found in Intynet, create in Ticketing
        4. If not found anywhere, return invalid
        """
        logger.info(f"🔍 Validating customer ID: {customer_ref_id}")
        
        # Step 1: Search in Ticketing
        ticketing_result = await self.search_customer_in_ticketing(customer_ref_id)
        
        if ticketing_result.get("success") and ticketing_result.get("found"):
            customer_data = ticketing_result.get("data")
            logger.info(f"✅ Customer found in Ticketing: {customer_data.get('name', 'Unknown')}")
            return {
                "valid": True,
                "customer_data": customer_data,
                "source": "ticketing",
                "created_in_ticketing": False,
                "message": f"Customer ditemukan: {customer_data.get('name', 'Unknown')}"
            }
        
        # Step 2: Search in Intynet
        logger.info(f"🔍 Not in Ticketing, searching Intynet...")
        intynet_result = await self.search_customer_in_intynet(customer_ref_id)
        
        if intynet_result.get("success") and intynet_result.get("found"):
            intynet_customer = intynet_result.get("data")
            logger.info(f"✅ Customer found in Intynet: {intynet_customer.get('name', 'Unknown')}")
            
            # Step 3: Create in Ticketing
            logger.info(f"📝 Creating customer in Ticketing from Intynet data...")
            create_result = await self.create_customer_in_ticketing(intynet_customer)
            
            if create_result.get("success"):
                logger.info(f"✅ Customer synced to Ticketing")
                return {
                    "valid": True,
                    "customer_data": intynet_customer,
                    "source": "intynet",
                    "created_in_ticketing": True,
                    "message": f"Customer ditemukan di Intynet: {intynet_customer.get('name', 'Unknown')}"
                }
            else:
                # Failed to create but customer exists in Intynet, still valid
                logger.warning(f"⚠️ Failed to sync to Ticketing but customer valid in Intynet")
                return {
                    "valid": True,
                    "customer_data": intynet_customer,
                    "source": "intynet",
                    "created_in_ticketing": False,
                    "message": f"Customer ditemukan: {intynet_customer.get('name', 'Unknown')}"
                }
        
        # Step 4: Not found anywhere
        logger.warning(f"❌ Customer ID not found in any system: {customer_ref_id}")
        return {
            "valid": False,
            "customer_data": None,
            "source": None,
            "created_in_ticketing": False,
            "message": "ID Pelanggan tidak ditemukan di sistem kami"
        }
    
    async def create_report(
        self,
        customer_name: str,
        customer_phone: str,
        description: str,
        customer_id: Optional[str] = None,
        customer_site_id: Optional[str] = None,
        customer_references_number: Optional[str] = None,
        problem_time: Optional[str] = None,
        qiscus_session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create incoming report in ticketing system
        POST /incoming-reports
        """
        payload = {
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "description": description,
            "customer_id": customer_id,
            "customer_site_id": customer_site_id,
            "customer_references_number": customer_references_number,
            "problem_time": problem_time,
            "qiscus_session_id": qiscus_session_id
        }
        
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        
        if not self.enabled:
            logger.info(f"📋 MOCK: Would create incoming report:")
            logger.info(f"   Customer: {customer_name}")
            logger.info(f"   Phone: {customer_phone}")
            logger.info(f"   Ref Number: {customer_references_number}")
            
            mock_id = f"RPT{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            return {
                "success": True,
                "data": {"id": mock_id, "status": "pending"},
                "mode": "mock"
            }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_url}/incoming-reports",
                    headers=self._get_headers(),
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                
                logger.info(f"✅ Incoming report created: {result.get('data', {}).get('id')}")
                
                return {
                    "success": True,
                    "data": result.get("data", {}),
                    "mode": "production"
                }
        
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ API Error: {e.response.status_code} - {e.response.text}")
            return {"success": False, "error": f"API error: {e.response.status_code}"}
        
        except Exception as e:
            logger.error(f"❌ Failed to create report: {e}")
            return {"success": False, "error": str(e)}
