"""
NFL Stats Transformers

This module provides transformation functions to convert nflreadpy data
into structured game statistics for players and teams.
"""

import polars as pl
from typing import Any, Dict, List, Optional


def _safe_div(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator) / float(denominator)


def _nfl_passer_rating(
    completions: int,
    attempts: int,
    yards: int,
    touchdowns: int,
    interceptions: int,
) -> float | None:
    """
    Traditional NFL passer rating, on a per-game (or per-week) basis.
    Returns None if there are no attempts.
    """
    if attempts in (None, 0):
        return None

    att = float(attempts)
    a = (completions / att - 0.3) * 5.0
    b = (yards / att - 3.0) * 0.25
    c = (touchdowns / att) * 20.0
    d = 2.375 - (interceptions / att) * 25.0

    # Each component is bounded between 0 and 2.375
    def _cap(x: float) -> float:
        return max(0.0, min(2.375, x))

    a = _cap(a)
    b = _cap(b)
    c = _cap(c)
    d = _cap(d)

    return ((a + b + c + d) / 6.0) * 100.0


def to_player_game_stats(
    player_id: str, pbp: pl.DataFrame, player_stats: pl.DataFrame
) -> List[Dict[str, Any]]:
    """
    Map nflreadpy play-by-play + player_stats into the player_game_stats schema
    for a single player on a game-by-game (week-by-week) basis.

    This focuses on what is realistically available from nflreadpy:
    - Fills standard passing / rushing / receiving box score fields
    - Adds EPA-based efficiency where possible
    - Derives team-level usage (targets / air_yards shares) from play-by-play
    - Leaves truly unavailable fields (snaps, team_id FKs, etc.) as None
    
    Usage:
    tom_brady_id = "00-0019596"
    tom_brady_stats = to_player_game_stats(tom_brady_id, pbp, player_stats)

    # Quick sanity check: print first few week-by-week records
    for record in tom_brady_stats:
        print(
            record["season"],
            record["week"],
            record["game_type"],
            record["team_id"],
            "vs" if record["home_away"] == "HOME" else "@",
            record["opponent_team_id"],
            "pass_yards:",
            record["pass_yards"],
        )
    """

    # Filter to the player of interest
    ps = player_stats.filter(pl.col("player_id") == player_id)
    if ps.is_empty():
        return []

    # Build a per-game "schedule" from pbp so we can recover game_id and home/away
    schedule = (
        pbp.select(
            [
                "game_id",
                "season",
                "week",
                "season_type",
                "home_team",
                "away_team",
            ]
        )
        .unique()
    )

    # Helper to detect ID columns for passer/rusher/receiver in pbp
    pbp_cols = set(pbp.columns)
    passer_id_col = "passer_player_id" if "passer_player_id" in pbp_cols else "passer_id"
    rusher_id_col = "rusher_player_id" if "rusher_player_id" in pbp_cols else "rusher_id"
    receiver_id_col = (
        "receiver_player_id" if "receiver_player_id" in pbp_cols else "receiver_id"
    )

    results: List[Dict[str, Any]] = []

    for row in ps.iter_rows(named=True):
        season = row["season"]
        week = row["week"]
        season_type = row["season_type"]  # "REG" / "POST" / "PRE"
       
        team = row["team"]
        opponent_team = row["opponent_team"]

        # Find the matching game for this season/week/team/opponent
        games = schedule.filter(
            (pl.col("season") == season)
            & (pl.col("week") == week)
            & (pl.col("season_type") == season_type)
            & (
                (
                    (pl.col("home_team") == team)
                    & (pl.col("away_team") == opponent_team)
                )
                | (
                    (pl.col("home_team") == opponent_team)
                    & (pl.col("away_team") == team)
                )
            )
        )

        if games.height == 0:
            # If we can't find a game_id, we still emit a record with minimal info.
            game_id = None
            home_team = None
        else:
            game = games.row(0, named=True)
            game_id = game["game_id"]
            home_team = game["home_team"]

        if home_team is not None and team is not None:
            home_away = "HOME" if team == home_team else "AWAY"
        else:
            home_away = None

        # Slice pbp down to this game for more advanced / team-level metrics
        if game_id is not None:
            pbp_game = pbp.filter(pl.col("game_id") == game_id)
        else:
            pbp_game = pbp.head(0)  # empty frame with same schema

        # Team-level play counts for this game
        if not pbp_game.is_empty() and team is not None:
            team_pbp = pbp_game.filter(pl.col("posteam") == team)

            team_pass_att = int(team_pbp["pass_attempt"].sum()) if "pass_attempt" in pbp_cols else None
            team_rush_att = int(team_pbp["rush_attempt"].sum()) if "rush_attempt" in pbp_cols else None

            if "pass_attempt" in pbp_cols:
                team_pass_plays = team_pbp.filter(pl.col("pass_attempt") == 1)
                if receiver_id_col in team_pass_plays.columns:
                    team_targets = (
                        team_pass_plays[receiver_id_col].drop_nulls().len()
                    )
                else:
                    team_targets = None
                team_air_yards = (
                    int(team_pass_plays["air_yards"].drop_nulls().sum())
                    if "air_yards" in team_pass_plays.columns
                    else None
                )
            else:
                team_targets = None
                team_air_yards = None
        else:
            team_pass_att = None
            team_rush_att = None
            team_targets = None
            team_air_yards = None

        # Player-level EPA and success from pbp
        if not pbp_game.is_empty():
            # Passing
            if passer_id_col in pbp_game.columns:
                player_pass = pbp_game.filter(
                    (pl.col(passer_id_col) == player_id)
                    & (pl.col("pass_attempt") == 1)
                )
            else:
                player_pass = pbp_game.head(0)

            pass_plays = player_pass.height
            pass_epa_total_pbp = float(player_pass["epa"].sum()) if "epa" in player_pass.columns else None
            if "success" in player_pass.columns and pass_plays > 0:
                success_series: pl.Series = player_pass["success"]  # type: ignore[assignment]
                pass_success_rate: Optional[float] = float(success_series.mean())  # type: ignore[arg-type]
            else:
                pass_success_rate = None

            # Rushing
            if rusher_id_col in pbp_game.columns:
                player_rush = pbp_game.filter(
                    (pl.col(rusher_id_col) == player_id)
                    & (pl.col("rush_attempt") == 1)
                )
            else:
                player_rush = pbp_game.head(0)

            rush_plays = player_rush.height
            rush_epa_total_pbp = float(player_rush["epa"].sum()) if "epa" in player_rush.columns else None
            if "success" in player_rush.columns and rush_plays > 0:
                rush_success_series: pl.Series = player_rush["success"]  # type: ignore[assignment]
                rush_success_rate: Optional[float] = float(rush_success_series.mean())  # type: ignore[arg-type]
            else:
                rush_success_rate = None
            rush_long_val = player_rush["rushing_yards"].max() if "rushing_yards" in player_rush.columns and rush_plays > 0 else None
            rush_long = int(rush_long_val) if rush_long_val is not None else None

            # Receiving (targets for this player)
            if receiver_id_col in pbp_game.columns:
                player_rec = pbp_game.filter(
                    (pl.col(receiver_id_col) == player_id)
                    & (pl.col("pass_attempt") == 1)
                )
            else:
                player_rec = pbp_game.head(0)

            rec_plays = player_rec.height
            rec_epa_total_pbp = float(player_rec["epa"].sum()) if "epa" in player_rec.columns else None
            if "success" in player_rec.columns and rec_plays > 0:
                rec_success_series: pl.Series = player_rec["success"]  # type: ignore[assignment]
                rec_success_rate: Optional[float] = float(rec_success_series.mean())  # type: ignore[arg-type]
            else:
                rec_success_rate = None
            rec_long_val = player_rec["receiving_yards"].max() if "receiving_yards" in player_rec.columns and rec_plays > 0 else None
            rec_long = int(rec_long_val) if rec_long_val is not None else None

            # Usage / share metrics (relative to team)
            targets = row.get("targets")
            rec_air_yards = row.get("receiving_air_yards")

            target_share = (
                _safe_div(targets, team_targets) if targets is not None and team_targets not in (None, 0) else None
            )
            air_yards_share = (
                _safe_div(rec_air_yards, team_air_yards)
                if rec_air_yards is not None and team_air_yards not in (None, 0)
                else None
            )
        else:
            pass_epa_total_pbp = None
            pass_success_rate = None
            rush_epa_total_pbp = None
            rush_success_rate = None
            rush_long = None
            rec_epa_total_pbp = None
            rec_success_rate = None
            rec_long = None
            targets = row.get("targets")
            rec_air_yards = row.get("receiving_air_yards")
            target_share = None
            air_yards_share = None

        # Basic aggregates from player_stats (per-week)
        attempts = row.get("attempts") or 0
        completions = row.get("completions") or 0
        passing_yards = row.get("passing_yards") or 0
        passing_tds = row.get("passing_tds") or 0
        interceptions = row.get("passing_interceptions") or 0
        sacks_suffered = row.get("sacks_suffered") or 0
        sack_yards_lost = row.get("sack_yards_lost") or 0

        passing_air_yards = row.get("passing_air_yards") or 0
        passing_yac = row.get("passing_yards_after_catch") or 0
        passing_first_downs = row.get("passing_first_downs") or 0
        passing_epa = row.get("passing_epa")
        passing_cpoe = row.get("passing_cpoe")

        carries = row.get("carries") or 0
        rushing_yards = row.get("rushing_yards") or 0
        rushing_tds = row.get("rushing_tds") or 0
        rushing_fumbles = row.get("rushing_fumbles") or 0
        rushing_first_downs = row.get("rushing_first_downs") or 0
        rushing_epa = row.get("rushing_epa")

        receptions = row.get("receptions") or 0
        targets = row.get("targets") or 0
        receiving_yards = row.get("receiving_yards") or 0
        receiving_tds = row.get("receiving_tds") or 0
        receiving_air_yards = row.get("receiving_air_yards") or 0
        receiving_yac = row.get("receiving_yards_after_catch") or 0
        receiving_first_downs = row.get("receiving_first_downs") or 0
        receiving_epa = row.get("receiving_epa")

        fantasy_points = row.get("fantasy_points")
        fantasy_points_ppr = row.get("fantasy_points_ppr")

	    # Derived advanced metrics
        pass_yards_per_att = _safe_div(passing_yards, attempts)

        # Adjusted Net Yards per Attempt (ANY/A)
        pass_any_a = None
        dropbacks = attempts + sacks_suffered
        if dropbacks > 0:
            pass_any_a = (
                (passing_yards + 20 * passing_tds - 45 * interceptions - sack_yards_lost)
                / float(dropbacks)
            )

        passer_rating = _nfl_passer_rating(
            completions=completions,
            attempts=attempts,
            yards=passing_yards,
            touchdowns=passing_tds,
            interceptions=interceptions,
        )

        # Prefer aggregated EPA from player_stats when available; fall back to pbp sum
        pass_epa_total = float(passing_epa) if passing_epa is not None else pass_epa_total_pbp
        pass_epa_per_play = _safe_div(pass_epa_total, dropbacks if dropbacks > 0 else None)

        rush_epa_total = float(rushing_epa) if rushing_epa is not None else rush_epa_total_pbp
        rush_epa_per_carry = _safe_div(rush_epa_total, carries if carries > 0 else None)

        rec_epa_total = float(receiving_epa) if receiving_epa is not None else rec_epa_total_pbp
        rec_epa_per_target = _safe_div(rec_epa_total, targets if targets > 0 else None)

        record: Dict[str, Any] = {
            # identity / game context
            "player_id": player_id,
            "game_id": game_id,
            "season": season,
            "week": week,
            "team_id": team,  # you will map team abbrev -> team PK in your DB
            "opponent_team_id": opponent_team,
            "home_away": home_away,
            "game_type": season_type,

            # snaps – not available from nflreadpy
            "snaps_offense": None,
            "snaps_offense_pct": None,

            # Passing
            "pass_att": int(attempts),
            "pass_cmp": int(completions),
            "pass_yards": int(passing_yards),
            "pass_td": int(passing_tds),
            "interceptions": int(interceptions),
            "sacks": int(sacks_suffered),
            "sack_yards": int(sack_yards_lost),
            "pass_first_downs": int(passing_first_downs),
            "pass_air_yards": int(passing_air_yards),
            "pass_yac_yards": int(passing_yac),
            "pass_yards_per_att": pass_yards_per_att,
            "pass_any_a": pass_any_a,
            "passer_rating": passer_rating,
            "cpoe": float(passing_cpoe) if passing_cpoe is not None else None,
            "pass_epa_total": pass_epa_total,
            "pass_epa_per_play": pass_epa_per_play,
            "pass_success_rate": pass_success_rate,

            # Rushing
            "rush_att": int(carries),
            "rush_yards": int(rushing_yards),
            "rush_td": int(rushing_tds),
            "rush_long": rush_long,
            "rush_first_downs": int(rushing_first_downs),
            "rush_fumbles": int(rushing_fumbles),
            "rush_epa_total": rush_epa_total,
            "rush_epa_per_carry": rush_epa_per_carry,
            "rush_success_rate": rush_success_rate,

            # Receiving
            "targets": int(targets),
            "receptions": int(receptions),
            "rec_yards": int(receiving_yards),
            "rec_td": int(receiving_tds),
            "rec_long": rec_long,
            "rec_first_downs": int(receiving_first_downs),
            "rec_air_yards": int(receiving_air_yards),
            "rec_yac_yards": int(receiving_yac),
            "rec_epa_total": rec_epa_total,
            "rec_epa_per_target": rec_epa_per_target,
            "rec_success_rate": rec_success_rate,

            # Team usage metrics
            "team_pass_att": team_pass_att,
            "team_rush_att": team_rush_att,
            "team_targets": team_targets,
            "team_air_yards": team_air_yards,
            "target_share": target_share,
            "air_yards_share": air_yards_share,
            "rush_attempt_share": _safe_div(carries, team_rush_att) if team_rush_att not in (None, 0) else None,

            # Fantasy
            "fantasy_points": float(fantasy_points) if fantasy_points is not None else None,
            "fantasy_points_ppr": float(fantasy_points_ppr) if fantasy_points_ppr is not None else None,
        }

        results.append(record)

    return results


