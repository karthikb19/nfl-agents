# Test Directory

This directory contains test scripts to verify the functionality of the NFL RAG project.

## Files

### `test_stats_transformers.py`

Tests the refactored NFL stats transformation functions that were moved from `scripts/nfl_ready_intro.py` to `utils/nfl_stats_transformers.py`.

**Usage:**
```bash
python test/test_stats_transformers.py
```

This script:
- Imports `to_player_game_stats` and `to_team_game_stats` from the utils module
- Loads sample NFL data for 2010 and 2020 seasons
- Prints sample team game stats (Patriots 2020 season)
- Prints sample player game stats (Tom Brady 2010 MVP season)
- Verifies that the refactored functions work correctly

**Expected Output:**
- Patriots game statistics for the 2020 regular season
- Tom Brady's game-by-game statistics from his 2010 MVP season
