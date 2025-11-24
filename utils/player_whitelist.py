import nflreadpy as nfl
from typing import List
import polars as pl
from pathlib import Path

def generate_player_whitelist(players: pl.DataFrame) -> List[str]:
    """
    Generates a list of Players GSIS IDs from the current_roster_data.csv file 
    """
    path = Path(__file__).resolve().parent / "data" / "current_roster_data.csv"
    df = pl.read_csv(path)
    valid_gsis_ids = []
    for row in df.iter_rows(named=True):
        name, position, team = row["name"], row["position"], row["team"]
        if position[-1] in "12":
            # remove number if it is WR1/WR2 type deal
            position = position[:-1]
        
        # Filter players DataFrame by name, position, and team
        filtered = players.filter(
            (pl.col("display_name") == name) & 
            (pl.col("position") == position) & 
            (pl.col("latest_team") == team)
        )
        
        # Check if any matches were found
        if filtered.height == 0:
            print(f"No match found for: {name} ({position}, {team})")
        else:
            # Append GSIS ID(s) to the valid list
            gsis_ids = filtered["gsis_id"].to_list()
            valid_gsis_ids.extend(gsis_ids)
    
    return valid_gsis_ids
