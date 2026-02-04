"""
ISP AI Customer Support - Production Ready
==========================================
Handles: Product inquiries, Complaint troubleshooting
Features: Message buffering, Session management, Qiscus integration
"""

import json
import os
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.services.ai_handler import AIHandler
from app.services.session_manager import SessionManager
from app.services.message_buffer import MessageBuffer
from app.services.qiscus_service import QiscusService

# ============ LOGGING ============

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
MESSAGE_BUFFER_DELAY = float(os.getenv("MESSAGE_BUFFER_DELAY", "10.0")) 

# ============ COMPONENTS ============

session_manager: SessionManager = None
ai_handler: AIHandler = None
message_buffer: MessageBuffer = None
qiscus_service: QiscusService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources"""
    global session_manager, ai_handler, message_buffer, qiscus_service

    logger.info("🚀 Starting ISP AI Support Service...")

    # Initialize components
    session_manager = SessionManager()
    ai_handler = AIHandler()
    message_buffer = MessageBuffer(delay_seconds=MESSAGE_BUFFER_DELAY)
    qiscus_service = QiscusService()

    # Health check
    redis_ok = session_manager.check_health()
    logger.info(
        f"{'✅' if redis_ok else '⚠️'} Redis: {'connected' if redis_ok else 'using memory fallback'}"
    )
    logger.info(f"✅ Environment: {ENVIRONMENT}")
    logger.info(f"✅ Buffer delay: {MESSAGE_BUFFER_DELAY}s")

    yield

    logger.info("👋 Shutting down...")


# ============ APP ============

app = FastAPI(
    title="ISP AI Support",
    version="2.0.0",
    description="AI-powered customer support for Intynet ISP",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ HELPER FUNCTIONS ============

def is_complaint_or_report_related(message: str) -> bool:
    """Check if message is related to complaint/report"""
    msg = message.lower()
    
    # Complaint/issue keywords - comprehensive list
    complaint_keywords = [
        # Status & progress
        "laporan", "gimana", "bagaimana", "sudah", "udah", "belum", 
        "progress", "status", "proses", "ditangani", "kapan",
        # Internet issues  
        "gangguan", "mati", "lambat", "putus", "tidak bisa", "gak bisa",
        "ga bisa", "gabisa", "gk bisa", "error", "masalah", "kendala",
        "trouble", "down", "lelet", "lemot", "lag", "disconnect",
        "los", "merah", "rusak", "wifi", "internet", "koneksi",
        # Expressions of frustration
        "masih", "tetap", "tetep", "sama aja", "gk usah", "juga"
    ]
    
    # Check for any complaint keyword
    for kw in complaint_keywords:
        if kw in msg:
            return True
    
    return False


def is_acknowledgment(message: str) -> bool:
    """Check if message is just an acknowledgment (ok, baik, siap, etc)"""
    ack_responses = [
        "ok", "oke", "okey", "okay", "baik", "baiklah", "siap", "sip", 
        "iya", "ya", "yaa", "yup", "yep", "thanks", "makasih", "terima kasih",
        "noted", "good", "mantap", "aman", "done", "sudah", "udah"
    ]
    message_clean = message.lower().strip().rstrip(".!,")
    
    # Check if message is short acknowledgment
    if message_clean in ack_responses:
        return True
    
    # Check if starts with ack and is short
    words = message_clean.split()
    if len(words) <= 3 and words[0] in ack_responses:
        return True
    
    return False


# ============ MESSAGE PROCESSOR ============

async def process_buffered_message(
    customer_id: str, message: str, metadata: Dict[str, Any]
):
    """Process combined messages after buffer delay"""
    customer_name = metadata.get("customer_name", "Customer")
    room_id = metadata.get("room_id")

    logger.info(f"🤖 Processing: '{message[:50]}...' from {customer_name}")

    # Get session
    session = session_manager.get_session(customer_id)

    # Handle acknowledgment messages (ok, baik, siap, etc)
    if is_acknowledgment(message):
        logger.info("👍 Acknowledgment message - sending simple response")
        if room_id:
            await qiscus_service.send_message(
                room_id=room_id,
                message="Siap kak!",
                customer_id=customer_id,
            )
        return

    # ===== CHECK TAG STATUS FIRST =====
    has_tag = False
    is_expired = False
    tag_id = None
    
    if room_id:
        has_tag, is_expired, tag_id = await qiscus_service.check_escalated_tag(room_id)
        logger.info(f"🏷️ Tag check: has_tag={has_tag}, is_expired={is_expired}")

    # If tag expired (> 2 days), auto-remove and allow conversation
    if has_tag and is_expired and tag_id:
        logger.info("⏰ Tag expired (admin forgot) → auto-removing tag")
        await qiscus_service.remove_room_tag(room_id, tag_id)
        has_tag = False
        session = {"state": "detect", "message_count": 0}
        session_manager.update_session(customer_id, session)

    # ===== INTERCEPT IF HAS PENDING REPORT =====
    # If has tag (not expired), ANY complaint-related message gets intercepted
    if has_tag and not is_expired:
        # Check if message is about the pending report
        is_report_related = is_complaint_or_report_related(message)
        logger.info(f"📋 Has pending report. Message related to report: {is_report_related}")
        
        if is_report_related:
            logger.info("🚫 Intercepting - sending pending status")
            await qiscus_service.send_message(
                room_id=room_id,
                message="Halo kak! 👋\n\nLaporan kakak masih dalam proses penanganan oleh tim teknis kami. Mohon ditunggu ya kak, tim kami akan segera menghubungi kakak untuk tindak lanjut.\n\nTerima kasih atas kesabarannya 🙏",
                customer_id=customer_id,
            )
            return
        else:
            # Non-complaint topic allowed, but mark session
            logger.info("📋 Non-complaint topic - allowing AI to respond")
            if "collected_data" not in session:
                session["collected_data"] = {}
            session["collected_data"]["has_pending_report"] = True

    # If no pending report and session was escalated → reset completely
    if not has_tag and session.get("state") == "escalated":
        logger.info("✅ Tag removed by admin → resetting session")
        session = {"state": "detect", "message_count": 0}
        session_manager.update_session(customer_id, session)

    # Process with AI
    ai_response = await ai_handler.process_message(
        customer_id=customer_id,
        customer_name=customer_name,
        message=message,
        session=session,
    )

    new_session = ai_response["session"]

    # If escalated (form submitted), add tag
    if ai_response.get("ai_stop"):
        logger.info("🛑 AI STOP - Escalated to human agent")

        if room_id:
            await qiscus_service.mark_ai_escalated(room_id)

        session_manager.update_session(customer_id, new_session)
        return

    session_manager.update_session(customer_id, new_session)

    # Send reply
    if room_id and ai_response.get("reply"):
        await qiscus_service.send_message(
            room_id=room_id, message=ai_response["reply"], customer_id=customer_id
        )


# ============ WEBHOOK ENDPOINT ============


@app.post("/webhook/qiscus")
async def qiscus_webhook(request: Request):
    """
    Handle incoming Qiscus webhook.
    Messages are buffered to handle multiple bubbles.
    """
    try:
        body = await request.body()
        data = json.loads(body)

        # Handle array payload
        if isinstance(data, list) and len(data) > 0:
            data = data[0]

        # Extract payload
        payload = data.get("payload", {})
        if not payload:
            payload = data.get("body", {}).get("payload", {})

        if not payload:
            return JSONResponse({"status": "ignored", "reason": "no_payload"})

        # Extract message info
        from_data = payload.get("from", {})
        room_data = payload.get("room", {})
        message_data = payload.get("message", {})

        customer_id = from_data.get("email", "")
        customer_name = from_data.get("name", "Customer")
        message_text = message_data.get("text", "")
        room_id = str(room_data.get("id", ""))
        message_type = message_data.get("type", "text")

        # Only process text messages
        if message_type != "text" or not message_text:
            return JSONResponse({"status": "ignored", "reason": "non_text"})

        logger.info(f"📨 From {customer_name} ({customer_id}): {message_text[:50]}...")

        # Add to buffer
        pending = await message_buffer.add_message(
            customer_id=customer_id,
            message=message_text,
            metadata={
                "customer_name": customer_name,
                "room_id": room_id,
            },
            process_callback=process_buffered_message,
        )

        logger.info(f"📝 Buffered ({pending} pending)")

        return JSONResponse({"status": "buffered", "pending_messages": pending})

    except Exception as e:
        logger.error(f"❌ Webhook error: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,  # Return 200 to prevent Qiscus retries
            content={"status": "error", "message": str(e)},
        )


# ============ API ENDPOINTS ============


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "redis": "connected" if session_manager.check_health() else "memory",
        "environment": ENVIRONMENT,
    }


@app.get("/stats")
async def stats():
    """System statistics"""
    session_stats = session_manager.get_stats()
    return {
        "sessions": session_stats,
        "buffer": {
            "delay_seconds": message_buffer.delay,
            "active_buffers": len(message_buffer.buffers),
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/sessions")
async def get_sessions():
    """Get all active sessions"""
    return session_manager.get_all_sessions()


@app.get("/session/{customer_id}")
async def get_session(customer_id: str):
    """Get session for a customer"""
    return session_manager.get_session(customer_id)


@app.delete("/session/{customer_id}")
async def delete_session(customer_id: str):
    """Reset customer session"""
    message_buffer.clear(customer_id)
    success = session_manager.delete_session(customer_id)
    return {"status": "deleted" if success else "not_found"}


# ============ TEST ENDPOINTS ============


@app.post("/test/chat")
async def test_chat(
    customer_id: str, 
    message: str, 
    customer_name: str = "Test Customer",
    room_id: str = None
):
    """
    Test endpoint - direct processing without buffer.
    Provide room_id to test tag-based logic.
    """
    session = session_manager.get_session(customer_id)

    # Check if room has escalated tag (if room_id provided)
    has_pending_report = False
    if room_id:
        has_pending_report = await qiscus_service.has_escalated_tag(room_id)

    # If has pending report and asking about complaint → reply pending
    if has_pending_report and is_complaint_topic(message):
        return {
            "reply": "Laporan kakak masih dalam proses penanganan oleh tim teknis kami. Mohon ditunggu ya kak 🙏",
            "state": "escalated",
            "ai_stop": True,
            "has_pending_report": True,
        }

    # If has pending report but asking other topic → allow conversation
    if has_pending_report and session.get("state") == "escalated":
        session["state"] = "detect"

    # If no pending report and session was escalated → reset
    if not has_pending_report and session.get("state") == "escalated":
        session = {"state": "detect", "message_count": 0}
        session_manager.update_session(customer_id, session)

    ai_response = await ai_handler.process_message(
        customer_id=customer_id,
        customer_name=customer_name,
        message=message,
        session=session,
    )

    new_session = ai_response["session"]

    # If escalated, add tag (if room_id provided)
    if ai_response.get("ai_stop"):
        logger.info("🛑 AI STOP - Form submitted")
        if room_id:
            await qiscus_service.mark_ai_escalated(room_id)

    session_manager.update_session(customer_id, new_session)

    return {
        "reply": ai_response.get("reply"),
        "state": new_session["state"],
        "ai_stop": ai_response.get("ai_stop", False),
        "has_pending_report": has_pending_report,
    }


@app.get("/test/check-tag/{room_id}")
async def test_check_tag(room_id: str):
    """Test checking if room has escalated tag"""
    has_tag = await qiscus_service.has_escalated_tag(room_id)
    tags = await qiscus_service.get_room_tags(room_id)
    return {
        "room_id": room_id,
        "has_escalated_tag": has_tag,
        "all_tags": tags,
    }


@app.post("/test/add-tag/{room_id}")
async def test_add_tag(room_id: str):
    """Test adding escalated tag to room"""
    success = await qiscus_service.mark_ai_escalated(room_id)
    return {"success": success, "room_id": room_id}
