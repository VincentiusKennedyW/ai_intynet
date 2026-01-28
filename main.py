"""
ISP Customer Support AI Service - PRODUCTION VERSION
Handles Qiscus webhook, conversational AI, and ticket creation
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import json
import hmac
import hashlib
from datetime import datetime
import os
import httpx
import logging
from contextlib import asynccontextmanager

from ai_handler import AIHandler
from session_manager import SessionManager
from ticket_service import TicketService

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
QISCUS_SECRET = os.getenv("QISCUS_SECRET", "")
QISCUS_APP_ID = os.getenv("QISCUS_APP_ID", "")
QISCUS_SECRET_KEY = os.getenv("QISCUS_SECRET_KEY", "")
QISCUS_API_URL = os.getenv(
    "QISCUS_SEND_MESSAGE_URL", "https://multichannel.qiscus.com/api/v1"
)
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Initialize components on startup
session_manager = None
ai_handler = None
ticket_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global session_manager, ai_handler, ticket_service

    # Startup
    logger.info("🚀 Starting ISP AI Support Service...")
    logger.info(f"📍 Environment: {ENVIRONMENT}")

    session_manager = SessionManager()
    ai_handler = AIHandler()
    ticket_service = TicketService()

    logger.info("✅ All services initialized")

    yield

    # Shutdown
    logger.info("🛑 Shutting down ISP AI Support Service...")


app = FastAPI(
    title="ISP AI Support",
    version="2.0.0",
    description="Production-ready AI customer support system",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# def verify_qiscus_signature(signature: str, body: bytes) -> bool:
#     """Verify Qiscus webhook signature"""
#     if ENVIRONMENT == "development" and not QISCUS_SECRET:
#         logger.warning("⚠️ Signature verification SKIPPED (development mode)")
#         return True

#     if not QISCUS_SECRET:
#         logger.error("❌ QISCUS_SECRET not configured")
#         return False

#     computed = hmac.new(
#         QISCUS_SECRET.encode(),
#         body,
#         hashlib.sha256
#     ).hexdigest()

#     is_valid = hmac.compare_digest(signature, computed)

#     if not is_valid:
#         logger.warning(f"⚠️ Invalid signature received")

#     return is_valid


async def send_qiscus_message(room_id: str, message: str, customer_id: str) -> bool:
    """Send message back to Qiscus room"""

    if not QISCUS_APP_ID or not QISCUS_SECRET_KEY:
        logger.warning(f"⚠️ Qiscus API credentials not configured")
        logger.info(f"   Would send to room {room_id}: {message[:100]}...")
        return False

    url = f"{QISCUS_API_URL}"

    headers = {
        "Qiscus-App-Id": QISCUS_APP_ID,
        "Qiscus-Secret-Key": QISCUS_SECRET_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "to": customer_id,
        "type": "text",
        "text": {"body": message},
        "room_id": room_id,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()

            logger.info(f"✅ Message sent to Qiscus room {room_id}")
            return True

    except httpx.HTTPStatusError as e:
        logger.error(
            f"❌ Qiscus API Error: {e.response.status_code} - {e.response.text}"
        )
        return False

    except Exception as e:
        logger.error(f"❌ Failed to send to Qiscus: {e}")
        return False


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "ISP AI Support",
        "version": "2.0.0",
        "status": "running",
        "environment": ENVIRONMENT,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    redis_status = session_manager.check_health() if session_manager else False

    qiscus_configured = bool(QISCUS_APP_ID and QISCUS_SECRET_KEY)

    return {
        "status": "healthy" if redis_status else "degraded",
        "components": {
            "api": "ok",
            "redis": "ok" if redis_status else "error",
            "ai": "ok",
            "qiscus": "configured" if qiscus_configured else "not_configured",
        },
        "environment": ENVIRONMENT,
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/webhook/qiscus")
async def qiscus_webhook(request: Request):
    """
    Main webhook endpoint for Qiscus messages
    Receives customer messages and processes with AI
    """
    try:
        # Get raw body
        body = await request.body()

        # Verify signature
        signature = request.headers.get("qiscus-signature-key", "")

        # if ENVIRONMENT == "production":
        #     if not verify_qiscus_signature(signature, body):
        #         raise HTTPException(status_code=401, detail="Invalid signature")
        # else:
        #     logger.warning("⚠️ Signature verification skipped (development mode)")

        # Parse payload
        data = json.loads(body)

        # Handle array payload
        if isinstance(data, list) and len(data) > 0:
            data = data[0]

        # Extract message data - handle both structures
        if "body" in data:
            payload = data.get("body", {}).get("payload", {})
        else:
            payload = data.get("payload", {})

        if not payload:
            logger.warning("⚠️ No payload found in webhook")
            return JSONResponse(
                status_code=200, content={"status": "ignored", "reason": "no payload"}
            )

        message_data = payload.get("message", {})
        from_data = payload.get("from", {})
        room_data = payload.get("room", {})

        # Extract key information
        customer_id = from_data.get("email", "")
        customer_name = from_data.get("name", "Customer")
        message_text = message_data.get("text", "")
        room_id = str(room_data.get("id", ""))
        message_type = message_data.get("type", "text")

        # Only process text messages
        if message_type != "text" or not message_text:
            return JSONResponse(
                status_code=200,
                content={"status": "ignored", "reason": "non-text message"},
            )

        # Log incoming message
        logger.info(f"📨 Message from {customer_name} ({customer_id}): {message_text}")

        # Get or create session
        session = session_manager.get_session(customer_id)

        # Process with AI
        ai_response = await ai_handler.process_message(
            customer_id=customer_id,
            customer_name=customer_name,
            message=message_text,
            session=session,
        )

        # Update session
        session_manager.update_session(
            customer_id=customer_id, session_data=ai_response["session"]
        )

        # Log AI response
        logger.info(f"🤖 AI Reply: {ai_response['reply'][:100]}...")
        logger.info(f"📊 State: {ai_response['session']['state']}")

        # If ticket created, save to ticketing system
        if ai_response.get("ticket_created"):
            ticket_data = ai_response.get("ticket_data")
            ticket_result = await ticket_service.create_ticket(ticket_data)

            if ticket_result.get("success"):
                logger.info(f"🎫 Ticket created: {ticket_result.get('ticket_id')}")
            else:
                logger.error(
                    f"❌ Failed to create ticket: {ticket_result.get('error')}"
                )

        # Send response back to Qiscus
        send_success = await send_qiscus_message(
            room_id, ai_response["reply"], customer_id
        )

        # Prepare response
        response_data = {
            "status": "success",
            "customer_id": customer_id,
            "room_id": room_id,
            "message_sent": send_success,
            "state": ai_response["session"]["state"],
            "ticket_created": ai_response.get("ticket_created", False),
        }

        return JSONResponse(status_code=200, content=response_data)

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ Error processing webhook: {str(e)}", exc_info=True)

        return JSONResponse(
            status_code=200,  # Return 200 to avoid Qiscus retries
            content={"status": "error", "message": "Internal processing error"},
        )


@app.get("/sessions")
async def list_sessions():
    """List all active sessions (admin only)"""
    sessions = session_manager.get_all_sessions()
    return {
        "count": len(sessions),
        "sessions": sessions,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/session/{customer_id}")
async def get_session(customer_id: str):
    """Get session data for a customer"""
    session = session_manager.get_session(customer_id)
    return {
        "customer_id": customer_id,
        "session": session,
        "timestamp": datetime.now().isoformat(),
    }


@app.delete("/session/{customer_id}")
async def reset_session(customer_id: str):
    """Reset session for a customer"""
    session_manager.delete_session(customer_id)
    logger.info(f"🔄 Session reset for {customer_id}")
    return {
        "status": "success",
        "message": f"Session reset for {customer_id}",
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/test/message")
async def test_message(
    customer_id: str, message: str, customer_name: str = "Test Customer"
):
    """Test endpoint to simulate messages without Qiscus"""
    session = session_manager.get_session(customer_id)

    ai_response = await ai_handler.process_message(
        customer_id=customer_id,
        customer_name=customer_name,
        message=message,
        session=session,
    )

    session_manager.update_session(
        customer_id=customer_id, session_data=ai_response["session"]
    )

    return {
        "reply": ai_response["reply"],
        "state": ai_response["session"]["state"],
        "collected_data": ai_response["session"].get("collected_data"),
        "ticket_created": ai_response.get("ticket_created", False),
        "ticket_data": ai_response.get("ticket_data"),
    }


@app.get("/stats")
async def get_stats():
    """Get system statistics"""
    sessions = session_manager.get_all_sessions()

    # Calculate stats
    total_sessions = len(sessions)
    states_count = {}

    for customer_id, session in sessions.items():
        state = session.get("state", "unknown")
        states_count[state] = states_count.get(state, 0) + 1

    return {
        "total_active_sessions": total_sessions,
        "states_distribution": states_count,
        "environment": ENVIRONMENT,
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
