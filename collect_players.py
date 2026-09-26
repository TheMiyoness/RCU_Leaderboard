import os
import sys
import requests
from supabase import create_client, Client

# 1. Initialize Supabase Connection
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
LEADERBOARD_ID = "totalAcorns"

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: Missing Supabase environment credentials.")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_and_store_players():
    print(f"🚀 Starting player data collection for leaderboard: {LEADERBOARD_ID}")
    
    # 2. Fetch data from the game's public API (Change endpoint path to match player tracking)
    api_url = f"https://public-api.powerfulstudio.xyz/rcu/v1/leaderboards/{LEADERBOARD_ID}?pageSize=100&useMemory=false"
    
    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        player_data = response.json()
    except Exception as e:
        print(f"❌ Failed to reach game API: {e}")
        sys.exit(1)
        
    if not isinstance(player_data, list):
        print("❌ Unexpected API response format. Expected a JSON array list.")
        sys.exit(1)

    print(f"📥 Received {len(player_data)} players from API.")

    # 3. Pull existing player IDs from Supabase to check for missing profiles
    try:
        existing_players_query = supabase.table("players").select("id").execute()
        existing_player_ids = {row["id"] for row in existing_players_query.data}
    except Exception as e:
        print(f"❌ Failed to fetch existing players from database: {e}")
        sys.exit(1)

    # 4. Prepare missing profiles to prevent foreign key constraint crashes
    players_to_insert = []
    for player in player_data:
        player_id = str(player.get("id")) # Force string context matching our TEXT data type
        if player_id and player_id not in existing_player_ids:
            players_to_insert.append({
                "id": player_id
            })

    # Batch insert newly discovered players
    if players_to_insert:
        print(f"✨ Found {len(players_to_insert)} new players. Registering profiles...")
        try:
            supabase.table("players").insert(players_to_insert).execute()
        except Exception as e:
            print(f"❌ Failed to register new players: {e}")
            sys.exit(1)

    # 5. Insert all entries into player_scores snapshot log (Array sequence = physical rank)
    player_scores_payload = []
    for index, player in enumerate(player_data):
        player_scores_payload.append({
            "player_id": str(player["id"]),
            "leaderboard_id": LEADERBOARD_ID,
            "score": player["value"],
            "current_rank": index + 1 # 1-indexed ranking
        })

    # Batch insert the tracking snapshots
    if player_scores_payload:
        print(f"💾 Saving {len(player_scores_payload)} rows to 'player_scores' table...")
        try:
            supabase.table("player_scores").insert(player_scores_payload).execute()
            print("✅ Player tracking entries successfully stored!")
        except Exception as e:
            print(f"❌ Failed to log historic player scores: {e}")
            sys.exit(1)

if __name__ == "__main__":
    fetch_and_store_players()
