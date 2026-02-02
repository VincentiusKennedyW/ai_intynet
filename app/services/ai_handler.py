"""
AI Handler - Troubleshooting First, Then Report with Customer Validation
Flow: Greeting → Troubleshooting → Check Resolved → Show Form → Validate Customer → Confirm → Submit Report
"""

import json
import os
import re
from typing import Dict, Any, List
from openai import AsyncOpenAI
from datetime import datetime

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))


class AIHandler:
    """Handles AI conversation with troubleshooting-first approach and customer validation"""

    # Conversation states - LINEAR FLOW
    STATE_GREETING = "greeting"
    STATE_CHECK_RESOLVED = "check_resolved"
    STATE_COLLECT_FORM = (
        "collect_form"  # New: Show form and collect both ID + description
    )
    STATE_VALIDATING_CUSTOMER = "validating_customer"  # New: Validate customer ID
    STATE_CONFIRM_DATA = "confirm_data"
    STATE_COMPLETED = "completed"

    # Troubleshooting steps based on issue type
    TROUBLESHOOTING_STEPS = {
        "internet_mati": [
            "Coba restart modem dengan cara cabut kabel power, tunggu 30 detik, lalu colok lagi",
            "Pastikan semua kabel (power, LAN, fiber) terpasang dengan baik dan tidak longgar",
            "Cek lampu indikator di modem - normalnya lampu Power, LAN, dan Internet/PON harus menyala hijau",
            "Jika pakai WiFi, coba sambungkan langsung pakai kabel LAN ke laptop/PC",
        ],
        "internet_lambat": [
            "Coba restart modem dulu - cabut power 30 detik lalu colok lagi",
            "Cek berapa device yang terhubung ke WiFi, mungkin terlalu banyak",
            "Coba dekatkan device ke modem/router atau pindah ke ruangan yang lebih dekat",
            "Pastikan tidak ada yang sedang download besar atau streaming di device lain",
        ],
        "wifi_bermasalah": [
            "Restart modem dengan cabut kabel power 30 detik",
            "Coba lupakan (forget) jaringan WiFi di HP/laptop, lalu sambungkan ulang",
            "Pastikan jarak tidak terlalu jauh dari modem",
            "Cek apakah pakai kabel LAN bisa konek normal (untuk isolasi masalah WiFi)",
        ],
        "default": [
            "Langkah pertama, coba restart modem - cabut power 30 detik lalu colok lagi",
            "Pastikan semua kabel terpasang dengan baik",
            "Cek lampu indikator modem apakah normal (hijau semua)",
        ],
    }

    # Neti's personality
    PERSONALITY = """Kamu adalah Neti, asisten virtual dari Intynet (ISP di Balikpapan).

Personality:
- Ramah, helpful, dan empathetic
- Bahasa Indonesia casual tapi profesional
- Pakai emoji secukupnya (1-2 per message)
- Responsif terhadap emosi customer
- Variasi sapaan natural

CRITICAL RULES:
- Response SINGKAT: max 2-3 kalimat
- LANGSUNG ke inti
- Natural seperti chat CS manusia
- Jangan terlalu formal"""

    def __init__(self):
        self.model = "gpt-4o-mini"
        self.conversation_history: Dict[str, List[Dict]] = {}

    def _get_conversation_history(self, customer_id: str) -> List[Dict]:
        if customer_id not in self.conversation_history:
            self.conversation_history[customer_id] = []
        return self.conversation_history[customer_id]

    def _add_to_history(self, customer_id: str, role: str, content: str):
        history = self._get_conversation_history(customer_id)
        history.append({"role": role, "content": content})
        if len(history) > 10:
            self.conversation_history[customer_id] = history[-10:]

    def _detect_issue_type(self, message: str) -> str:
        """Detect issue type from message"""
        msg_lower = message.lower()

        if any(
            word in msg_lower
            for word in [
                "mati",
                "tidak bisa",
                "gak bisa",
                "ga bisa",
                "no internet",
                "putus",
            ]
        ):
            return "internet_mati"
        elif any(
            word in msg_lower
            for word in ["lambat", "lemot", "pelan", "slow", "lag", "lelet"]
        ):
            return "internet_lambat"
        elif any(word in msg_lower for word in ["wifi", "wi-fi", "wireless", "sinyal"]):
            return "wifi_bermasalah"
        else:
            return "default"

    def _check_still_not_working(self, message: str) -> bool:
        """Check if user says problem is not resolved"""
        msg_lower = message.lower()

        not_resolved_keywords = [
            "masih",
            "tetap",
            "belum",
            "tidak",
            "gak",
            "ga ",
            "nggak",
            "ngga",
            "sama aja",
            "sama saja",
            "tetep",
            "still",
            "blm",
            "tdk",
        ]

        resolved_keywords = [
            "sudah",
            "udah",
            "bisa",
            "berhasil",
            "work",
            "jalan",
            "lancar",
            "solved",
            "fix",
            "oke",
            "ok",
            "yes",
            "ya",
            "mantap",
            "thanks",
            "makasih",
        ]

        # Check if resolved first
        for keyword in resolved_keywords:
            if keyword in msg_lower and not any(
                neg in msg_lower for neg in ["tidak", "gak", "ga ", "belum", "blm"]
            ):
                return False

        # Check if not resolved
        for keyword in not_resolved_keywords:
            if keyword in msg_lower:
                return True

        return False

    def _extract_customer_id(self, message: str) -> str:
        """Extract customer ID from message"""
        # Try regex patterns
        patterns = [
            r"[A-Za-z]\d{3,}[A-Za-z]*",  # C650AD, A123BC
            r"\d{3,}[A-Za-z]+",  # 123ABC
            r"[A-Za-z]{2,}\d{3,}",  # AB123
        ]

        for pattern in patterns:
            match = re.search(pattern, message.upper())
            if match:
                return match.group()

        return None

    async def _generate_ai_response(
        self,
        customer_id: str,
        instruction: str,
        user_message: str,
        collected_data: Dict[str, Any],
    ) -> str:
        """Generate AI response"""

        context_parts = [self.PERSONALITY, "", instruction]

        if collected_data:
            context_parts.append("\nData terkumpul:")
            for key, value in collected_data.items():
                if key not in [
                    "message_count",
                    "troubleshooting_given",
                    "customer_validated",
                    "customer_data",
                ]:
                    context_parts.append(f"- {key}: {value}")

        system_prompt = "\n".join(context_parts)
        history = self._get_conversation_history(customer_id)

        messages = (
            [{"role": "system", "content": system_prompt}]
            + history
            + [{"role": "user", "content": user_message}]
        )

        try:
            response = await client.chat.completions.create(
                model=self.model, messages=messages, temperature=0.8, max_tokens=300
            )

            ai_response = response.choices[0].message.content.strip()

            self._add_to_history(customer_id, "user", user_message)
            self._add_to_history(customer_id, "assistant", ai_response)

            return ai_response

        except Exception as e:
            print(f"AI Response Error: {e}")
            return "Maaf, ada kendala sistem sebentar. Bisa coba lagi?"

    async def process_message(
        self,
        customer_id: str,
        customer_name: str,
        message: str,
        session: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Process message and route to appropriate handler"""

        current_state = session.get("state", self.STATE_GREETING)
        collected_data = session.get("collected_data", {})
        message_count = session.get("message_count", 0) + 1

        # Store customer info
        if customer_name and "customer_name" not in collected_data:
            collected_data["customer_name"] = customer_name
        if customer_id and "phone" not in collected_data:
            collected_data["phone"] = customer_id

        # Route to handler based on state
        if current_state == self.STATE_GREETING:
            result = await self._handle_greeting(customer_id, message, collected_data)
        elif current_state == self.STATE_CHECK_RESOLVED:
            result = await self._handle_check_resolved(
                customer_id, message, collected_data
            )
        elif current_state == self.STATE_COLLECT_FORM:
            result = await self._handle_collect_form(
                customer_id, message, collected_data
            )
        elif current_state == self.STATE_VALIDATING_CUSTOMER:
            result = await self._handle_validating_customer(
                customer_id, message, collected_data
            )
        elif current_state == self.STATE_CONFIRM_DATA:
            result = await self._handle_confirmation(
                customer_id, message, collected_data
            )
        elif current_state == self.STATE_COMPLETED:
            result = await self._handle_completed(customer_id, message, collected_data)
        else:
            result = await self._handle_greeting(customer_id, message, {})

        # Add message count to session
        result["session"]["message_count"] = message_count

        return result

    async def _handle_greeting(
        self, customer_id: str, message: str, collected_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle greeting and detect issue"""

        # Detect if message contains issue
        detection_prompt = f"""Analisis pesan ini: "{message}"

Apakah ada keluhan/masalah internet? Jawab dalam JSON:
{{"has_issue": true/false, "issue_summary": "ringkasan singkat atau null"}}"""

        try:
            resp = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": detection_prompt}],
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            result = json.loads(resp.choices[0].message.content.strip())

            if result.get("has_issue"):
                collected_data["initial_complaint"] = result.get(
                    "issue_summary", message
                )
                issue_type = self._detect_issue_type(message)
                collected_data["issue_type"] = issue_type

                # Get troubleshooting steps
                steps = self.TROUBLESHOOTING_STEPS.get(
                    issue_type, self.TROUBLESHOOTING_STEPS["default"]
                )
                steps_text = "\n".join([f"• {step}" for step in steps])

                instruction = f"""Customer melaporkan: {result.get('issue_summary', message)}

Task: Tunjukkan empati singkat, lalu berikan langkah troubleshooting ini:
{steps_text}

Setelah itu tanya apakah mau dicoba dulu dan kabari hasilnya.
Gunakan format bullet points. Max 4-5 kalimat total."""

                reply = await self._generate_ai_response(
                    customer_id, instruction, message, collected_data
                )
                collected_data["troubleshooting_given"] = True
                next_state = self.STATE_CHECK_RESOLVED
            else:
                instruction = "Sapa sebagai Neti dari Intynet. Tanya ada yang bisa dibantu. Max 2 kalimat."
                reply = await self._generate_ai_response(
                    customer_id, instruction, message, collected_data
                )
                next_state = self.STATE_GREETING

        except Exception as e:
            print(f"Greeting error: {e}")
            instruction = "Sapa sebagai Neti dari Intynet. Tanya ada yang bisa dibantu."
            reply = await self._generate_ai_response(
                customer_id, instruction, message, collected_data
            )
            next_state = self.STATE_GREETING

        return {
            "reply": reply,
            "session": {"state": next_state, "collected_data": collected_data},
        }

    async def _handle_check_resolved(
        self, customer_id: str, message: str, collected_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check if issue is resolved after troubleshooting"""

        # Use AI to detect
        check_prompt = f"""Analisis response user: "{message}"

Apakah masalah SUDAH TERATASI atau MASIH BERMASALAH?
JSON: {{"resolved": true/false}}

resolved=true jika: sudah bisa, berhasil, lancar, ok, thanks, makasih
resolved=false jika: masih, tetap, belum, tidak bisa, sama aja, gagal"""

        try:
            resp = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": check_prompt}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            result = json.loads(resp.choices[0].message.content.strip())
            is_resolved = result.get("resolved", False)

        except Exception as e:
            print(f"Check resolved error: {e}")
            is_resolved = not self._check_still_not_working(message)

        if is_resolved:
            # Problem solved!
            instruction = """Senang masalahnya sudah teratasi! 
Ucapkan terima kasih sudah menghubungi Intynet.
Bilang kalau ada masalah lagi bisa hubungi kapan saja.
Max 2 kalimat."""

            reply = await self._generate_ai_response(
                customer_id, instruction, message, collected_data
            )
            next_state = self.STATE_COMPLETED
            collected_data["resolved_by_troubleshooting"] = True
        else:
            # Need to create report - Show FORM (copy-paste ready)
            form_text = """Baik, saya akan bantu buatkan laporan ke tim teknis kami. 📝

Mohon *copy-paste* format di bawah ini, lalu isi datanya:

ID: 
Gangguan: 

Contoh pengisian:
ID: C650AD
Gangguan: Internet mati sejak pagi, lampu modem merah berkedip"""

            reply = form_text
            next_state = self.STATE_COLLECT_FORM

        return {
            "reply": reply,
            "session": {"state": next_state, "collected_data": collected_data},
        }

    async def _handle_collect_form(
        self, customer_id: str, message: str, collected_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle form submission - extract ID and description"""

        # Try to extract ID and description from message
        extracted_id = None
        extracted_desc = None

        # Check for formatted response (ID: xxx, Gangguan: xxx)
        id_match = re.search(r"(?:ID|id|Id)[:\s]*([A-Za-z0-9]+)", message)
        desc_match = re.search(
            r"(?:Gangguan|gangguan|GANGGUAN|Detail|detail|Masalah|masalah)[:\s]*(.+)",
            message,
            re.IGNORECASE | re.DOTALL,
        )

        if id_match:
            extracted_id = id_match.group(1).upper()

        if desc_match:
            extracted_desc = desc_match.group(1).strip()

        # If not formatted, try to extract customer ID from anywhere in message
        if not extracted_id:
            extracted_id = self._extract_customer_id(message)

        # If still no description, use the whole message minus the ID part
        if not extracted_desc and extracted_id:
            # Remove ID part and use rest as description
            desc_text = re.sub(r"(?:ID|id|Id)[:\s]*[A-Za-z0-9]+[,\s]*", "", message)
            desc_text = desc_text.strip()
            if len(desc_text) > 10:
                extracted_desc = desc_text

        # Validate we have both
        if not extracted_id:
            reply = """Hmm, saya tidak menemukan ID Pelanggan di pesanmu 🤔

Coba *copy-paste* format ini ya:

ID: 
Gangguan: 

*(ID bisa dilihat di tagihan/kontrak, contoh: C650AD)*"""

            return {
                "reply": reply,
                "session": {
                    "state": self.STATE_COLLECT_FORM,
                    "collected_data": collected_data,
                },
            }

        if not extracted_desc or len(extracted_desc) < 5:
            reply = f"""✅ ID Pelanggan: *{extracted_id}*

Tapi detail gangguannya belum ada. Balas dengan:

Gangguan: [jelaskan masalahnya, sejak kapan]"""

            collected_data["customer_references_number"] = extracted_id

            return {
                "reply": reply,
                "session": {
                    "state": self.STATE_COLLECT_FORM,
                    "collected_data": collected_data,
                },
            }

        # Both ID and description found - store and request validation
        collected_data["customer_references_number"] = extracted_id
        collected_data["description"] = extracted_desc
        collected_data["problem_time"] = datetime.now().isoformat()

        # Return with validation request
        return {
            "reply": f"⏳ Sedang memverifikasi ID Pelanggan {extracted_id}...",
            "session": {
                "state": self.STATE_VALIDATING_CUSTOMER,
                "collected_data": collected_data,
            },
            "needs_validation": True,
            "customer_ref_id": extracted_id,
        }

    async def _handle_validating_customer(
        self, customer_id: str, message: str, collected_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle after customer validation"""

        # This state is entered after main.py validates the customer
        # Check if we have validation result in collected_data

        if collected_data.get("customer_validated") == True:
            # Customer is valid - show confirmation
            customer_data = collected_data.get("customer_data", {})
            customer_name_from_system = customer_data.get(
                "name", collected_data.get("customer_name", "-")
            )

            summary = f"""📋 *Ringkasan Laporan*

👤 Nama: {customer_name_from_system}
📱 No. HP: {collected_data.get('phone', '-')}
🆔 ID Pelanggan: {collected_data.get('customer_references_number', '-')}
❗ Keluhan Awal: {collected_data.get('initial_complaint', '-')}
📝 Detail: {collected_data.get('description', '-')}

Apakah data di atas sudah benar? Balas *Ya* untuk kirim atau *Tidak* untuk koreksi."""

            # Update customer name from system
            if customer_name_from_system:
                collected_data["customer_name"] = customer_name_from_system

            return {
                "reply": summary,
                "session": {
                    "state": self.STATE_CONFIRM_DATA,
                    "collected_data": collected_data,
                },
            }

        elif collected_data.get("customer_validated") == False:
            # Customer not found - ask for valid ID
            reply = """❌ Maaf, ID Pelanggan tidak ditemukan di sistem kami.

Pastikan ID yang dimasukkan benar. ID Pelanggan bisa dilihat di:
• Tagihan/invoice bulanan
• Kontrak berlangganan
• Email konfirmasi pendaftaran

Mohon masukkan ID Pelanggan yang valid:"""

            # Clear the invalid ID
            collected_data.pop("customer_references_number", None)
            collected_data.pop("customer_validated", None)

            return {
                "reply": reply,
                "session": {
                    "state": self.STATE_COLLECT_FORM,
                    "collected_data": collected_data,
                },
            }

        else:
            # No validation result yet - this shouldn't happen normally
            # Try to extract ID from current message and request validation again
            extracted_id = self._extract_customer_id(message)

            if extracted_id:
                collected_data["customer_references_number"] = extracted_id
                return {
                    "reply": f"⏳ Sedang memverifikasi ID Pelanggan {extracted_id}...",
                    "session": {
                        "state": self.STATE_VALIDATING_CUSTOMER,
                        "collected_data": collected_data,
                    },
                    "needs_validation": True,
                    "customer_ref_id": extracted_id,
                }
            else:
                reply = """Mohon masukkan ID Pelanggan Anda:
(contoh: C650AD - bisa dilihat di tagihan)"""

                return {
                    "reply": reply,
                    "session": {
                        "state": self.STATE_COLLECT_FORM,
                        "collected_data": collected_data,
                    },
                }

    async def _handle_confirmation(
        self, customer_id: str, message: str, collected_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle data confirmation"""

        msg_lower = message.lower().strip()

        yes_keywords = [
            "ya",
            "yes",
            "benar",
            "betul",
            "ok",
            "oke",
            "y",
            "yap",
            "yup",
            "iya",
            "yoi",
            "sip",
            "siap",
            "bener",
        ]
        no_keywords = [
            "tidak",
            "no",
            "salah",
            "bukan",
            "koreksi",
            "ubah",
            "ganti",
            "n",
            "nggak",
            "ngga",
            "ga",
        ]

        is_yes = any(keyword in msg_lower for keyword in yes_keywords)
        is_no = any(keyword in msg_lower for keyword in no_keywords)

        if is_yes and not is_no:
            # Create report
            report_data = self._prepare_report_data(collected_data, customer_id)

            reply = """✅ Laporan berhasil dikirim!

Tim Helpdesk kami akan segera mengecek dan menghubungi Anda jika diperlukan.

Terima kasih sudah melapor ke Intynet! 🙏"""

            return {
                "reply": reply,
                "session": {
                    "state": self.STATE_COMPLETED,
                    "collected_data": collected_data,
                },
                "report_created": True,
                "report_data": report_data,
            }

        elif is_no:
            reply = """Baik, silakan isi ulang dengan format:
• *ID Pelanggan*: (contoh: C650AD)
• *Detail Gangguan*: (jelaskan masalahnya)"""

            # Clear form data but keep basic info
            keep_keys = [
                "customer_name",
                "phone",
                "initial_complaint",
                "issue_type",
                "troubleshooting_given",
            ]
            collected_data = {k: v for k, v in collected_data.items() if k in keep_keys}

            return {
                "reply": reply,
                "session": {
                    "state": self.STATE_COLLECT_FORM,
                    "collected_data": collected_data,
                },
            }

        else:
            reply = "Mohon balas *Ya* jika data sudah benar, atau *Tidak* jika ingin koreksi."

            return {
                "reply": reply,
                "session": {
                    "state": self.STATE_CONFIRM_DATA,
                    "collected_data": collected_data,
                },
            }

    async def _handle_completed(
        self, customer_id: str, message: str, collected_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle messages after completion"""

        # Check if new issue
        detection_prompt = f"""Analisis: "{message}"
Ada keluhan/masalah BARU? JSON: {{"new_issue": true/false}}"""

        try:
            resp = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": detection_prompt}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            result = json.loads(resp.choices[0].message.content.strip())

            if result.get("new_issue"):
                # Reset for new issue
                return await self._handle_greeting(
                    customer_id,
                    message,
                    {
                        "customer_name": collected_data.get("customer_name"),
                        "phone": collected_data.get("phone"),
                    },
                )
        except:
            pass

        reply = "Ada yang bisa saya bantu lagi? Kalau ada masalah lain, silakan ceritakan ya 😊"

        return {
            "reply": reply,
            "session": {
                "state": self.STATE_COMPLETED,
                "collected_data": collected_data,
            },
        }

    def _prepare_report_data(
        self, collected_data: Dict[str, Any], customer_id: str
    ) -> Dict[str, Any]:
        """Prepare data for incoming report API"""

        # Combine initial complaint and description
        full_description = collected_data.get("description", "")
        if collected_data.get("initial_complaint"):
            full_description = f"Keluhan awal: {collected_data.get('initial_complaint')}\n\nDetail: {full_description}"

        # Get customer ID from validated data if available
        customer_data = collected_data.get("customer_data", {})

        return {
            "customer_id": customer_data.get("id"),  # ID from ticketing system
            "customer_site_id": customer_data.get("site_id"),
            "customer_name": collected_data.get("customer_name", "Unknown"),
            "customer_phone": collected_data.get("phone", customer_id),
            "customer_references_number": collected_data.get(
                "customer_references_number"
            ),
            "description": full_description,
            "problem_time": collected_data.get("problem_time"),
            "qiscus_session_id": customer_id,
        }
