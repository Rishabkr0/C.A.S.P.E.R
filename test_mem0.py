from dotenv import load_dotenv
from mem0 import MemoryClient
import logging
import json


load_dotenv()
user_name = 'David'
# Pass api_key explicitly (avoids env lookup issues) — uses MEM0_API_KEY from .env
import os
mem0 = MemoryClient(api_key=os.getenv("MEM0_API_KEY"))

def add_memory():
    
    messages_formatted = [
        {        "role": "user",
            "content": "I really like Linkin Park."
        },
        {
            "role": "assistant",
            "content": "That is a good choice."
        },
        {
            "role": "user",
            "content": "I think so too."
        },
        {
            "role": "assistant",
            "content": "What is your favorite song by them?"
        },
    ]

    mem0.add(messages_formatted, user_id="David")

def get_memory_by_query():
    client = MemoryClient(api_key=os.getenv("MEM0_API_KEY"))
    query = f"What are {user_name}'s preferences?"
    # mem0ai 2.0.19 requires filters={'user_id': ...} (top-level user_id rejected)
    res = client.search(query, filters={'user_id': user_name})
    results = res.get("results", []) if isinstance(res, dict) else res

    memories = [
            {
                "memory": result["memory"],
                "updated_at": result["updated_at"]
            }
            for result in results
        ]
    memories_str = json.dumps(memories)
    print(f"Memories: {memories_str}")
    return memories_str


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    get_memory_by_query()
