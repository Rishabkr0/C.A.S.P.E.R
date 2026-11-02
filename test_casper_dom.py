"""
Test script for Casper DOM Agent & Ghost Cursor feature
Demonstrates:
1. Navigation via CDP
2. Set-of-Marks visual badges on interactive elements
3. Ghost Cursor gliding smoothly across the screen
4. Click ripple animation and typing into search inputs
5. Submitting search and clicking an element by numeric ID
"""

import asyncio
import logging
import sys

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from mcp_client.chrome_server import create_chrome_server

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def run_test():
    print("==================================================")
    print("1. Connecting to Chrome Server via CDP...")
    print("==================================================")
    server = await create_chrome_server(auto_connect=True)

    print("\n==================================================")
    print("2. Navigating to Google...")
    print("==================================================")
    nav_res = await server.call_tool("navigate", {"url": "https://www.google.com"})
    print("Navigation:", nav_res.get("content", [""])[0])
    await asyncio.sleep(2.0)

    print("\n==================================================")
    print("3. Scanning DOM for Interactive Elements (Set-of-Marks)...")
    print("   (Watch Chrome: Glowing cyan numbered badges will appear!)")
    print("==================================================")
    scan_res = await server.call_tool("scan_page", {"show_badges": True, "max_elements": 30})
    print("\nScanned Elements:")
    print(scan_res.get("content", ["No content"])[0])

    print("\n==================================================")
    print("4. Testing Ghost Cursor Movement & Visual Animation...")
    print("   (Watch Chrome: Casper's glowing cursor glides to center)")
    print("==================================================")
    await server.call_tool("move_cursor", {"x": 500, "y": 350, "label": "Casper Scanning..."})
    await asyncio.sleep(1.5)

    # Locate the search input
    elements = scan_res.get("elements", [])
    search_input = None
    for el in elements:
        role = el.get("role", "")
        label = el.get("label", "").lower()
        if "combobox" in role or "input" in role or "search" in label or "textarea" in role:
            search_input = el
            break

    if search_input:
        el_id = search_input["id"]
        print(f"\n==================================================")
        print(f"5. Typing into element [{el_id}] '{search_input.get('label')}' with Ghost Cursor...")
        print("   (Watch Chrome: Cursor moves to search bar, focuses, and types query)")
        print(f"==================================================")
        type_res = await server.call_tool("type_id", {
            "id": el_id,
            "text": "Antigravity AI Agent",
            "press_enter": True
        })
        print("Type result:", type_res.get("content", [""])[0])
        print("Waiting 3 seconds for search results to load...")
        await asyncio.sleep(3.0)

        # Scan the new search results page
        print("\n==================================================")
        print("6. Scanning Search Results Page...")
        print("==================================================")
        results_scan = await server.call_tool("scan_page", {"show_badges": True, "max_elements": 20})
        print(results_scan.get("content", ["No content"])[0])

        # Find first result link to click
        result_elements = results_scan.get("elements", [])
        link_to_click = None
        for el in result_elements:
            # Pick a link that is part of search results
            if el.get("role") in ("a", "link") and el.get("y", 0) > 150 and len(el.get("label", "")) > 10:
                link_to_click = el
                break

        if link_to_click:
            click_id = link_to_click["id"]
            print(f"\n==================================================")
            print(f"7. Clicking Search Result [{click_id}] '{link_to_click.get('label')}'...")
            print("   (Watch Chrome: Ghost cursor flies to link, triggers ripple wave & navigates)")
            print(f"==================================================")
            click_res = await server.call_tool("click_id", {"id": click_id})
            print("Click result:", click_res.get("content", [""])[0])
            await asyncio.sleep(3.0)

    print("\n==================================================")
    print("8. Cleaning up badges & overlays...")
    print("==================================================")
    await server.call_tool("clear_overlays", {})

    print("\n==================================================")
    print("✓ Full Casper DOM & Ghost Cursor test completed successfully!")
    print("Chrome will stay open so you can see the result.")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_test())
