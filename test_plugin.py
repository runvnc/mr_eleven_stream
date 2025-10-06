#!/usr/bin/env python3
"""
Test script for the ElevenLabs Streaming TTS plugin.

This script tests the plugin structure and basic functionality.
"""

import os
import sys
import asyncio
import json
from pathlib import Path

def test_plugin_structure():
    """Test that all required plugin files exist."""
    print("Testing plugin structure...")
    
    plugin_root = Path("/xfiles/upd5/mr_eleven_stream")
    required_files = [
        "plugin_info.json",
        "setup.py",
        "pyproject.toml",
        "README.md",
        "src/mr_eleven_stream/__init__.py",
        "src/mr_eleven_stream/mod.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        full_path = plugin_root / file_path
        if not full_path.exists():
            missing_files.append(file_path)
        else:
            print(f"✓ {file_path}")
    
    if missing_files:
        print(f"✗ Missing files: {missing_files}")
        return False
    
    print("✓ All required files present")
    return True

def test_plugin_info():
    """Test plugin_info.json structure."""
    print("\nTesting plugin_info.json...")
    
    try:
        with open("/xfiles/upd5/mr_eleven_stream/plugin_info.json", 'r') as f:
            plugin_info = json.load(f)
        
        required_keys = ["name", "version", "description", "services"]
        for key in required_keys:
            if key not in plugin_info:
                print(f"✗ Missing key in plugin_info.json: {key}")
                return False
            print(f"✓ {key}: {plugin_info[key]}")
        
        if "stream_tts" not in plugin_info["services"]:
            print("✗ stream_tts service not listed in plugin_info.json")
            return False
        
        print("✓ plugin_info.json structure is valid")
        return True
        
    except Exception as e:
        print(f"✗ Error reading plugin_info.json: {e}")
        return False

def test_imports():
    """Test that the plugin modules can be imported."""
    print("\nTesting imports...")
    
    # Add the src directory to Python path
    src_path = "/xfiles/upd5/mr_eleven_stream/src"
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    
    try:
        # Test basic import
        import mr_eleven_stream
        print("✓ mr_eleven_stream module imported")
        
        # Test mod import
        from mr_eleven_stream import mod
        print("✓ mr_eleven_stream.mod imported")
        
        # Check if service is defined
        if hasattr(mod, 'stream_tts'):
            print("✓ stream_tts service found")
        else:
            print("✗ stream_tts service not found")
            return False
        
        # Check if ElevenLabsStreamer class exists
        if hasattr(mod, 'ElevenLabsStreamer'):
            print("✓ ElevenLabsStreamer class found")
        else:
            print("✗ ElevenLabsStreamer class not found")
            return False
        
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("Note: This is expected if elevenlabs package is not installed")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

async def test_service_signature():
    """Test the service function signature."""
    print("\nTesting service signature...")
    
    try:
        # Add the src directory to Python path
        src_path = "/xfiles/upd5/mr_eleven_stream/src"
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        
        from mr_eleven_stream.mod import stream_tts
        import inspect
        
        # Check if it's an async function
        if not asyncio.iscoroutinefunction(stream_tts):
            print("✗ stream_tts is not an async function")
            return False
        
        # Check function signature
        sig = inspect.signature(stream_tts)
        params = list(sig.parameters.keys())
        
        expected_params = ['text']
        for param in expected_params:
            if param not in params:
                print(f"✗ Missing required parameter: {param}")
                return False
        
        print(f"✓ Function signature: {sig}")
        print("✓ stream_tts service signature is valid")
        return True
        
    except Exception as e:
        print(f"✗ Error testing service signature: {e}")
        return False

def test_configuration():
    """Test configuration and environment setup."""
    print("\nTesting configuration...")
    
    # Check if .env.example exists
    env_example = Path("/xfiles/upd5/mr_eleven_stream/.env.example")
    if env_example.exists():
        print("✓ .env.example file exists")
    else:
        print("✗ .env.example file missing")
    
    # Check environment variable
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if api_key:
        print("✓ ELEVENLABS_API_KEY environment variable is set")
    else:
        print("⚠ ELEVENLABS_API_KEY environment variable not set")
        print("  This is required for the plugin to work")
    
    return True

def test_documentation():
    """Test documentation completeness."""
    print("\nTesting documentation...")
    
    readme_path = Path("/xfiles/upd5/mr_eleven_stream/README.md")
    if not readme_path.exists():
        print("✗ README.md missing")
        return False
    
    with open(readme_path, 'r') as f:
        readme_content = f.read()
    
    required_sections = [
        "# ElevenLabs Streaming TTS Plugin",
        "## Installation",
        "## Usage",
        "## Configuration"
    ]
    
    for section in required_sections:
        if section in readme_content:
            print(f"✓ {section} section found")
        else:
            print(f"✗ {section} section missing")
            return False
    
    print("✓ Documentation is complete")
    return True

async def main():
    """Run all tests."""
    print("ElevenLabs Streaming TTS Plugin - Test Suite")
    print("=" * 50)
    
    tests = [
        ("Plugin Structure", test_plugin_structure),
        ("Plugin Info", test_plugin_info),
        ("Imports", test_imports),
        ("Service Signature", test_service_signature),
        ("Configuration", test_configuration),
        ("Documentation", test_documentation)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                passed += 1
                print(f"✓ {test_name} PASSED")
            else:
                print(f"✗ {test_name} FAILED")
        except Exception as e:
            print(f"✗ {test_name} ERROR: {e}")
    
    print(f"\n{'='*50}")
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Plugin is ready to use.")
        print("\nNext steps:")
        print("1. Set ELEVENLABS_API_KEY environment variable")
        print("2. Install the plugin: pip install -e .")
        print("3. Enable the service in MindRoot admin interface")
    else:
        print("❌ Some tests failed. Please fix the issues above.")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
