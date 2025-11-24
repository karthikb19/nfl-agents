import nflreadpy as nfl
from dotenv import load_dotenv, find_dotenv
import os
from supabase import Client, create_client
from utils.nfl_stats_transformers import to_player_game_stats, to_team_game_stats
import polars as pl
from typing import Dict, List, Any

FLAG = True

def init_load_dotenv() -> Client:
    load_dotenv(find_dotenv())
    url: str = os.getenv("SUPABASE_URL")
    key: str = os.getenv("SUPABASE_KEY")
    supabase: Client = create_client(url, key)
    return supabase

def _extract_team_id_abbrev(supabase: Client) -> Dict[str, int]:
    teams_res = supabase.table("teams").select("id, team_abbr").execute()
    abbr_to_id = {t["team_abbr"]: t["id"] for t in teams_res.data}
    return abbr_to_id


def _extract_needed_player_info(row):
    return {
        "gsis_id": row["gsis_id"],
        "display_name": row["display_name"],
        "common_first_name": row["common_first_name"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "short_name": row["short_name"],
        "football_name": row["football_name"],
        "suffix": row["suffix"],
        "nfl_id": row["nfl_id"],
        "pfr_id": row["pfr_id"],
        "espn_id": row["espn_id"],
        "birth_date": row["birth_date"],
        "position_group": row["position_group"],
        "position": row["position"],
        "height": row["height"],
        "weight": row["weight"],
        "headshot": row["headshot"],
        "college_name": row["college_name"],
        "college_conference": row["college_conference"],
        "jersey_number": row["jersey_number"],
        "rookie_season": row["rookie_season"],
        "last_season": row["last_season"],
        "latest_team_id": row["latest_team"],
        "status": row["status"],
        "years_of_experience": row["years_of_experience"],
        "draft_year": row["draft_year"],
        "draft_round": row["draft_round"],
        "draft_pick": row["draft_pick"],
        "draft_team_id": row["draft_team"],
    }

def load_player_info_into_db():
    supabase: Client = init_load_dotenv()
    abbr_to_id = _extract_team_id_abbrev(supabase)

    try:
        players = nfl.load_players()
        for row in players.iter_rows(named=True):
            if FLAG and row["gsis_id"] == "00-0019596":
                needed_player_info = _extract_needed_player_info(row)
                # get draft_team_id and latest_team_id and convert from ABBREV to id
                draft_abbr = needed_player_info["draft_team_id"]
                latest_abbr = needed_player_info["latest_team_id"]

                # 2) Handle None / missing teams safely
                needed_player_info["draft_team_id"] = abbr_to_id.get(draft_abbr) if draft_abbr else None
                needed_player_info["latest_team_id"] = abbr_to_id.get(latest_abbr) if latest_abbr else None

                try:
                    supabase.table("players").upsert(needed_player_info).execute()
                except Exception as e:
                    continue
        print("✓ Players table loaded successfully")
    except Exception as e:
        print(f"✗ Error loading players table: {e}")
        raise

def _extract_needed_team_info(row):
    return {
        "team_id": row["team_id"],
        "team_abbr": row["team_abbr"],
        "team_name": row["team_name"],
        "team_nick": row["team_nick"],
        "team_conf": row["team_conf"],
        "team_division": row["team_division"],
        "team_color": row["team_color"],
        "team_color2": row["team_color2"],
        "team_color3": row["team_color3"],
        "team_color4": row["team_color4"],
        "team_logo_wikipedia": row["team_logo_wikipedia"],
    }

def load_team_info_into_db():
    supabase: Client = init_load_dotenv()

    try:
        teams = nfl.load_teams()
        for row in teams.iter_rows(named=True):
            current_team_info = _extract_needed_team_info(row)
            try:
                supabase.table("teams").upsert(current_team_info).execute()
            except Exception as e:
                continue
        print("✓ Teams table loaded successfully")
    except Exception as e:
        print(f"✗ Error loading teams table: {e}")
        raise 

def load_player_game_stats_into_db(pbp: pl.DataFrame, player_stats: pl.DataFrame):
    supabase: Client = init_load_dotenv()
    abbr_to_id = _extract_team_id_abbrev(supabase)
    try:
        rows = supabase.table("players").select("*").execute().data
        print(rows)
        for row in rows:
            player_week_stats: List[Dict[str, Any]] = to_player_game_stats(row["gsis_id"], pbp, player_stats)
            for idx, game in enumerate(player_week_stats):
                player_week_stats[idx]["team_id"] = abbr_to_id.get(game["team_id"])
                player_week_stats[idx]["opponent_team_id"] = abbr_to_id.get(game["opponent_team_id"])
            print(player_week_stats)
            for idx, game in enumerate(player_week_stats):
                for k, v in game.items():
                    if type(v) == str and v == "0.00":
                        print(k)
                        exit(0)
            try:
                supabase.table("player_game_stats").upsert(player_week_stats).execute()
            except Exception as e:
                print(e)
                raise 
        print("✓ Player Game Stats table loaded successfully")
    except Exception as e:
        print(f"✗ Error loading players game stats table: {e}")
        raise


def main():
    # load_player_info_into_db()

    # pbp: pl.DataFrame = nfl.load_pbp(list(range(2000, 2025)))
    # player_stats: pl.DataFrame = nfl.load_player_stats(list(range(2000, 2025)))
    # team_stats: pl.DataFrame = nfl.load_team_stats(seasons=True)
    # print("✓ PBP + Player Game + Team Stats tables loaded successfully")
    # # load_player_game_stats_into_db(pbp, player_stats)
    pass

if __name__ == "__main__":
    main()