def to_team_game_stats(
    team_abbr: str, pbp: pl.DataFrame, team_stats: pl.DataFrame
) -> List[Dict[str, Any]]:
    """
    Map nflreadpy play-by-play + team_stats into the team_game_stats schema
    for a single team on a game-by-game (week-by-week) basis.

    This focuses on what is realistically available from nflreadpy:
    - Fills standard offensive stats (passing, rushing, receiving)
    - Adds defensive stats
    - Includes special teams and kicking stats
    - Derives efficiency metrics (EPA, success rates)
    - Leaves truly unavailable fields (time_of_possession, total_drives, etc.) as None
    
    Usage:
        patriots_stats = to_team_game_stats("NE", pbp, team_stats)
        
        # Quick sanity check: print first few week-by-week records
        for record in patriots_stats:
            print(
                record["season"],
                record["week"],
                record["game_type"],
                record["team_id"],
                "vs" if record["home_away"] == "HOME" else "@",
                record["opponent_team_id"],
                "Result:",
                record["result"],
                f"{record['points_for']}-{record['points_against']}",
            )
    """
    
    # Filter to the team of interest
    ts = team_stats.filter(pl.col("team") == team_abbr)
    if ts.is_empty():
        return []
    
    # Build a per-game "schedule" from pbp so we can recover game_id, home/away, and scores
    # We need to get the final scores, so we'll take the max scores from each game
    pbp_cols = set(pbp.columns)
    
    # Check which score columns are available
    if "total_home_score" in pbp_cols and "total_away_score" in pbp_cols:
        schedule = (
            pbp.group_by(["game_id", "season", "week", "season_type", "home_team", "away_team"])
            .agg([
                pl.col("total_home_score").max().alias("home_score"),
                pl.col("total_away_score").max().alias("away_score"),
            ])
        )
    else:
        # Fallback if those columns don't exist
        schedule = (
            pbp.select(
                [
                    "game_id",
                    "season",
                    "week",
                    "season_type",
                    "home_team",
                    "away_team",
                ]
            )
            .unique()
        )
    
    results: List[Dict[str, Any]] = []
    
    for row in ts.iter_rows(named=True):
        season = row["season"]
        week = row["week"]
        season_type = row["season_type"]  # "REG" / "POST" / "PRE"
        team = row["team"]
        opponent_team = row["opponent_team"]
        
        # Find the matching game for this season/week/team/opponent
        games = schedule.filter(
            (pl.col("season") == season)
            & (pl.col("week") == week)
            & (pl.col("season_type") == season_type)
            & (
                (
                    (pl.col("home_team") == team)
                    & (pl.col("away_team") == opponent_team)
                )
                | (
                    (pl.col("home_team") == opponent_team)
                    & (pl.col("away_team") == team)
                )
            )
        )
        
        if games.height == 0:
            # If we can't find a game_id, we still emit a record with minimal info.
            game_id = None
            home_team = None
            home_score = None
            away_score = None
        else:
            game = games.row(0, named=True)
            game_id = game["game_id"]
            home_team = game["home_team"]
            home_score = game["home_score"]
            away_score = game["away_score"]
        
        if home_team is not None and team is not None:
            home_away = "HOME" if team == home_team else "AWAY"
        else:
            home_away = None
        
        # Determine points for/against and result
        if home_away == "HOME" and home_score is not None and away_score is not None:
            points_for = int(home_score)
            points_against = int(away_score)
        elif home_away == "AWAY" and home_score is not None and away_score is not None:
            points_for = int(away_score)
            points_against = int(home_score)
        else:
            points_for = None
            points_against = None
        
        if points_for is not None and points_against is not None:
            if points_for > points_against:
                result = "W"
            elif points_for < points_against:
                result = "L"
            else:
                result = "T"
        else:
            result = None
        
        # Slice pbp down to this game for more advanced metrics
        if game_id is not None:
            pbp_game = pbp.filter(pl.col("game_id") == game_id)
        else:
            pbp_game = pbp.head(0)  # empty frame with same schema
        
        # Compute play counts and efficiency from pbp
        if not pbp_game.is_empty() and team is not None:
            team_pbp = pbp_game.filter(pl.col("posteam") == team)
            
            # Total plays (pass attempts + rush attempts)
            pbp_cols = set(pbp_game.columns)
            if "pass_attempt" in pbp_cols and "rush_attempt" in pbp_cols:
                total_plays = int(
                    team_pbp["pass_attempt"].sum() + team_pbp["rush_attempt"].sum()
                )
            else:
                total_plays = None
            
            # Passing efficiency from pbp
            if "pass_attempt" in pbp_cols:
                pass_plays = team_pbp.filter(pl.col("pass_attempt") == 1)
                pass_plays_count = pass_plays.height
                
                if "success" in pbp_cols and pass_plays_count > 0:
                    pass_success_rate = float(pass_plays["success"].mean())
                else:
                    pass_success_rate = None
            else:
                pass_success_rate = None
            
            # Rushing efficiency from pbp
            if "rush_attempt" in pbp_cols:
                rush_plays = team_pbp.filter(pl.col("rush_attempt") == 1)
                rush_plays_count = rush_plays.height
                
                if "success" in pbp_cols and rush_plays_count > 0:
                    rush_success_rate = float(rush_plays["success"].mean())
                else:
                    rush_success_rate = None
            else:
                rush_success_rate = None
            
            # Dropbacks = attempts + sacks
            attempts = row.get("attempts") or 0
            sacks_suffered = row.get("sacks_suffered") or 0
            dropbacks = attempts + sacks_suffered
        else:
            total_plays = None
            pass_success_rate = None
            rush_success_rate = None
            dropbacks = None
        
        # Extract basic stats from team_stats row
        # Passing
        completions = row.get("completions") or 0
        attempts = row.get("attempts") or 0
        passing_yards = row.get("passing_yards") or 0
        passing_tds = row.get("passing_tds") or 0
        passing_interceptions = row.get("passing_interceptions") or 0
        sacks_suffered = row.get("sacks_suffered") or 0
        sack_yards_lost = row.get("sack_yards_lost") or 0
        sack_fumbles = row.get("sack_fumbles") or 0
        sack_fumbles_lost = row.get("sack_fumbles_lost") or 0
        passing_air_yards = row.get("passing_air_yards") or 0
        passing_yards_after_catch = row.get("passing_yards_after_catch") or 0
        passing_first_downs = row.get("passing_first_downs") or 0
        passing_epa = row.get("passing_epa")
        passing_cpoe = row.get("passing_cpoe")
        passing_2pt_conversions = row.get("passing_2pt_conversions") or 0
        
        # Rushing
        carries = row.get("carries") or 0
        rushing_yards = row.get("rushing_yards") or 0
        rushing_tds = row.get("rushing_tds") or 0
        rushing_fumbles = row.get("rushing_fumbles") or 0
        rushing_fumbles_lost = row.get("rushing_fumbles_lost") or 0
        rushing_first_downs = row.get("rushing_first_downs") or 0
        rushing_epa = row.get("rushing_epa")
        rushing_2pt_conversions = row.get("rushing_2pt_conversions") or 0
        
        # Receiving
        receptions = row.get("receptions") or 0
        targets = row.get("targets") or 0
        receiving_yards = row.get("receiving_yards") or 0
        receiving_tds = row.get("receiving_tds") or 0
        receiving_fumbles = row.get("receiving_fumbles") or 0
        receiving_fumbles_lost = row.get("receiving_fumbles_lost") or 0
        receiving_air_yards = row.get("receiving_air_yards") or 0
        receiving_yards_after_catch = row.get("receiving_yards_after_catch") or 0
        receiving_first_downs = row.get("receiving_first_downs") or 0
        receiving_epa = row.get("receiving_epa")
        receiving_2pt_conversions = row.get("receiving_2pt_conversions") or 0
        
        # Defense
        def_tackles_solo = row.get("def_tackles_solo") or 0
        def_tackles_with_assist = row.get("def_tackles_with_assist") or 0
        def_tackle_assists = row.get("def_tackle_assists") or 0
        def_tackles_for_loss = row.get("def_tackles_for_loss") or 0
        def_tackles_for_loss_yards = row.get("def_tackles_for_loss_yards") or 0
        def_fumbles_forced = row.get("def_fumbles_forced") or 0
        def_sacks = row.get("def_sacks")
        def_sack_yards = row.get("def_sack_yards") or 0
        def_qb_hits = row.get("def_qb_hits") or 0
        def_interceptions = row.get("def_interceptions") or 0
        def_interception_yards = row.get("def_interception_yards") or 0
        def_pass_defended = row.get("def_pass_defended") or 0
        def_tds = row.get("def_tds") or 0
        def_fumbles = row.get("def_fumbles") or 0
        def_safeties = row.get("def_safeties") or 0
        
        # Fumbles / misc
        misc_yards = row.get("misc_yards") or 0
        fumble_recovery_own = row.get("fumble_recovery_own") or 0
        fumble_recovery_yards_own = row.get("fumble_recovery_yards_own") or 0
        fumble_recovery_opp = row.get("fumble_recovery_opp") or 0
        fumble_recovery_yards_opp = row.get("fumble_recovery_yards_opp") or 0
        fumble_recovery_tds = row.get("fumble_recovery_tds") or 0
        
        # Penalties
        penalties = row.get("penalties") or 0
        penalty_yards = row.get("penalty_yards") or 0
        timeouts = row.get("timeouts") or 0
        
        # Returns / special teams
        punt_returns = row.get("punt_returns") or 0
        punt_return_yards = row.get("punt_return_yards") or 0
        kickoff_returns = row.get("kickoff_returns") or 0
        kickoff_return_yards = row.get("kickoff_return_yards") or 0
        special_teams_tds = row.get("special_teams_tds") or 0
        
        # Field goals
        fg_made = row.get("fg_made") or 0
        fg_att = row.get("fg_att") or 0
        fg_missed = row.get("fg_missed") or 0
        fg_blocked = row.get("fg_blocked") or 0
        fg_long = row.get("fg_long")
        fg_pct = row.get("fg_pct")
        
        fg_made_0_19 = row.get("fg_made_0_19") or 0
        fg_made_20_29 = row.get("fg_made_20_29") or 0
        fg_made_30_39 = row.get("fg_made_30_39") or 0
        fg_made_40_49 = row.get("fg_made_40_49") or 0
        fg_made_50_59 = row.get("fg_made_50_59") or 0
        fg_made_60_ = row.get("fg_made_60_") or 0
        
        fg_missed_0_19 = row.get("fg_missed_0_19") or 0
        fg_missed_20_29 = row.get("fg_missed_20_29") or 0
        fg_missed_30_39 = row.get("fg_missed_30_39") or 0
        fg_missed_40_49 = row.get("fg_missed_40_49") or 0
        fg_missed_50_59 = row.get("fg_missed_50_59") or 0
        fg_missed_60_ = row.get("fg_missed_60_") or 0
        
        fg_made_list = row.get("fg_made_list")
        fg_missed_list = row.get("fg_missed_list")
        fg_blocked_list = row.get("fg_blocked_list")
        fg_made_distance = row.get("fg_made_distance")
        fg_missed_distance = row.get("fg_missed_distance")
        fg_blocked_distance = row.get("fg_blocked_distance")
        
        # PATs
        pat_made = row.get("pat_made") or 0
        pat_att = row.get("pat_att") or 0
        pat_missed = row.get("pat_missed") or 0
        pat_blocked = row.get("pat_blocked") or 0
        pat_pct = row.get("pat_pct")
        
        # Game-winning FG
        gwfg_made = row.get("gwfg_made") or 0
        gwfg_att = row.get("gwfg_att") or 0
        gwfg_missed = row.get("gwfg_missed") or 0
        gwfg_blocked = row.get("gwfg_blocked") or 0
        gwfg_distance = row.get("gwfg_distance")
        
        # Derived efficiency metrics
        pass_yards_per_att = _safe_div(passing_yards, attempts)
        pass_epa_per_play = _safe_div(passing_epa, dropbacks if dropbacks and dropbacks > 0 else None)
        
        rush_yards_per_carry = _safe_div(rushing_yards, carries)
        rush_epa_per_carry = _safe_div(rushing_epa, carries if carries > 0 else None)
        
        record: Dict[str, Any] = {
            # Identity / game context
            "game_id": game_id,
            "team_id": team,  # you will map team abbrev -> team PK in your DB
            "opponent_team_id": opponent_team,
            "season": season,
            "week": week,
            "season_type": season_type,
            "home_away": home_away,
            
            # Result / scoreboard
            "points_for": points_for,
            "points_against": points_against,
            "point_diff": points_for - points_against if points_for is not None and points_against is not None else None,
            "result": result,
            
            # Pace / volume (mostly unavailable from nflreadpy)
            "total_plays": total_plays,
            "total_drives": None,  # not available
            "time_of_possession": None,  # not available
            
            # Passing offense
            "completions": int(completions),
            "attempts": int(attempts),
            "passing_yards": int(passing_yards),
            "passing_tds": int(passing_tds),
            "passing_interceptions": int(passing_interceptions),
            "sacks_suffered": int(sacks_suffered),
            "sack_yards_lost": int(sack_yards_lost),
            "sack_fumbles": int(sack_fumbles),
            "sack_fumbles_lost": int(sack_fumbles_lost),
            "passing_air_yards": int(passing_air_yards),
            "passing_yards_after_catch": int(passing_yards_after_catch),
            "passing_first_downs": int(passing_first_downs),
            "passing_epa": float(passing_epa) if passing_epa is not None else None,
            "passing_cpoe": float(passing_cpoe) if passing_cpoe is not None else None,
            "passing_2pt_conversions": int(passing_2pt_conversions),
            
            # Derived passing efficiency
            "pass_yards_per_att": pass_yards_per_att,
            "pass_epa_per_play": pass_epa_per_play,
            "pass_success_rate": pass_success_rate,
            "dropbacks": dropbacks,
            "neutral_pass_rate": None,  # would need to compute from pbp with game script
            
            # Rushing offense
            "carries": int(carries),
            "rushing_yards": int(rushing_yards),
            "rushing_tds": int(rushing_tds),
            "rushing_fumbles": int(rushing_fumbles),
            "rushing_fumbles_lost": int(rushing_fumbles_lost),
            "rushing_first_downs": int(rushing_first_downs),
            "rushing_epa": float(rushing_epa) if rushing_epa is not None else None,
            "rushing_2pt_conversions": int(rushing_2pt_conversions),
            
            # Derived rushing efficiency
            "rush_yards_per_carry": rush_yards_per_carry,
            "rush_epa_per_carry": rush_epa_per_carry,
            "rush_success_rate": rush_success_rate,
            
            # Receiving offense
            "receptions": int(receptions),
            "targets": int(targets),
            "receiving_yards": int(receiving_yards),
            "receiving_tds": int(receiving_tds),
            "receiving_fumbles": int(receiving_fumbles),
            "receiving_fumbles_lost": int(receiving_fumbles_lost),
            "receiving_air_yards": int(receiving_air_yards),
            "receiving_yards_after_catch": int(receiving_yards_after_catch),
            "receiving_first_downs": int(receiving_first_downs),
            "receiving_epa": float(receiving_epa) if receiving_epa is not None else None,
            "receiving_2pt_conversions": int(receiving_2pt_conversions),
            
            # Defense
            "def_tackles_solo": int(def_tackles_solo),
            "def_tackles_with_assist": int(def_tackles_with_assist),
            "def_tackle_assists": int(def_tackle_assists),
            "def_tackles_for_loss": int(def_tackles_for_loss),
            "def_tackles_for_loss_yards": int(def_tackles_for_loss_yards),
            "def_fumbles_forced": int(def_fumbles_forced),
            "def_sacks": float(def_sacks) if def_sacks is not None else None,
            "def_sack_yards": int(def_sack_yards),
            "def_qb_hits": int(def_qb_hits),
            "def_interceptions": int(def_interceptions),
            "def_interception_yards": int(def_interception_yards),
            "def_pass_defended": int(def_pass_defended),
            "def_tds": int(def_tds),
            "def_fumbles": int(def_fumbles),
            "def_safeties": int(def_safeties),
            
            # Defensive EPA (would need to compute from opponent's offensive plays)
            "defense_epa_total": None,
            "defense_epa_per_play": None,
            
            # Fumbles / misc
            "misc_yards": int(misc_yards),
            "fumble_recovery_own": int(fumble_recovery_own),
            "fumble_recovery_yards_own": int(fumble_recovery_yards_own),
            "fumble_recovery_opp": int(fumble_recovery_opp),
            "fumble_recovery_yards_opp": int(fumble_recovery_yards_opp),
            "fumble_recovery_tds": int(fumble_recovery_tds),
            
            # Penalties
            "penalties": int(penalties),
            "penalty_yards": int(penalty_yards),
            "timeouts": int(timeouts),
            
            # Returns / special teams
            "punt_returns": int(punt_returns),
            "punt_return_yards": int(punt_return_yards),
            "kickoff_returns": int(kickoff_returns),
            "kickoff_return_yards": int(kickoff_return_yards),
            "special_teams_tds": int(special_teams_tds),
            
            # Field goals
            "fg_made": int(fg_made),
            "fg_att": int(fg_att),
            "fg_missed": int(fg_missed),
            "fg_blocked": int(fg_blocked),
            "fg_long": int(fg_long) if fg_long is not None else None,
            "fg_pct": float(fg_pct) if fg_pct is not None else None,
            
            "fg_made_0_19": int(fg_made_0_19),
            "fg_made_20_29": int(fg_made_20_29),
            "fg_made_30_39": int(fg_made_30_39),
            "fg_made_40_49": int(fg_made_40_49),
            "fg_made_50_59": int(fg_made_50_59),
            "fg_made_60_": int(fg_made_60_),
            
            "fg_missed_0_19": int(fg_missed_0_19),
            "fg_missed_20_29": int(fg_missed_20_29),
            "fg_missed_30_39": int(fg_missed_30_39),
            "fg_missed_40_49": int(fg_missed_40_49),
            "fg_missed_50_59": int(fg_missed_50_59),
            "fg_missed_60_": int(fg_missed_60_),
            
            "fg_made_list": str(fg_made_list) if fg_made_list is not None else None,
            "fg_missed_list": str(fg_missed_list) if fg_missed_list is not None else None,
            "fg_blocked_list": str(fg_blocked_list) if fg_blocked_list is not None else None,
            "fg_made_distance": str(fg_made_distance) if fg_made_distance is not None else None,
            "fg_missed_distance": str(fg_missed_distance) if fg_missed_distance is not None else None,
            "fg_blocked_distance": str(fg_blocked_distance) if fg_blocked_distance is not None else None,
            
            # PATs
            "pat_made": int(pat_made),
            "pat_att": int(pat_att),
            "pat_missed": int(pat_missed),
            "pat_blocked": int(pat_blocked),
            "pat_pct": float(pat_pct) if pat_pct is not None else None,
            
            # Game-winning FG
            "gwfg_made": int(gwfg_made),
            "gwfg_att": int(gwfg_att),
            "gwfg_missed": int(gwfg_missed),
            "gwfg_blocked": int(gwfg_blocked),
            "gwfg_distance": int(gwfg_distance) if gwfg_distance is not None else None,
        }
        
        results.append(record)
    
    return results
