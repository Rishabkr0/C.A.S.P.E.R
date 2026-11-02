import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from worker_agent import delegate_heavy_task

async def main():
    print("Starting test...")
    # Mock context since it's type ignored anyway
    res = await delegate_heavy_task(None, "List the top-level items in your workspace.")
    print("Result:", res)

if __name__ == "__main__":
    asyncio.run(main())
