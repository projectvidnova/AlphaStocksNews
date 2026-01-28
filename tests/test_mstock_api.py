#!/usr/bin/env python3
"""
Test script for the refactored MStockAPI class
This script tests the basic functionality without making real API calls
"""

import json
import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from api.mstock_api import MStockAPI

def test_initialization():
    """Test API initialization"""
    print("Testing MStockAPI initialization...")
    
    # Sample configuration
    test_config = {
        "api": {
            "credentials": {
                "api_key": "test_api_key",
                "username": "test_username", 
                "password": "test_password"
            },
            "urls": {
                "ws_url": "wss://test.com/ws"
            },
            "timeout": 30,
            "retry_attempts": 3,
            "retry_delay": 1
        }
    }
    
    try:
        api = MStockAPI(test_config)
        
        # Check if all attributes are set correctly
        assert api.api_key == "test_api_key"
        assert api.username == "test_username"
        assert api.password == "test_password"
        assert api.base_url == "https://api.mstock.trade/openapi/typea"
        assert api.session is not None
        assert 'X-Mirae-Version' in api.session.headers
        assert api.session.headers['X-Mirae-Version'] == '1'
        
        print("✓ Initialization successful!")
        return api
        
    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        return None

def test_checksum_generation():
    """Test checksum generation for session token"""
    print("Testing checksum generation...")
    
    test_config = {
        "api": {
            "credentials": {
                "api_key": "test_api_key",
                "username": "test_username", 
                "password": "test_password"
            },
            "urls": {
                "ws_url": "wss://test.com/ws"
            },
            "timeout": 30,
            "retry_attempts": 3,
            "retry_delay": 1
        }
    }
    
    try:
        api = MStockAPI(test_config)
        
        # Test checksum generation
        checksum = api._generate_checksum("test_api_key", "test_request_token")
        
        # Verify it's a valid SHA256 hash (64 characters)
        assert len(checksum) == 64
        assert all(c in '0123456789abcdef' for c in checksum)
        
        print(f"✓ Checksum generation successful: {checksum[:16]}...")
        return True
        
    except Exception as e:
        print(f"✗ Checksum generation failed: {e}")
        return False

def test_methods_exist():
    """Test that all expected methods exist"""
    print("Testing method availability...")
    
    test_config = {
        "api": {
            "credentials": {
                "api_key": "test_api_key",
                "username": "test_username", 
                "password": "test_password"
            },
            "urls": {
                "ws_url": "wss://test.com/ws"
            },
            "timeout": 30,
            "retry_attempts": 3,
            "retry_delay": 1
        }
    }
    
    try:
        api = MStockAPI(test_config)
        
        # Check that all expected methods exist
        expected_methods = [
            'login',
            'generate_session',
            'get_ltp',
            'get_ohlc',
            'get_historical_data',
            'get_option_chain',
            'get_option_chain_master',
            'get_option_strikes',
            'find_optimal_option_strike',
            'connect_websocket',
            'subscribe_ticks',
            'close_websocket',
            'place_order',
            'get_order_book',
            'get_holdings'
        ]
        
        missing_methods = []
        for method_name in expected_methods:
            if not hasattr(api, method_name) or not callable(getattr(api, method_name)):
                missing_methods.append(method_name)
        
        if missing_methods:
            print(f"✗ Missing methods: {missing_methods}")
            return False
        
        print("✓ All expected methods are available!")
        return True
        
    except Exception as e:
        print(f"✗ Method check failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=== Testing Refactored MStockAPI ===\n")
    
    tests = [
        test_initialization,
        test_checksum_generation,
        test_methods_exist
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        result = test_func()
        if result:
            passed += 1
        print()  # Add spacing between tests
    
    print("=== Test Results ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed! The refactoring appears successful.")
        return 0
    else:
        print("✗ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)