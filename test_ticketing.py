"""
Test script untuk search customer ke Ticketing API
"""
import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_search_customer():
    # Langsung pakai IP untuk testing dari host
    api_url = "http://172.19.1.35:8080/api"
    api_key = os.getenv("TICKETING_API_KEY", "s3cr3tkey")
    
    customer_id = "EA429E"
    
    print(f"🔍 Testing search customer: {customer_id}")
    print(f"📍 API URL: {api_url}")
    print(f"🔑 API Key: {api_key[:10]}..." if api_key else "🔑 API Key: (not set)")
    print("-" * 50)
    
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"{api_url}/customers/search"
            print(f"🌐 Request: GET {url}?search={customer_id}")
            print(f"📋 Headers: {headers}")
            print("-" * 50)
            
            response = await client.get(
                url,
                headers=headers,
                params={"search": customer_id}
            )
            
            print(f"📊 Status: {response.status_code}")
            print(f"📄 Response Headers: {dict(response.headers)}")
            print("-" * 50)
            print(f"📦 Response Body:")
            print(response.text)
            
            if response.status_code == 200:
                data = response.json()
                print("-" * 50)
                print(f"✅ Success! Parsed JSON:")
                print(data)
            
    except httpx.ConnectError as e:
        print(f"❌ Connection Error: {e}")
    except httpx.TimeoutException as e:
        print(f"❌ Timeout: {e}")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_search_customer())
