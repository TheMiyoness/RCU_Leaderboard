import os
import sys
import requests
from supabase import create_client, Client

# 1. Initialize Supabase Admin Credentials
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: Missing Supabase environment credentials.")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
ROBLOX_USERS_API = "https://roblox.com"

def chunk_list(lst, n):
    """Splits a list into sub-lists of size n."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def sync_unresolved_players_via_roblox():
    print("🔍 Scanning database for blank (NULL) Roblox player profiles...")
    
    # Target only players whose usernames are completely NULL/blank
    try:
        query = supabase.table("players").select("id").is_("username", "null").execute()
        unresolved_players = query.data
    except Exception as e:
        print(f"❌ Failed to query database profiles: {e}")
        return

    if not unresolved_players:
        print("✅ All player usernames are populated.")
        return

    # Extract clean list arrays (Ensuring conversion from text to numbers for Roblox requirements)
    unresolved_ids = []
    for item in unresolved_players:
        try:
            unresolved_ids.append(int(item["id"]))
        except ValueError:
            continue

    print(f"🔄 Found {len(unresolved_ids)} blank profiles. Bulk fetching metadata via Roblox API...")

    # Roblox allows batches per network payload; we chunk by 100 to stay optimal and safe
    id_chunks = list(chunk_list(unresolved_ids, 100))
    
    for chunk in id_chunks:
        payload = {
            "userIds": chunk,
            "excludeBannedUsers": False
        }
        
        try:
            response = requests.post(ROBLOX_USERS_API, json=payload, timeout=20)
            if response.status_code == 200:
                roblox_data = response.json().get("data", [])
                
                print(f"   📥 Received data properties for {len(roblox_data)} profiles. Syncing changes...")
                for user in roblox_data:
                    roblox_id = str(user.get("id"))
                    
                    # user.get("name") is their unique Roblox username (e.g., Builderman)
                    # user.get("displayName") is their custom display name (e.g., ActiveBuilder)
                    real_name = user.get("name") 
                    
                    if real_name:
                        supabase.table("players")\
                            .update({"username": real_name, "updated_at": "now()"})\
                            .eq("id", roblox_id)\
                            .execute()
                            
                print(f"   ✅ Chunk translation update set completed.")
            else:
                print(f"   ⚠️ Roblox requested payload returned status structural failure: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Network communication failure hitting Roblox endpoints: {e}")

if __name__ == "__main__":
    sync_unresolved_players_via_roblox()
    print("🏁 Roblox profile registry resolution pass finished.")
