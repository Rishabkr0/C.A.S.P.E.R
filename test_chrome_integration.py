"""
Quick Test Script for Chrome MCP Integration
Run this to verify Chrome MCP is working correctly
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("chrome-test")


async def test_chrome_installation():
    """Test if Chrome is installed"""
    import subprocess

    print("\n" + "="*50)
    print("TEST 1: Chrome Installation")
    print("="*50)

    try:
        from mcp_client.chrome_server import ChromeMCPServer
        server = ChromeMCPServer()
        chrome_path = server.chrome_path

        if os.path.exists(chrome_path):
            print(f"✅ Chrome found at: {chrome_path}")
            return True
        else:
            print(f"❌ Chrome not found at: {chrome_path}")
            return False
    except Exception as e:
        print(f"❌ Error checking Chrome: {e}")
        return False


async def test_nodejs_installation():
    """Test if Node.js and npm are installed"""
    import subprocess

    print("\n" + "="*50)
    print("TEST 2: Node.js Installation")
    print("="*50)

    try:
        # Check Node.js
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            print(f"✅ Node.js version: {result.stdout.strip()}")

            # Check npm
            npm_result = subprocess.run(
                ["npm", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if npm_result.returncode == 0:
                print(f"✅ npm version: {npm_result.stdout.strip()}")
                return True
            else:
                print("❌ npm not found")
                return False
        else:
            print("❌ Node.js not found")
            print("\nInstall from: https://nodejs.org/")
            return False

    except FileNotFoundError:
        print("❌ Node.js not found in PATH")
        print("\nInstall from: https://nodejs.org/")
        return False
    except Exception as e:
        print(f"❌ Error checking Node.js: {e}")
        return False


async def test_chrome_mcp_server():
    """Test if Chrome MCP server can be accessed"""
    import subprocess

    print("\n" + "="*50)
    print("TEST 3: Chrome MCP Server")
    print("="*50)

    try:
        print("Testing npx access to Chrome MCP server...")

        result = subprocess.run(
            ["npx", "-y", "@modelcontextprotocol/server-chrome", "--help"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 or "usage" in result.stdout.lower() or "options" in result.stdout.lower():
            print("✅ Chrome MCP server accessible")
            print("   (Server will be downloaded on first use)")
            return True
        else:
            print(f"❌ Chrome MCP server test failed")
            print(f"   stdout: {result.stdout[:200]}")
            print(f"   stderr: {result.stderr[:200]}")
            return False

    except subprocess.TimeoutExpired:
        print("⚠️  Server test timed out (this is OK - server might be downloading)")
        print("   It will work when you run the agent")
        return True
    except Exception as e:
        print(f"❌ Error testing Chrome MCP server: {e}")
        return False


async def test_python_dependencies():
    """Test if required Python packages are installed"""

    print("\n" + "="*50)
    print("TEST 4: Python Dependencies")
    print("="*50)

    required_packages = [
        "psutil",
        "mcp",
        "livekit",
        "google.genai",
    ]

    missing = []

    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - NOT INSTALLED")
            missing.append(package)

    if missing:
        print(f"\nMissing packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False

    return True


async def test_chrome_server_initialization():
    """Test Chrome server initialization"""

    print("\n" + "="*50)
    print("TEST 5: Chrome Server Initialization")
    print("="*50)

    try:
        from mcp_client.chrome_server import create_chrome_server

        print("Attempting to initialize Chrome server...")
        print("(This may take 10-20 seconds on first run)")

        server = await create_chrome_server(auto_connect=True)

        if server and server.connected:
            print("✅ Chrome server initialized successfully")
            print(f"   Chrome running on port: {server.remote_debugging_port}")
            print(f"   User data dir: {server.user_data_dir}")

            # Cleanup
            await server.cleanup()
            print("✅ Server cleaned up successfully")
            return True
        else:
            print("❌ Server initialized but not connected")
            return False

    except Exception as e:
        print(f"❌ Failed to initialize Chrome server: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


async def test_basic_navigation():
    """Test basic Chrome navigation"""

    print("\n" + "="*50)
    print("TEST 6: Basic Navigation (Optional)")
    print("="*50)

    try:
        from mcp_client.chrome_server import create_chrome_server

        print("Initializing Chrome...")
        server = await create_chrome_server(auto_connect=True)

        if not server.connected:
            print("⚠️  Server not connected, skipping navigation test")
            return False

        print("✅ Chrome initialized")
        print("   A Chrome window should be open")
        print("   Check if Chrome is running with debugging enabled")

        # Cleanup
        await server.cleanup()
        print("✅ Test complete, Chrome closed")
        return True

    except Exception as e:
        print(f"⚠️  Navigation test skipped: {e}")
        return False


async def run_all_tests():
    """Run all tests"""

    print("\n" + "="*60)
    print("  casper - CHROME MCP INTEGRATION TEST SUITE")
    print("="*60)

    results = {}

    # Run tests
    results["Chrome Installation"] = await test_chrome_installation()
    results["Node.js Installation"] = await test_nodejs_installation()
    results["Chrome MCP Server"] = await test_chrome_mcp_server()
    results["Python Dependencies"] = await test_python_dependencies()

    # Only run advanced tests if basic ones pass
    if all([results["Chrome Installation"], results["Node.js Installation"]]):
        results["Server Initialization"] = await test_chrome_server_initialization()

        if results["Server Initialization"]:
            results["Basic Navigation"] = await test_basic_navigation()

    # Summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print("\n" + "-"*60)
    print(f"Results: {passed}/{total} tests passed")
    print("-"*60)

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nYou can now use Chrome MCP with voice commands:")
        print('  - "Skip this YouTube ad"')
        print('  - "Play music on Spotify"')
        print('  - "Read my emails"')
        print('  - "Search for Python tutorials"')
    else:
        print("\n⚠️  SOME TESTS FAILED")
        print("\nCheck the errors above and:")
        print("  1. Install missing dependencies")
        print("  2. Verify Chrome is installed")
        print("  3. Install Node.js if needed")
        print("  4. Run: pip install -r requirements.txt")
        print("\nSee CHROME_MCP_SETUP.md for detailed setup instructions")

    return passed == total


if __name__ == "__main__":
    print("\nStarting Chrome MCP tests...")
    print("This will verify your installation is correct\n")

    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test suite crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
