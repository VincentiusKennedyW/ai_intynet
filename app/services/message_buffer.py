"""
Message Buffer - Debounce multiple chat bubbles into single message
Prevents multiple AI replies when customer sends multiple messages quickly
"""

import asyncio
import logging
from typing import Dict, Any, Callable
import time

logger = logging.getLogger(__name__)


class MessageBuffer:
    """
    Buffer messages from same customer and process after delay.
    Uses simple approach: only ONE processor task per customer.
    
    Example:
        Customer sends:
            [08:00:01] "Halo"
            [08:00:02] "internet mati"
            [08:00:03] "gimana nih"
        
        After 3 seconds of no new message:
            → Combined: "Halo internet mati gimana nih"
            → Process once, reply once
    """

    def __init__(self, delay_seconds: float = 3.0):
        self.delay = delay_seconds
        self.buffers: Dict[str, Dict[str, Any]] = {}
        self.active_processors: Dict[str, bool] = {}
        
    async def add_message(
        self,
        customer_id: str,
        message: str,
        metadata: Dict[str, Any],
        process_callback: Callable
    ) -> int:
        """Add message to buffer."""
        now = time.time()

        if customer_id in self.buffers:
            # Append to existing buffer
            self.buffers[customer_id]["messages"].append(message)
            self.buffers[customer_id]["last_update"] = now
            count = len(self.buffers[customer_id]["messages"])
            logger.info(f"📝 Appended to buffer: {customer_id} ({count} messages)")
            return count
        else:
            # Create new buffer
            self.buffers[customer_id] = {
                "messages": [message],
                "metadata": metadata,
                "created_at": now,
                "last_update": now,
                "callback": process_callback
            }
            logger.info(f"📝 New buffer created: {customer_id}")
            
            # Start processor ONLY if not already active
            if not self.active_processors.get(customer_id):
                self.active_processors[customer_id] = True
                asyncio.create_task(self._process_when_ready(customer_id))
            
            return 1

    async def _process_when_ready(self, customer_id: str):
        """Wait until no new messages for `delay` seconds, then process"""
        try:
            while True:
                # Wait full delay first
                await asyncio.sleep(self.delay)
                
                # Check if buffer still exists
                if customer_id not in self.buffers:
                    return
                
                # Check if enough time has passed since last message
                last_update = self.buffers[customer_id]["last_update"]
                time_since_last = time.time() - last_update
                
                if time_since_last >= self.delay - 0.1:  # Small tolerance
                    # Ready to process - no new messages for delay seconds
                    break
                # else: new message arrived, loop again
            
            # Get and clear buffer atomically
            if customer_id not in self.buffers:
                return
                
            buffer = self.buffers.pop(customer_id, None)
            if not buffer:
                return
            
            # Combine all messages
            combined_message = " ".join(buffer["messages"])
            message_count = len(buffer["messages"])
            
            logger.info(
                f"⏰ Processing {message_count} message(s) from {customer_id}: "
                f"'{combined_message[:50]}{'...' if len(combined_message) > 50 else ''}'"
            )

            # Call the process callback
            await buffer["callback"](
                customer_id=customer_id,
                message=combined_message,
                metadata=buffer["metadata"]
            )
            
        except Exception as e:
            logger.error(f"❌ Buffer processing error: {e}")
            self.buffers.pop(customer_id, None)
        finally:
            self.active_processors.pop(customer_id, None)

    def get_pending_count(self, customer_id: str) -> int:
        if customer_id in self.buffers:
            return len(self.buffers[customer_id]["messages"])
        return 0

    def clear(self, customer_id: str):
        self.buffers.pop(customer_id, None)
        self.active_processors.pop(customer_id, None)

    def clear_all(self):
        self.buffers.clear()
        self.active_processors.clear()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "delay_seconds": self.delay,
            "active_buffers": len(self.buffers),
            "pending_customers": list(self.buffers.keys())
        }
