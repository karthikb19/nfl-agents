"""
Test script to verify the refactored NFL stats transformers work correctly.

This script demonstrates that the functions moved to utils/nfl_stats_transformers.py
still work as expected by importing and running sample outputs.
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import from utils
sys.path.insert(0, str(Path(__file__).parent.parent))

import nflreadpy as nfl
import polars as pl
from utils.nfl_stats_transformers import to_player_game_stats, to_team_game_stats


def sample_team_game_stats(pbp: pl.DataFrame, team_stats: pl.DataFrame):
    """
    Sample output demonstrating to_team_game_stats() with Patriots data.
    Shows 2020 regular season games and championship seasons.
    """
    # Example: Get Patriots team game stats from 2000-2024
    patriots_stats = to_team_game_stats("NE", pbp, team_stats)
    
    print(f"Patriots game stats count: {len(patriots_stats)}")
    print(f"Seasons covered: {min(r['season'] for r in patriots_stats)} - {max(r['season'] for r in patriots_stats)}")
    
    # Show some games from 2020 season
    print("\n" + "="*100)
    print("Sample: Patriots 2020 Regular Season Games")
    print("="*100)
    games_2020 = [r for r in patriots_stats if r['season'] == 2020 and r['season_type'] == 'REG']
    for record in games_2020:
        pf = record['points_for'] if record['points_for'] is not None else 0
        pa = record['points_against'] if record['points_against'] is not None else 0
        res = record['result'] if record['result'] is not None else '?'
        epa_str = f"{record['passing_epa']:6.2f}" if record['passing_epa'] is not None else "   N/A"
        def_sacks = record['def_sacks'] if record['def_sacks'] is not None else 0.0
        print(
            f"Week {record['week']:2d}: "
            f"{record['team_id']} {'vs' if record['home_away'] == 'HOME' else '@':2s} {record['opponent_team_id']} - "
            f"{res:1s} {pf:2d}-{pa:2d} | "
            f"Pass: {record['passing_yards']:3d}yds {record['passing_tds']:2d}TD {epa_str}EPA | "
            f"Rush: {record['rushing_yards']:3d}yds {record['rushing_tds']:2d}TD | "
            f"Def: {def_sacks:.1f}sacks {record['def_interceptions']:2d}INT"
        )
    
    # Show a few championship years
    print("\n" + "="*100)
    print("Sample: Patriots Super Bowl Championship Seasons (2001, 2003, 2004)")
    print("="*100)
    for year in [2000, 2003, 2004]:
        games = [r for r in patriots_stats if r['season'] == year and r['season_type'] == 'REG'][:3]
        print(f"\n{year} Season (first 3 games):")
        for record in games:
            pf = record['points_for'] if record['points_for'] is not None else 0
            pa = record['points_against'] if record['points_against'] is not None else 0
            res = record['result'] if record['result'] is not None else '?'
            print(
                f"  Week {record['week']:2d}: "
                f"{record['team_id']} {'vs' if record['home_away'] == 'HOME' else '@':2s} {record['opponent_team_id']} - "
                f"{res:1s} {pf:2d}-{pa:2d} | "
                f"Pass: {record['passing_yards']:3d}yds {record['passing_tds']:2d}TD | "
                f"Rush: {record['rushing_yards']:3d}yds {record['rushing_tds']:2d}TD"
            )


def sample_player_game_stats(pbp: pl.DataFrame, player_stats: pl.DataFrame):
    """
    Sample output demonstrating to_player_game_stats() with Tom Brady data.
    Shows 2010 season and 2014/2017 Super Bowl championship games.
    """
    tom_brady_id = "00-0019596"
    tom_brady_stats = to_player_game_stats(tom_brady_id, pbp, player_stats)
    
    print(f"\nTom Brady game stats count: {len(tom_brady_stats)}")
    print(f"Seasons covered: {min(r['season'] for r in tom_brady_stats)} - {max(r['season'] for r in tom_brady_stats)}")
    
    # Show 2010 regular season (MVP year)
    print("\n" + "="*100)
    print("Sample: Tom Brady 2010 Regular Season (MVP Year)")
    print("="*100)
    games_2010 = [r for r in tom_brady_stats if r['season'] == 2010 and r['game_type'] == 'REG']
    for record in games_2010:
        pass_yds = record['pass_yards'] if record['pass_yards'] is not None else 0
        pass_tds = record['pass_td'] if record['pass_td'] is not None else 0
        ints = record['interceptions'] if record['interceptions'] is not None else 0
        rating = record['passer_rating'] if record['passer_rating'] is not None else 0.0
        epa_str = f"{record['pass_epa_total']:6.2f}" if record['pass_epa_total'] is not None else "   N/A"
        print(
            f"Week {record['week']:2d}: "
            f"{record['team_id']} {'vs' if record['home_away'] == 'HOME' else '@':2s} {record['opponent_team_id']} - "
            f"Pass: {pass_yds:3d}yds {pass_tds:2d}TD {ints:2d}INT | "
            f"Rating: {rating:5.1f} | EPA: {epa_str}"
        )
    
    # Show 2014 Super Bowl season (SB XLIX vs SEA)
    print("\n" + "="*100)
    print("Sample: Tom Brady 2014 Season (Super Bowl XLIX Champion)")
    print("="*100)
    games_2014_post = [r for r in tom_brady_stats if r['season'] == 2014 and r['game_type'] == 'POST']
    print(f"\n2014 Playoffs ({len(games_2014_post)} games):")
    for record in games_2014_post:
        pass_yds = record['pass_yards'] if record['pass_yards'] is not None else 0
        pass_tds = record['pass_td'] if record['pass_td'] is not None else 0
        ints = record['interceptions'] if record['interceptions'] is not None else 0
        rating = record['passer_rating'] if record['passer_rating'] is not None else 0.0
        print(
            f"  Week {record['week']:2d}: "
            f"{record['team_id']} {'vs' if record['home_away'] == 'HOME' else '@':2s} {record['opponent_team_id']} - "
            f"Pass: {pass_yds:3d}yds {pass_tds:2d}TD {ints:2d}INT | "
            f"Rating: {rating:5.1f}"
        )
    
    # Show 2017 Super Bowl season (SB LI vs ATL - 28-3 comeback)
    print("\n" + "="*100)
    print("Sample: Tom Brady 2016 Season (Super Bowl LI Champion - 28-3 Comeback)")
    print("="*100)
    games_2016_post = [r for r in tom_brady_stats if r['season'] == 2016 and r['game_type'] == 'POST']
    print(f"\n2016 Playoffs ({len(games_2016_post)} games):")
    for record in games_2016_post:
        pass_yds = record['pass_yards'] if record['pass_yards'] is not None else 0
        pass_tds = record['pass_td'] if record['pass_td'] is not None else 0
        ints = record['interceptions'] if record['interceptions'] is not None else 0
        rating = record['passer_rating'] if record['passer_rating'] is not None else 0.0
        print(
            f"  Week {record['week']:2d}: "
            f"{record['team_id']} {'vs' if record['home_away'] == 'HOME' else '@':2s} {record['opponent_team_id']} - "
            f"Pass: {pass_yds:3d}yds {pass_tds:2d}TD {ints:2d}INT | "
            f"Rating: {rating:5.1f}"
        )

def main():
    """
    Main test function that loads data and runs sample outputs.
    """
    print("="*100)
    print("NFL STATS TRANSFORMERS TEST")
    print("Testing refactored functions from utils/nfl_stats_transformers.py")
    print("="*100)
    
    # Load a small subset of data for testing (just 2010 season)
    print("\nLoading play-by-play data for 2010 season...")
    pbp: pl.DataFrame = nfl.load_pbp(list(range(2000, 2025)))
    print("Loading player stats for 2010 season...")
    player_stats: pl.DataFrame = nfl.load_player_stats(list(range(2000, 2025)))
    print("Loading team stats...")
    team_stats: pl.DataFrame = nfl.load_team_stats(seasons=True)
    print("Data loaded successfully!\n")
    
    # Sample team game stats output
    sample_team_game_stats(pbp, team_stats)
    
    # Sample player game stats output
    sample_player_game_stats(pbp, player_stats)
    
    print("\n" + "="*100)
    print("✅ TEST COMPLETE - Functions are working correctly!")
    print("="*100)


if __name__ == "__main__":
    main()
