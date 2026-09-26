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
BASE_API_URL = "https://powerfulstudio.xyz"

# Standard browser header to avoid blanket bot bans
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def chunk_list(lst, n):
    """Splits a list into sub-lists of size n."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def fetch_roblox_users_with_csrf(user_ids_chunk):
    """Handles the Roblox X-CSRF-TOKEN handshake to prevent 403 errors."""
    payload = {
        "userIds": user_ids_chunk,
        "excludeBannedUsers": False
    }

    # Step A: Make an initial call to extract the required token
    response = requests.post(ROBLOX_USERS_API, json=payload, headers=HEADERS, timeout=20)
    
    # If Roblox demands a CSRF token, grab it from the response header
    if response.status_code == 403 and "X-CSRF-TOKEN" in response.headers:
        csrf_token = response.headers["X-CSRF-TOKEN"]
        
        # Step B: Attach the token and immediately retry the request
        authenticated_headers = HEADERS.copy()
        authenticated_headers["X-CSRF-TOKEN"] = csrf_token
        
        response = requests.post(ROBLOX_USERS_API, json=payload, headers=authenticated_headers, timeout=20)
        
    return response

def sync_unresolved_clans():
    print("🔍 Scanning database for blank (NULL) clan names...")
    
    try:
        query = supabase.table("clans").select("id").filter("name", "is", "null").limit(100).execute()
        unresolved_clans = query.data
    except Exception as e:
        print(f"❌ Failed to query database clan profiles: {e}")
        return

    if not unresolved_clans:
        print("   ✅ All clan profiles are populated with names.")
        return

    print(f"🔄 Found {len(unresolved_clans)} blank clans. Fetching profile info...")
    
    for row in unresolved_clans:
        clan_id = row["id"]
        try:
            res = requests.get(f"{BASE_API_URL}/clans/{clan_id}", headers=HEADERS, timeout=15)
            if res.status_code == 200:
                data = res.json()
                real_name = data.get("name")
                
                if real_name:
                    supabase.table("clans").update({"name": real_name, "updated_at": "now()"}).eq("id", clan_id).execute()
                    print(f"   ↳ Updated Clan {clan_id[:6]}... -> '{real_name}'")
            elif res.status_code == 404:
                supabase.table("clans").update({"name": "Deleted Clan", "updated_at": "now()"}).eq("id", clan_id).execute()
        except Exception as e:
            print(f"   ❌ Error fetching details for clan {clan_id}: {e}")

def sync_unresolved_players_via_roblox():
    print("🔍 Scanning database for blank (NULL) Roblox player profiles...")
    
    try:
        query = supabase.table("players").select("id").filter("username", "is", "null").execute()
        unresolved_players = query.data
    except Exception as e:
        print(f"❌ Failed to query database player profiles: {e}")
        return

    if not unresolved_players:
        print("   ✅ All player profiles are populated with names.")
        return

    unresolved_ids = []
    for item in unresolved_players:
        try:
            unresolved_ids.append(int(item["id"]))
        except ValueError:
            continue

    print(f"🔄 Found {len(unresolved_ids)} blank player profiles. Bulk fetching names via Roblox...")

    id_chunks = list(chunk_list(unresolved_ids, 100))
    
    for chunk in id_chunks:
        try:
            response = fetch_roblox_users_with_csrf(chunk)
            
            if response.status_code == 200:
                roblox_data = response.json().get("data", [])
                print(f"   📥 Received {len(roblox_data)} verified profiles from Roblox.")
                
                for user in roblox_data:
                    roblox_id = str(user.get("id"))
                    real_name = user.get("name") # Change to user.get("displayName") if desired
                    
                    if real_name:
                        supabase.table("players")\
                            .update({"username": real_name, "updated_at": "now()"})\
                            .eq("id", roblox_id)\
                            .execute()
                            
                print(f"   ✅ Chunk update completed.")
            else:
                print(f"   ⚠️ Roblox requested payload returned status failure: {response.status_code}")
                print(f"   📋 Error Details: {response.text}")
        except Exception as e:
            print(f"   ❌ Network failure hitting Roblox endpoint: {e}")

if __name__ == "__main__":
    sync_unresolved_clans()
    sync_unresolved_players_via_roblox()
    print("🏁 Registry metadata sync loop completed.")
