"""
Data Loader for NFL Parquet Files

Generates parquet files from nflreadpy data using existing transformer functions.
These parquet files are then queryable via DuckDB in the sql_agent.
"""

import sys
from pathlib import Path

import nflreadpy as nfl
import polars as pl
from tqdm import tqdm

# Add parent directory to path for utils import
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import nfl_stats_transformers
from utils import player_whitelist

# Directory for parquet files
DATA_DIR = Path(__file__).parent / "data"


def load_teams_to_parquet() -> None:
    """Load teams from nflreadpy and save to parquet."""
    print("Loading teams...")
    teams = nfl.load_teams()
    
    # Select relevant columns
    teams_df = teams.select([
        "team_id",
        "team_abbr",
        "team_name",
        "team_nick",
        "team_conf",
        "team_division",
        "team_color",
        "team_color2",
        "team_color3",
        "team_color4",
        "team_logo_wikipedia",
    ])
    
    output_path = DATA_DIR / "teams.parquet"
    teams_df.write_parquet(output_path)
    print(f"✓ Teams saved to {output_path} ({teams_df.height} rows)")


def load_players_to_parquet() -> None:
    """Load players from nflreadpy (filtered by whitelist) and save to parquet."""
    print("Loading players...")
    players = nfl.load_players()
    allowed_players = player_whitelist.generate_player_whitelist(players)
    
    # Filter to whitelisted players
    players_df = players.filter(pl.col("gsis_id").is_in(allowed_players))
    
    # Select relevant columns
    players_df = players_df.select([
        "gsis_id",
        "display_name",
        "common_first_name",
        "first_name",
        "last_name",
        "short_name",
        "football_name",
        "suffix",
        "nfl_id",
        "pfr_id",
        "espn_id",
        "birth_date",
        "position_group",
        "position",
        "height",
        "weight",
        "headshot",
        "college_name",
        "college_conference",
        "jersey_number",
        "rookie_season",
        "last_season",
        "latest_team",  # Using abbreviation directly
        "status",
        "years_of_experience",
        "draft_year",
        "draft_round",
        "draft_pick",
        "draft_team",  # Using abbreviation directly
    ])
    
    output_path = DATA_DIR / "players.parquet"
    players_df.write_parquet(output_path)
    print(f"✓ Players saved to {output_path} ({players_df.height} rows)")


def load_player_game_stats_to_parquet(
    seasons: list[int] | None = None,
) -> None:
    """
    Load player game stats using the existing transformer function.
    
    This uses nfl_stats_transformers.to_player_game_stats() which calculates
    derived stats like passer_rating, pass_epa_per_play, rush_success_rate, etc.
    """
    if seasons is None:
        seasons = list(range(2000, 2025))
    
    print(f"Loading play-by-play for seasons {seasons[0]}-{seasons[-1]}...")
    pbp = nfl.load_pbp(seasons)
    
    print(f"Loading player stats for seasons {seasons[0]}-{seasons[-1]}...")
    player_stats = nfl.load_player_stats(seasons)
    
    print("Loading players for whitelist...")
    players = nfl.load_players()
    allowed_players = player_whitelist.generate_player_whitelist(players)
    
    all_records = []
    print("Transforming player game stats...")
    
    for player_id in tqdm(allowed_players, desc="Processing players"):
        player_records = nfl_stats_transformers.to_player_game_stats(
            player_id, pbp, player_stats
        )
        all_records.extend(player_records)
    
    if not all_records:
        print("⚠ No player game stats records generated")
        return
    
    # Convert to polars DataFrame
    df = pl.DataFrame(all_records, infer_schema_length=None)
    
    output_path = DATA_DIR / "player_game_stats.parquet"
    df.write_parquet(output_path)
    print(f"✓ Player game stats saved to {output_path} ({df.height} rows)")


def load_team_game_stats_to_parquet(
    seasons: list[int] | None = None,
) -> None:
    """
    Load team game stats using the existing transformer function.
    
    This uses nfl_stats_transformers.to_team_game_stats() which calculates
    derived stats like pass_yards_per_att, rush_epa_per_carry, etc.
    """
    if seasons is None:
        seasons = list(range(2000, 2025))
    
    print(f"Loading play-by-play for seasons {seasons[0]}-{seasons[-1]}...")
    pbp = nfl.load_pbp(seasons)
    
    print(f"Loading team stats for seasons {seasons[0]}-{seasons[-1]}...")
    team_stats = nfl.load_team_stats(seasons=True)
    
    print("Loading teams...")
    teams = nfl.load_teams()
    
    all_records = []
    print("Transforming team game stats...")
    
    for row in tqdm(teams.iter_rows(named=True), desc="Processing teams", total=teams.height):
        team_abbr = row["team_abbr"]
        team_records = nfl_stats_transformers.to_team_game_stats(
            team_abbr, pbp, team_stats
        )
        all_records.extend(team_records)
    
    if not all_records:
        print("⚠ No team game stats records generated")
        return
    
    # Convert to polars DataFrame
    df = pl.DataFrame(all_records, infer_schema_length=None)
    
    output_path = DATA_DIR / "team_game_stats.parquet"
    df.write_parquet(output_path)
    print(f"✓ Team game stats saved to {output_path} ({df.height} rows)")


def generate_all_parquet(seasons: list[int] | None = None) -> None:
    """Generate all parquet files from nflreadpy data."""
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("Generating parquet files for NFL data")
    print("=" * 60)
    
    # load_teams_to_parquet()
    # load_players_to_parquet()
    # load_player_game_stats_to_parquet(seasons)
    load_team_game_stats_to_parquet(seasons)
    
    print("=" * 60)
    print("✓ All parquet files generated successfully!")
    print("=" * 60)


if __name__ == "__main__":
    generate_all_parquet()
