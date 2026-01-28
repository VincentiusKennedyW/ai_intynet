#!/bin/bash

# Test script untuk ISP AI Support - NEW FLOW with Customer Validation
# Flow: Greeting → Troubleshooting → Check Resolved → Form → Validate Customer → Confirm → Submit Report
# Usage: ./test.sh

BASE_URL="http://localhost:8000"
CUSTOMER_ID="628115987778"
CUSTOMER_NAME="Vincent"

echo "🧪 Testing ISP AI Support System - NEW FLOW"
echo "============================================="
echo ""
echo "Flow: Lapor → Troubleshooting → Form → Validasi Customer → Report"
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Reset session first
echo -e "${YELLOW}0. Resetting Session...${NC}"
curl -s -X DELETE "$BASE_URL/session/$CUSTOMER_ID" | python3 -m json.tool 2>/dev/null || echo "{}"
echo ""
echo ""

# Test 1: Health Check
echo -e "${BLUE}1. Testing Health Check...${NC}"
curl -s "$BASE_URL/health" | python3 -m json.tool
echo ""
echo ""

# Test 2: Customer reports issue - AI gives troubleshooting tips
echo -e "${BLUE}2. Customer Melaporkan Gangguan...${NC}"
echo "   → AI akan kasih tips troubleshooting"
curl -s -X POST "$BASE_URL/test/message?customer_id=$CUSTOMER_ID&message=Halo%2C%20internet%20saya%20mati%20total&customer_name=$CUSTOMER_NAME" | python3 -m json.tool
echo ""
echo ""
sleep 2

# Test 3: Customer says still not working - AI shows FORM
echo -e "${BLUE}3. Customer: Masih tidak bisa setelah troubleshooting...${NC}"
echo "   → AI akan tampilkan FORM (ID + Gangguan)"
curl -s -X POST "$BASE_URL/test/message?customer_id=$CUSTOMER_ID&message=Sudah%20saya%20restart%20tapi%20masih%20tetap%20tidak%20bisa&customer_name=$CUSTOMER_NAME" | python3 -m json.tool
echo ""
echo ""
sleep 2

# Test 4: Customer fills form with ID and description
echo -e "${BLUE}4. Customer Mengisi Form (ID + Detail Gangguan)...${NC}"
echo "   → AI akan validasi customer ID ke Ticketing/Intynet"
curl -s -X POST "$BASE_URL/test/message?customer_id=$CUSTOMER_ID&message=ID%3A%20C650AD%2C%20Gangguan%3A%20Internet%20mati%20total%20sejak%20pagi%20jam%208%2C%20lampu%20modem%20merah%20berkedip&customer_name=$CUSTOMER_NAME" | python3 -m json.tool
echo ""
echo ""
sleep 2

# Test 5: Customer confirms data
echo -e "${BLUE}5. Customer Konfirmasi Data...${NC}"
curl -s -X POST "$BASE_URL/test/message?customer_id=$CUSTOMER_ID&message=Ya%20benar&customer_name=$CUSTOMER_NAME" | python3 -m json.tool
echo ""
echo ""

# Test 6: Check Session
echo -e "${BLUE}6. Checking Final Session State...${NC}"
curl -s "$BASE_URL/session/$CUSTOMER_ID" | python3 -m json.tool
echo ""
echo ""

echo -e "${GREEN}✅ Flow Test Completed!${NC}"
echo ""
echo "============================================="
echo "Expected Flow:"
echo "1. greeting → detect issue → give troubleshooting tips"
echo "2. check_resolved → customer says still not working → show FORM"
echo "3. collect_form → extract ID + description → validate customer"
echo "4. validating_customer → check Ticketing → check Intynet → show summary"
echo "5. confirm_data → customer confirms → create report"
echo "6. completed"
echo "============================================="
echo ""

# Optional: Test resolved scenario
echo ""
echo -e "${YELLOW}--- BONUS: Test Resolved Scenario (No Report Created) ---${NC}"
echo ""

CUSTOMER_ID2="628111222333"

echo -e "${BLUE}B1. Reset & Report Issue...${NC}"
curl -s -X DELETE "$BASE_URL/session/$CUSTOMER_ID2" > /dev/null
curl -s -X POST "$BASE_URL/test/message?customer_id=$CUSTOMER_ID2&message=Internet%20lambat%20banget&customer_name=Budi" | python3 -m json.tool
echo ""
sleep 2

echo -e "${BLUE}B2. Customer: Sudah bisa setelah restart...${NC}"
curl -s -X POST "$BASE_URL/test/message?customer_id=$CUSTOMER_ID2&message=Sudah%20saya%20restart%20dan%20lancar%20lagi%2C%20makasih&customer_name=Budi" | python3 -m json.tool
echo ""

echo -e "${GREEN}✅ Resolved scenario ends without creating report!${NC}"
echo ""

# Optional: Test invalid customer ID
echo ""
echo -e "${YELLOW}--- BONUS: Test Invalid Customer ID ---${NC}"
echo ""

CUSTOMER_ID3="628999888777"

echo -e "${BLUE}C1. Reset & Flow until form...${NC}"
curl -s -X DELETE "$BASE_URL/session/$CUSTOMER_ID3" > /dev/null
curl -s -X POST "$BASE_URL/test/message?customer_id=$CUSTOMER_ID3&message=Internet%20mati&customer_name=Test" > /dev/null
sleep 1
curl -s -X POST "$BASE_URL/test/message?customer_id=$CUSTOMER_ID3&message=Masih%20tidak%20bisa&customer_name=Test" > /dev/null
sleep 1

echo -e "${BLUE}C2. Submit invalid customer ID...${NC}"
curl -s -X POST "$BASE_URL/test/message?customer_id=$CUSTOMER_ID3&message=ID%3A%20INVALID123%2C%20Gangguan%3A%20Internet%20mati&customer_name=Test" | python3 -m json.tool
echo ""

echo -e "${RED}⚠️ Invalid ID should be rejected and ask for valid ID!${NC}"
