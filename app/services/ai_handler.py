"""
AI Handler - Intynet Customer Service Bot
==========================================
Smart state machine with AI-based intent detection.
NO keyword matching - uses LLM to classify intent dynamically.

State Flow (LOCKED SEQUENCE):
    DETECT → PRODUCT_INFO | TROUBLESHOOT
    TROUBLESHOOT → FORM_SENT → ESCALATED
    
Any state can transition back to DETECT for new topics.

Author: Intynet Team
Version: 3.0.0
"""

import os
import json
import logging
from typing import Dict, Any, Tuple
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))


class AIHandler:
    """AI-powered customer service with smart state machine"""

    # ============ STATES ============
    STATE_DETECT = "detect"              # Initial - waiting for topic
    STATE_PRODUCT_INFO = "product_info"  # Answering product questions
    STATE_TROUBLESHOOT = "troubleshoot"  # Giving troubleshooting steps
    STATE_FORM_SENT = "form_sent"        # Form sent, waiting for form data
    STATE_ESCALATED = "escalated"        # Escalated to human

    # ============ INTENTS ============
    INTENT_PRODUCT = "product"           # Asking about products/pricing
    INTENT_COMPLAINT = "complaint"       # Reporting internet issues
    INTENT_STATUS = "status"             # Asking about report status
    INTENT_RESOLVED = "resolved"         # Saying problem is fixed
    INTENT_NOT_RESOLVED = "not_resolved" # Saying problem persists
    INTENT_FORM_DATA = "form_data"       # Submitting form information
    INTENT_GREETING = "greeting"         # Hi, hello, etc
    INTENT_THANKS = "thanks"             # Thank you, ok, etc
    INTENT_OTHER = "other"               # Unrelated topics

    # ============ STATE TRANSITIONS ============
    # Flexible cross-state transitions allowed
    # Core flow: DETECT → TROUBLESHOOT → FORM_SENT → ESCALATED
    # But can switch topics anytime (except form_sent which locks until form/topic change)
    VALID_TRANSITIONS = {
        STATE_DETECT: [STATE_PRODUCT_INFO, STATE_TROUBLESHOOT, STATE_DETECT],
        STATE_PRODUCT_INFO: [STATE_DETECT, STATE_TROUBLESHOOT, STATE_PRODUCT_INFO],
        STATE_TROUBLESHOOT: [STATE_FORM_SENT, STATE_DETECT, STATE_TROUBLESHOOT, STATE_PRODUCT_INFO],
        STATE_FORM_SENT: [STATE_ESCALATED, STATE_DETECT, STATE_FORM_SENT, STATE_PRODUCT_INFO, STATE_TROUBLESHOOT],
        STATE_ESCALATED: [STATE_DETECT, STATE_ESCALATED, STATE_PRODUCT_INFO, STATE_TROUBLESHOOT],
    }

    # ============ KNOWLEDGE BASE ============
    KNOWLEDGE_BASE = """
## LAYANAN INTYNET

Intynet adalah layanan internet fiber-optic dengan:
- ✅ Unlimited tanpa kuota & FUP
- ✅ Kecepatan stabil sesuai paket
- ✅ Modem + WiFi dipinjamkan GRATIS
- ✅ TV Transvision untuk paket tertentu
- ✅ Support 24 jam
- 💰 Instalasi normal: Rp 150.000 (PROMO: GRATIS!)

## PAKET INTERNET RUMAH

| Paket   | Speed    | Harga/bulan  |
|---------|----------|--------------|
| Starter | 10 Mbps  | Rp 149.000   |
| Smart   | 20 Mbps  | Rp 199.000   |
| Family  | 30 Mbps  | Rp 249.000   |
| Maxima  | 50 Mbps  | Rp 299.000   |
| Ultima  | 100 Mbps | Rp 380.000   |

*Harga belum termasuk PPN 11% dan admin Rp 5.000*
*Paket 30/50/100 Mbps gratis 40 channel TV Transvision!*

## PAKET BISNIS
- Bandwidth: 50–200 Mbps
- IP privat tersedia
- Harga konsultasi lebih lanjut

## KEBIJAKAN
- Sistem prabayar (bayar dulu baru pakai)
- Invoice terbit tgl 1, jatuh tempo tgl 20
- Minimal berlangganan 12 bulan
- Pemasangan ± 1-3 hari kerja
- Modem wajib dikembalikan jika berhenti
- Maksimal tarikan kabel 250m
"""

    PROMO_TEXT = """
📢 *PROMO SAAT INI:*

• Bebas biaya instalasi!
• Sistem prabayar - bayar setelah aktivasi
• Paket 30/50/100 Mbps dapat 40 channel TV Transvision GRATIS
• Harga belum termasuk PPN 11% dan admin Rp 5.000
• Pemasangan ± 1-3 hari kerja jika lokasi tercover

Boleh dibantu *share lokasi* kak, agar bisa kami cek apakah tercover jaringan kami 📍
"""

    TROUBLESHOOT_STEPS = """
**Langkah Troubleshooting:**
1. Restart modem - cabut kabel power, tunggu 30 detik, colok lagi
2. Pastikan semua kabel (power, LAN, fiber) terpasang dengan baik
3. Cek lampu modem:
   - Power, LAN, PON harus hijau ✅
   - Jika LOS merah = ada gangguan fiber
4. Jika pakai WiFi, coba dekatkan device ke modem
"""

    COMPLAINT_FORM = """Baik kak, untuk proses penanganan lebih lanjut, mohon isi data berikut:

*Copy dan lengkapi:*

```
ID Pelanggan: 
Nama: 
Alamat: 
Kendala: 
Sejak Kapan: 
```

Setelah diisi, langsung kirim ke chat ini dan tim kami akan segera menindaklanjuti 🙏"""

    def __init__(self):
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # ============ AI INTENT CLASSIFIER ============

    async def _classify_intent(self, message: str, current_state: str, context: str = "") -> str:
        """
        Use AI to classify user intent based on message and current state.
        NO keyword matching - fully dynamic understanding.
        """
        # Build state-aware prompt
        state_hints = {
            self.STATE_DETECT: "User baru memulai atau topik baru.",
            self.STATE_PRODUCT_INFO: "User sedang bertanya tentang produk.",
            self.STATE_TROUBLESHOOT: "User baru dapat langkah troubleshooting, tunggu hasil coba.",
            self.STATE_FORM_SENT: "User sudah diminta isi form laporan. Cek apakah mengirim data form.",
            self.STATE_ESCALATED: "User punya laporan aktif yang sedang diproses tim."
        }

        system_prompt = f"""Kamu adalah intent classifier untuk chatbot ISP.

CURRENT STATE: {current_state}
STATE CONTEXT: {state_hints.get(current_state, '')}
CONVERSATION CONTEXT: {context}

Klasifikasikan pesan user ke SATU intent berikut:
- "product": Tanya produk, harga, paket, instalasi, langganan, promo
- "complaint": Lapor masalah internet (lambat, mati, putus, error, gangguan)
- "status": Tanya status laporan/tiket/progress penanganan
- "resolved": Bilang masalah sudah teratasi/normal/bekerja lagi
- "not_resolved": Bilang masalah masih ada/belum beres setelah troubleshoot
- "form_data": Mengirim data form (ada ID pelanggan, nama, alamat, kendala)
- "greeting": Sapaan (halo, hi, selamat pagi, dll)
- "thanks": Terima kasih, ok, baik, siap, iya, noted
- "other": Tidak terkait layanan ISP

ATURAN PENTING STATE:
1. STATE "form_sent": Jika pesan berisi ID/nama/alamat/kendala → "form_data"
2. STATE "troubleshoot": 
   - Respon negatif (masih bermasalah, belum, tetap, ga bisa) → "not_resolved"
   - Respon positif (sudah normal, bisa, lancar) → "resolved"
   - Pertanyaan baru → sesuai topik
3. Pesan singkat "ok", "baik", "siap", "oke", "ya" → "thanks"
4. Tanya "gimana laporan", "sudah ditangani" → "status"

PENTING: Pahami MAKSUD pesan, bukan hanya kata-kata. 
Contoh: "wifi saya kok jadi begini ya" = complaint (bukan product)
Contoh: "oh gitu, oke deh" = thanks (bukan resolved)

Jawab HANYA dengan satu kata intent, tidak ada penjelasan."""

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.1,
                max_tokens=20
            )
            intent = response.choices[0].message.content.strip().lower()
            
            # Validate intent
            valid_intents = [
                self.INTENT_PRODUCT, self.INTENT_COMPLAINT, self.INTENT_STATUS,
                self.INTENT_RESOLVED, self.INTENT_NOT_RESOLVED, self.INTENT_FORM_DATA,
                self.INTENT_GREETING, self.INTENT_THANKS, self.INTENT_OTHER
            ]
            
            if intent not in valid_intents:
                logger.warning(f"Unknown intent '{intent}', defaulting to 'other'")
                return self.INTENT_OTHER
            
            logger.info(f"🎯 Intent classified: {intent} (state: {current_state})")
            return intent
            
        except Exception as e:
            logger.error(f"Intent classification error: {e}")
            return self.INTENT_OTHER

    # ============ AI RESPONSE GENERATOR ============

    async def _generate_response(
        self, 
        instruction: str, 
        user_message: str, 
        include_kb: bool = True,
        conversation_context: str = ""
    ) -> str:
        """Generate AI response using OpenAI"""
        system = """Kamu adalah Neti, asisten virtual Intynet (ISP fiber-optic di Balikpapan).

PERSONALITY:
- Ramah dan helpful
- Bahasa Indonesia casual, sopan (pakai "kak")
- Emoji secukupnya (1-2 per pesan)
- Empathetic terhadap keluhan
- Response singkat dan to the point (max 3 paragraf)

RULES:
- Jawab berdasarkan knowledge base
- Jangan mengarang info yang tidak ada
- Jika di luar knowledge base, bilang akan dibantu tim terkait"""

        if include_kb:
            system += f"\n\nKNOWLEDGE BASE:\n{self.KNOWLEDGE_BASE}"
        
        if conversation_context:
            system += f"\n\nCONTEXT:\n{conversation_context}"
            
        system += f"\n\nINSTRUCTION:\n{instruction}"

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=400
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return "Maaf kak, ada kendala sistem. Bisa coba lagi ya? 🙏"

    # ============ STATE HANDLERS ============

    async def _handle_detect(
        self, intent: str, message: str, data: Dict[str, Any]
    ) -> Tuple[str, str, Dict[str, Any], bool]:
        """Handle DETECT state - route based on intent"""
        
        if intent == self.INTENT_PRODUCT:
            reply = await self._generate_response(
                """Customer menanyakan produk/harga.
Berikan info paket dengan jelas dan singkat.
Tanyakan apakah mau dibantu cek coverage area.""",
                message
            )
            reply += "\n\n" + self.PROMO_TEXT
            return self.STATE_PRODUCT_INFO, reply, data, False
        
        if intent == self.INTENT_COMPLAINT:
            data["initial_complaint"] = message[:200]
            reply = await self._generate_response(
                f"""Customer melaporkan gangguan internet.
Tunjukkan empati singkat, lalu berikan langkah troubleshooting:

{self.TROUBLESHOOT_STEPS}

Akhiri dengan tanya "Mau dicoba dulu langkah-langkahnya kak?" """,
                message,
                include_kb=False
            )
            return self.STATE_TROUBLESHOOT, reply, data, False
        
        if intent == self.INTENT_GREETING:
            reply = await self._generate_response(
                "Customer menyapa. Balas ramah, perkenalkan diri sebagai Neti dari Intynet, tanya ada yang bisa dibantu.",
                message,
                include_kb=False
            )
            return self.STATE_DETECT, reply, data, False
        
        if intent == self.INTENT_THANKS:
            return self.STATE_DETECT, "Siap kak! Ada yang bisa dibantu lagi? 😊", data, False
        
        # Default - general inquiry
        reply = await self._generate_response(
            "Jawab pertanyaan customer. Jika di luar knowledge base, bilang akan dibantu tim terkait.",
            message
        )
        return self.STATE_DETECT, reply, data, False

    async def _handle_product_info(
        self, intent: str, message: str, data: Dict[str, Any]
    ) -> Tuple[str, str, Dict[str, Any], bool]:
        """Handle PRODUCT_INFO state"""
        
        if intent == self.INTENT_COMPLAINT:
            # Switch to complaint handling
            data["initial_complaint"] = message[:200]
            reply = await self._generate_response(
                f"""Customer melaporkan gangguan. Berikan troubleshooting:
{self.TROUBLESHOOT_STEPS}
Tanya mau dicoba dulu?""",
                message,
                include_kb=False
            )
            return self.STATE_TROUBLESHOOT, reply, data, False
        
        if intent == self.INTENT_THANKS:
            return self.STATE_DETECT, "Siap kak! Jika ada pertanyaan lain, silakan tanya ya 😊", data, False
        
        # Continue answering product questions
        reply = await self._generate_response(
            "Lanjutkan menjawab pertanyaan produk/harga. Tetap helpful dan informatif.",
            message
        )
        return self.STATE_PRODUCT_INFO, reply, data, False

    async def _handle_troubleshoot(
        self, intent: str, message: str, data: Dict[str, Any]
    ) -> Tuple[str, str, Dict[str, Any], bool]:
        """Handle TROUBLESHOOT state - waiting for troubleshoot result"""
        
        if intent == self.INTENT_NOT_RESOLVED:
            # Problem not resolved - send form (LOCKED: must go to form_sent)
            return self.STATE_FORM_SENT, self.COMPLAINT_FORM, data, False
        
        if intent == self.INTENT_RESOLVED:
            reply = "Alhamdulillah sudah normal ya kak! 🎉 Senang bisa membantu. Jika ada kendala lagi, silakan hubungi kami kapan saja 😊"
            return self.STATE_DETECT, reply, data, False
        
        if intent == self.INTENT_PRODUCT:
            # Switch topic to product
            reply = await self._generate_response(
                "Customer tanya produk. Jawab pertanyaannya.",
                message
            )
            reply += "\n\n" + self.PROMO_TEXT
            return self.STATE_PRODUCT_INFO, reply, data, False
        
        if intent == self.INTENT_THANKS:
            # Acknowledge but stay in troubleshoot
            reply = "Siap kak! Coba dulu langkah-langkahnya ya. Kabari kalau sudah dicoba 😊"
            return self.STATE_TROUBLESHOOT, reply, data, False
        
        if intent == self.INTENT_COMPLAINT:
            # Additional complaint details
            reply = await self._generate_response(
                f"""Customer memberikan detail tambahan masalah.
Berikan troubleshooting yang relevan:
{self.TROUBLESHOOT_STEPS}
Tanya apakah mau dicoba.""",
                message,
                include_kb=False,
                conversation_context=f"Keluhan awal: {data.get('initial_complaint', '')}"
            )
            return self.STATE_TROUBLESHOOT, reply, data, False
        
        # Unclear response - ask for clarification (stay in troubleshoot)
        reply = "Bagaimana kak, sudah dicoba langkah-langkahnya? Apakah sudah normal atau masih bermasalah? 🙏"
        return self.STATE_TROUBLESHOOT, reply, data, False

    async def _handle_form_sent(
        self, intent: str, message: str, data: Dict[str, Any]
    ) -> Tuple[str, str, Dict[str, Any], bool]:
        """Handle FORM_SENT state - waiting for form submission (LOCKED)"""
        
        if intent == self.INTENT_FORM_DATA:
            # Form received - ESCALATE (human takeover)
            data["has_pending_report"] = True
            data["form_submitted"] = message[:500]
            logger.info("📋 Form received - escalating to human")
            return self.STATE_ESCALATED, None, data, True  # ai_stop = True
        
        if intent == self.INTENT_PRODUCT:
            # Allow product questions but remind about form
            reply = await self._generate_response(
                "Customer tanya produk. Jawab pertanyaannya, tapi ingatkan soal form laporan.",
                message
            )
            reply += "\n\n_PS: Jangan lupa isi form laporan di atas ya kak jika ingin dilanjutkan penanganannya 🙏_"
            return self.STATE_FORM_SENT, reply, data, False
        
        if intent == self.INTENT_THANKS:
            return self.STATE_FORM_SENT, "Siap kak! Ditunggu form-nya ya 🙏", data, False
        
        # Stay locked - remind about form
        return self.STATE_FORM_SENT, "Mohon isi form di atas ya kak agar bisa kami proses 🙏\n\nAtau jika ada pertanyaan lain, silakan tanyakan saja!", data, False

    async def _handle_escalated(
        self, intent: str, message: str, data: Dict[str, Any]
    ) -> Tuple[str, str, Dict[str, Any], bool]:
        """Handle ESCALATED state - human handling, AI helps with other topics"""
        
        if intent == self.INTENT_STATUS:
            reply = "Laporan kakak sudah diterima dan sedang dalam proses penanganan 🔧\n\nTim kami akan segera menghubungi. Ada hal lain yang bisa dibantu?"
            return self.STATE_ESCALATED, reply, data, False
        
        if intent == self.INTENT_COMPLAINT:
            reply = "Untuk laporan sebelumnya masih dalam proses kak 🔧\n\nJika ini masalah berbeda atau ada info tambahan, silakan sampaikan."
            return self.STATE_ESCALATED, reply, data, False
        
        if intent == self.INTENT_PRODUCT:
            # Can still answer product questions
            reply = await self._generate_response(
                "Customer tanya produk. Jawab pertanyaannya.",
                message
            )
            reply += "\n\n" + self.PROMO_TEXT
            return self.STATE_ESCALATED, reply, data, False
        
        if intent == self.INTENT_THANKS:
            return self.STATE_ESCALATED, "Sama-sama kak! Ada yang bisa dibantu lagi? 😊", data, False
        
        # Other questions - answer normally
        reply = await self._generate_response(
            "Jawab pertanyaan customer. Tetap ramah.",
            message
        )
        return self.STATE_ESCALATED, reply, data, False

    # ============ MAIN PROCESS ============

    async def process_message(
        self,
        customer_id: str,
        customer_name: str,
        message: str,
        session: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process incoming message using AI-based intent detection.
        NO keyword matching - fully dynamic.
        
        Returns:
            {
                "reply": str or None (None = no reply),
                "session": updated session dict,
                "ai_stop": bool (True = don't send message, human takeover)
            }
        """
        state = session.get("state", self.STATE_DETECT)
        data = session.get("collected_data", {})
        
        # Store customer info
        if customer_name:
            data["customer_name"] = customer_name
        if customer_id:
            data["phone"] = customer_id

        # Build context for intent classification
        context_parts = []
        if data.get("initial_complaint"):
            context_parts.append(f"Keluhan awal: {data['initial_complaint'][:50]}")
        if data.get("has_pending_report"):
            context_parts.append("Ada laporan pending")
        context = ", ".join(context_parts) if context_parts else ""

        logger.info(f"📥 Processing: state={state}, msg='{message[:30]}...'")

        # ===== AI-BASED INTENT CLASSIFICATION =====
        intent = await self._classify_intent(message, state, context)

        # ===== ROUTE TO STATE HANDLER =====
        handlers = {
            self.STATE_DETECT: self._handle_detect,
            self.STATE_PRODUCT_INFO: self._handle_product_info,
            self.STATE_TROUBLESHOOT: self._handle_troubleshoot,
            self.STATE_FORM_SENT: self._handle_form_sent,
            self.STATE_ESCALATED: self._handle_escalated,
        }

        handler = handlers.get(state, self._handle_detect)
        new_state, reply, new_data, ai_stop = await handler(intent, message, data)

        # ===== VALIDATE STATE TRANSITION =====
        valid_next = self.VALID_TRANSITIONS.get(state, [])
        if new_state not in valid_next:
            logger.warning(f"⚠️ Invalid transition {state} → {new_state}, staying in {state}")
            new_state = state

        logger.info(f"📤 Result: state={new_state}, ai_stop={ai_stop}")

        return {
            "reply": reply,
            "session": {"state": new_state, "collected_data": new_data},
            "ai_stop": ai_stop
        }
