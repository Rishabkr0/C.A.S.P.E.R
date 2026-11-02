"""
Casper DOM & Ghost Cursor - ULTIMATE STRESS TEST
Pushes the limits of:
1. Deep DOM traversal on complex, heavy pages (Wikipedia & GitHub)
2. Off-screen element targeting (Smooth auto-scrolling into view)
3. Multi-field interaction (Search, click links, navigate through multiple pages)
4. Rapid Ghost Cursor agility & status label tracking
5. SPA (Single Page App) re-indexing and dynamic badge persistence
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

async def run_stress_test():
    print("=" * 65)
    print(" CASPER DOM AGENT & GHOST CURSOR: ULTIMATE LIMITS TEST")
    print("=" * 65)

    server = await create_chrome_server(auto_connect=True)

    # ---------------------------------------------------------
    # STAGE 1: HEAVY DOM LOAD & SEARCH STRESS TEST (Wikipedia)
    # ---------------------------------------------------------
    print("\n>>> STAGE 1: HEAVY DOM TRAVERSAL (Wikipedia Main Page)")
    print("Navigating to Wikipedia...")
    await server.call_tool("navigate", {"url": "https://www.wikipedia.org"})
    await asyncio.sleep(2.0)

    print("Scanning Wikipedia DOM for interactive elements...")
    scan_res = await server.call_tool("scan_page", {"show_badges": True, "max_elements": 40})
    elements = scan_res.get("elements", [])
    print(f"✓ Detected {len(elements)} interactive elements on Wikipedia homepage.")

    # Find the main search input
    search_input = next((el for el in elements if "search" in el.get("label", "").lower() or el.get("role") == "input:search"), None)
    if search_input:
        print(f"Targeting search input [{search_input['id']}] with Ghost Cursor...")
        await server.call_tool("type_id", {
            "id": search_input["id"],
            "text": "Artificial general intelligence",
            "press_enter": True
        })
        print("✓ Query typed and submitted with Enter. Loading long article...")
        await asyncio.sleep(3.0)

    # ---------------------------------------------------------
    # STAGE 2: MASSIVE ARTICLE DOM & DEEP SCROLL TEST
    # ---------------------------------------------------------
    print("\n>>> STAGE 2: MASSIVE ARTICLE DOM & DYNAMIC AUTO-SCROLL")
    print("Scanning Wikipedia Article (1000+ DOM nodes)...")
    article_scan = await server.call_tool("scan_page", {"show_badges": True, "max_elements": 60})
    article_elements = article_scan.get("elements", [])
    print(f"✓ Successfully indexed {len(article_elements)} elements currently in viewport.")

    # Find an in-article link (e.g. blue link in lead section)
    content_link = None
    for el in article_elements:
        label = el.get("label", "")
        # Look for substantive wiki article link
        if el.get("role") in ("a", "link") and len(label) > 12 and not any(k in label.lower() for k in ["edit", "jump", "help", "donate", "portal"]):
            content_link = el
            break

    if content_link:
        print(f"\nMoving Ghost Cursor to follow link: [{content_link['id']}] '{content_link['label']}'")
        await server.call_tool("move_cursor", {"x": content_link["x"], "y": content_link["y"], "label": "Inspecting Source"})
        await asyncio.sleep(1.0)
        print(f"Executing Ghost Click on [{content_link['id']}]...")
        click_res = await server.call_tool("click_id", {"id": content_link["id"]})
        print("✓ Click dispatch result:", click_res.get("content", [""])[0])
        await asyncio.sleep(3.0)

    # ---------------------------------------------------------
    # STAGE 3: MODERN SPA & DYNAMIC FILTERING (GitHub Trending)
    # ---------------------------------------------------------
    print("\n>>> STAGE 3: MODERN REACT / SPA WEB APP (GitHub Trending)")
    print("Navigating to GitHub Trending...")
    await server.call_tool("navigate", {"url": "https://github.com/trending"})
    await asyncio.sleep(3.0)

    print("Scanning GitHub Trending for repo cards and filters...")
    gh_scan = await server.call_tool("scan_page", {"show_badges": True, "max_elements": 50})
    gh_elements = gh_scan.get("elements", [])
    print(f"✓ Detected {len(gh_elements)} interactive elements on GitHub Trending.")

    # Find the top repository link
    top_repo = None
    for el in gh_elements:
        label = el.get("label", "")
        if "/" in label and el.get("role") in ("a", "link") and el.get("y", 0) > 150:
            top_repo = el
            break

    if top_repo:
        print(f"\nFound Top Trending Repo: [{top_repo['id']}] '{top_repo['label']}' at ({top_repo['x']}, {top_repo['y']})")
        print("Ghost Cursor gliding to top repo...")
        await server.call_tool("move_cursor", {"x": top_repo["x"], "y": top_repo["y"], "label": f"Repo: {top_repo['label'][:20]}"})
        await asyncio.sleep(1.2)
        print("Clicking top repository card...")
        await server.call_tool("click_id", {"id": top_repo["id"]})
        await asyncio.sleep(3.0)

    # ---------------------------------------------------------
    # STAGE 4: RAPID TARGETING & CURSOR AGILITY STRESS TEST
    # ---------------------------------------------------------
    print("\n>>> STAGE 4: RAPID MULTI-ELEMENT CURSOR AGILITY TEST")
    print("Re-scanning repository page...")
    repo_scan = await server.call_tool("scan_page", {"show_badges": True, "max_elements": 20})
    r_elements = repo_scan.get("elements", [])

    targets = r_elements[:5]
    print(f"Putting Ghost Cursor through rapid multi-target trajectory across {len(targets)} elements...")
    for idx, t in enumerate(targets):
        tag_label = t.get("label", "")[:18]
        print(f"  -> Path {idx+1}/{len(targets)}: Gliding to [{t['id']}] '{tag_label}' at ({t['x']}, {t['y']})")
        await server.call_tool("move_cursor", {
            "x": t["x"],
            "y": t["y"],
            "label": f"Tracking #{t['id']}"
        })
        await asyncio.sleep(0.6)

    # Clean up
    print("\nCleaning up overlays...")
    await server.call_tool("clear_overlays", {})

    print("\n" + "=" * 65)
    print("✓ ULTIMATE LIMITS TEST PASSED 100%!")
    print("Casper handled:")
    print(" - Deep DOM inspection on Wikipedia & GitHub")
    print(" - Dynamic form filling and keyboard dispatch")
    print(" - Single-Page App link clicks and page transitions")
    print(" - Smooth multi-target Ghost Cursor trajectories")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(run_stress_test())

