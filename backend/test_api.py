#!/usr/bin/env python3
"""
Simple test script to verify the API is working
"""

import requests
import sys
from pathlib import Path


def test_api():
    """Test the API endpoints"""
    base_url = "http://localhost:8000"
    
    print("🧪 Testing Album Recognition API\n")
    
    # Test 1: Root endpoint
    print("1. Testing root endpoint...")
    try:
        response = requests.get(f"{base_url}/")
        if response.status_code == 200:
            print("   ✅ Root endpoint working")
        else:
            print(f"   ❌ Root endpoint failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   ❌ Cannot connect to API. Is it running?")
        return False
    
    # Test 2: Health check
    print("2. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/api/health")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Health check: {data['status']}")
            print(f"      - Model loaded: {data['model_loaded']}")
            print(f"      - Data loaded: {data['data_loaded']}")
            print(f"      - Releases: {data['num_releases']}")
        else:
            print(f"   ❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Health check error: {str(e)}")
    
    # Test 3: Releases endpoint
    print("3. Testing releases endpoint...")
    try:
        response = requests.get(f"{base_url}/api/releases")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Found {data['count']} releases")
            if data['count'] > 0:
                first = data['releases'][0]
                print(f"      - First: {first['title']} by {', '.join(first['artists'])}")
        else:
            print(f"   ❌ Releases endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Releases error: {str(e)}")
    
    print("\n✨ API tests completed!\n")
    return True


if __name__ == "__main__":
    success = test_api()
    sys.exit(0 if success else 1)

