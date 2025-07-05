#!/usr/bin/env python3
"""
Test script to verify which Poe models are currently working.
This script will test a few models with a simple message and report which ones work.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pypoe.poe.client import PoeChatClient

async def test_model(client, model_name):
    """Test a single model with a simple message."""
    print(f"Testing {model_name}... ", end="", flush=True)
    
    try:
        response = ""
        async for chunk in client.send_message(
            "Hello! Please respond with just 'Working' to confirm you're accessible.",
            bot_name=model_name,
            save_history=False
        ):
            response += chunk
            
        print(f"✅ Working - Response: {response[:50]}{'...' if len(response) > 50 else ''}")
        return True
        
    except Exception as e:
        error_msg = str(e)
        if "Cannot access private bots" in error_msg:
            print("❌ Private/Deprecated")
        elif "insufficient" in error_msg.lower() or "quota" in error_msg.lower():
            print("⚠️  Quota/Credit issue")
        else:
            print(f"❌ Error: {error_msg[:100]}{'...' if len(error_msg) > 100 else ''}")
        return False

async def main():
    """Test various models to see which ones are working."""
    print("🧪 Testing PyPoe Model Availability")
    print("=" * 50)
    
    try:
        client = PoeChatClient(enable_history=False)
        
        # Test a selection of models
        models_to_test = [
            # OpenAI models
            "GPT-3.5-Turbo",
            "GPT-4",
            "GPT-4o",
            "GPT-4o-mini",
            
            # Anthropic models
            "Claude-instant",  # The problematic one
            "Claude-3-Opus",
            "Claude-3-Sonnet",
            "Claude-3-Haiku",
            "Claude-3.5-Sonnet",
            
            # Google models
            "Gemini-Pro",
            "Gemini-1.5-Pro",
            
            # Meta models
            "Llama-2-70b-chat",
            "Code-Llama-34b-Instruct",
        ]
        
        working_models = []
        failed_models = []
        
        for model in models_to_test:
            if await test_model(client, model):
                working_models.append(model)
            else:
                failed_models.append(model)
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)
        
        print("\n" + "=" * 50)
        print(f"✅ Working models ({len(working_models)}):")
        for model in working_models:
            print(f"  • {model}")
        
        print(f"\n❌ Failed models ({len(failed_models)}):")
        for model in failed_models:
            print(f"  • {model}")
        
        if working_models:
            print(f"\n💡 Recommended models to use:")
            # Show top 3 working models
            for model in working_models[:3]:
                print(f"  • {model}")
        
        await client.close()
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 