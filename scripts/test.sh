#!/bin/bash

# Test script untuk ISP AI Support
# Usage: ./test.sh

BASE_URL="http://localhost:8000"
CUSTOMER_ID="628115987778"
CUSTOMER_NAME="Vincent"

echo "🧪 Testing ISP AI Support System"
echo "================================="
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test 1: Health Check
echo -e "${BLUE}1. Testing Health Check...${NC}"
curl -s "$BASE_URL/health" | python3 -m json.tool
echo ""
echo ""

# Test 2: Initial greeting with complaint
echo -e "${BLUE}2. Testing Initial Greeting (with complaint)...${NC}"
curl -s -X POST "$BASE_URL/test/message?customer_id=$CUSTOMER_ID&message=Internet%20saya%20mati&customer_name=$CUSTOMER_NAME" | python3 -m json.tool
echo ""
echo ""
sleep 2

# Test 3: Customer ID
echo -e "${BLUE}3. Testing Customer ID Collection...${NC}"
curl -s -X POST "$BASE_URL/test/message?customer_id=$CUSTOMER_ID&message=C650AD&customer_name=$CUSTOMER_NAME" | python3 -m json.tool
echo ""
echo ""
sleep 2

# Test 4: Address
echo -e "${BLUE}4. Testing Address Collection...${NC}"
curl -s -X POST "$BASE_URL/test/message?customer_id=$CUSTOMER_ID&message=Jl.%20Merdeka%20No%20123%20RT02%20RW05%20Balikpapan%20Kota&customer_name=$CUSTOMER_NAME" | python3 -m json.tool
echo ""
echo ""
sleep 2

# Test 5: Issue Type
echo -e "${BLUE}5. Testing Issue Type Selection...${NC}"
curl -s -X POST "$BASE_URL/test/message?customer_id=$CUSTOMER_ID&message=1&customer_name=$CUSTOMER_NAME" | python3 -m json.tool
echo ""
echo ""
sleep 2

# Test 6: Description
echo -e "${BLUE}6. Testing Description Collection...${NC}"
curl -s -X POST "$BASE_URL/test/message?customer_id=$CUSTOMER_ID&message=Internet%20mati%20sejak%20pagi%20jam%208%2C%20lampu%20modem%20merah%20berkedip&customer_name=$CUSTOMER_NAME" | python3 -m json.tool
echo ""
echo ""
sleep 2

# Test 7: Confirmation
echo -e "${BLUE}7. Testing Confirmation...${NC}"
curl -s -X POST "$BASE_URL/test/message?customer_id=$CUSTOMER_ID&message=ya&customer_name=$CUSTOMER_NAME" | python3 -m json.tool
echo ""
echo ""

# Test 8: Check Session
echo -e "${BLUE}8. Checking Final Session State...${NC}"
curl -s "$BASE_URL/session/$CUSTOMER_ID" | python3 -m json.tool
echo ""
echo ""

# Test 9: Reset Session
echo -e "${BLUE}9. Resetting Session...${NC}"
curl -s -X DELETE "$BASE_URL/session/$CUSTOMER_ID" | python3 -m json.tool
echo ""
echo ""

echo -e "${GREEN}✅ All tests completed!${NC}"
echo ""
echo "Check the logs above for AI responses."
echo "Each step should show natural conversation flow."
