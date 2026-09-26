import os
import sys
import requests
from supabase import create_client, Client

# 1. Initialize Supabase Connection using securely injected variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
LEADERBOARD_ID = "clanTotalAcorns"

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: Missing Supabase environment credentials.")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_and_store_clans():
    print(f"🚀 Starting clan data collection for leaderboard: {LEADERBOARD_ID}")
    
    # 2. Fetch data from the game's public API
    api_url = f"https://public-api.powerfulstudio.xyz/rcu/v1/leaderboards/{LEADERBOARD_ID}?pageSize=100&useMemory=false"
    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        clan_data = response.json()
    except Exception as e:
        print(f"❌ Failed to reach game API: {e}")
        sys.exit(1)
        
    if not isinstance(clan_data, list):
        print("❌ Unexpected API response format. Expected a JSON array list.")
        sys.exit(1)

    print(f"📥 Received {len(clan_data)} clans from API.")

    # 3. Pull existing clan IDs from Supabase to check for missing entries
    try:
        existing_clans_query = supabase.table("clans").select("id").execute()
        existing_clan_ids = {row["id"] for row in existing_clans_query.data}
    except Exception as e:
        print(f"❌ Failed to fetch existing clans from database: {e}")
        sys.exit(1)

    # 4. Prepare missing clans to prevent Foreign Key constraint crashes
    clans_to_insert = []
    for clan in clan_data:
        clan_id = clan.get("id")
        if clan_id and clan_id not in existing_clan_ids:
            clans_to_insert.append({
                "id": clan_id,
                "name": None
            })

    # Batch insert any newly discovered clans
    if clans_to_insert:
        print(f"✨ Found {len(clans_to_insert)} new clans. Registering them in 'clans' table...")
        try:
            supabase.table("clans").insert(clans_to_insert).execute()
        except Exception as e:
            print(f"❌ Failed to insert new clans: {e}")
            sys.exit(1)

    # 5. Insert all entries into clan_scores (Order from API determines Rank)
    clan_scores_payload = []
    for index, clan in enumerate(clan_data):
        clan_scores_payload.append({
            "clan_id": clan["id"],
            "leaderboard_id": LEADERBOARD_ID,
            "score": clan["value"],
            "current_rank": index + 1 # 1-indexed ranking
        })

    # Batch insert the historical log points
    if clan_scores_payload:
        print(f"💾 Saving {len(clan_scores_payload)} rows to 'clan_scores' table...")
        try:
            supabase.table("clan_scores").insert(clan_scores_payload).execute()
            print("✅ Clan tracking entries successfully stored!")
        except Exception as e:
            print(f"❌ Failed to log historic clan scores: {e}")
            sys.exit(1)

if __name__ == "__main__":
    fetch_and_store_clans()
