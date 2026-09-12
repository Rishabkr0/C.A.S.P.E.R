import os
from dotenv import load_dotenv
from livekit import api

load_dotenv()

# Generate a token for a user to join the test room
token = api.AccessToken(
    os.getenv('LIVEKIT_API_KEY'), 
    os.getenv('LIVEKIT_API_SECRET')
)
token.with_identity("human_user")
token.with_name("Human")
token.with_grants(api.VideoGrants(room_join=True, room="casper-test-room"))

jwt = token.to_jwt()

livekit_url = os.getenv('LIVEKIT_URL')

print("\n" + "="*60)
print("🔗 HERE IS YOUR TESTING LINK:")
print("="*60)
print(f"https://meet.livekit.io/custom?liveKitUrl={livekit_url}&token={jwt}")
print("="*60)
print("\nInstructions:")
print("1. Click the 'Launch casper' button in the dashboard so it says 'Online'.")
print("2. Ctrl+Click the link above to open it in your browser.")
print("3. Click 'Connect' in the browser.")
print("4. Say 'Hello', and casper will respond!\n")
