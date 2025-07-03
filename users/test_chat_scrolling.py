#!/usr/bin/env python3
"""
Test script to verify chat scrolling functionality in the PyPoe web interface.
This script starts the web server and opens the browser for manual testing.
"""

import sys
import webbrowser
import time
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

from pypoe.web.runner import main

def test_chat_scrolling():
    print("🚀 Starting PyPoe web interface...")
    print("📝 Testing chat scrolling functionality:")
    print("   - Auto-scroll to bottom when loading conversations")
    print("   - Auto-scroll during message streaming")
    print("   - Navigation buttons (Home/End keys)")
    print("   - Smooth scrolling behavior")
    print("   - Mobile responsive design")
    print()
    print("🔧 Manual testing steps:")
    print("   1. Select a conversation with many messages")
    print("   2. Verify auto-scroll to latest message")
    print("   3. Test Home/End key navigation")
    print("   4. Test navigation buttons in chat header")
    print("   5. Send new messages and verify auto-scroll")
    print("   6. Test on mobile view (resize browser)")
    print()
    print("🌐 Opening browser...")
    
    # Give a moment for output to be visible
    time.sleep(2)
    
    # Open browser
    webbrowser.open("http://localhost:8000")
    
    # Start the web server
    main()

if __name__ == "__main__":
    test_chat_scrolling() 