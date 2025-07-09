#!/usr/bin/env python3
"""Debug script to test environment loading."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

print("=" * 60)
print("🔍 Environment Loading Debug Script")
print("=" * 60)

print(f"📁 Current working directory: {os.getcwd()}")
print(f"🐍 Python executable: {sys.executable}")
print(f"📝 Script location: {__file__}")

# Test 1: Check if .env file exists
env_file = Path(".env")
print(f"\n1️⃣ Checking .env file:")
print(f"   File path: {env_file.absolute()}")
print(f"   Exists: {env_file.exists()}")

if env_file.exists():
    print(f"   Size: {env_file.stat().st_size} bytes")
    print(f"   Readable: {os.access(env_file, os.R_OK)}")

# Test 2: Try reading .env file manually
print(f"\n2️⃣ Manual file reading:")
try:
    with open(".env", "r") as f:
        content = f.read()
    print(f"   Content length: {len(content)} characters")
    lines = content.strip().split('\n')
    for i, line in enumerate(lines[:10], 1):  # Show first 10 lines
        if line.strip() and not line.strip().startswith('#'):
            # Mask the API key value for security
            if 'POE_API_KEY' in line:
                key_part = line.split('=')[0]
                print(f"   Line {i}: {key_part}=***MASKED***")
            else:
                print(f"   Line {i}: {line}")
        elif line.strip():
            print(f"   Line {i}: {line}")
except Exception as e:
    print(f"   Error reading file: {e}")

# Test 3: Check environment before loading
print(f"\n3️⃣ Environment before loading:")
poe_key_before = os.getenv("POE_API_KEY")
print(f"   POE_API_KEY: {'***SET***' if poe_key_before else 'NOT SET'}")

# Test 4: Try loading with dotenv
print(f"\n4️⃣ Loading with dotenv:")
try:
    result = load_dotenv(".env", verbose=True)
    print(f"   load_dotenv result: {result}")
except Exception as e:
    print(f"   load_dotenv error: {e}")

# Test 5: Check environment after loading
print(f"\n5️⃣ Environment after loading:")
poe_key_after = os.getenv("POE_API_KEY")
print(f"   POE_API_KEY: {'***SET***' if poe_key_after else 'NOT SET'}")

if poe_key_after:
    print(f"   Key length: {len(poe_key_after)} characters")
    print(f"   Key starts with: {poe_key_after[:10]}...")

# Test 6: Try the PyPoe config system
print(f"\n6️⃣ Testing PyPoe config system:")
try:
    sys.path.insert(0, 'src')
    from pypoe.config import get_config
    config = get_config()
    print(f"   Config loaded successfully")
    print(f"   API key set: {'***SET***' if config.poe_api_key else 'NOT SET'}")
    if config.poe_api_key:
        print(f"   Key length: {len(config.poe_api_key)} characters")
except Exception as e:
    print(f"   Config loading error: {e}")

print(f"\n✅ Debug complete!") 