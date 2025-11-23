```
CREATE TABLE player_game_stats (
    id                  BIGSERIAL PRIMARY KEY,

    player_id           BIGINT NOT NULL REFERENCES players(id),
    game_id             BIGINT NOT NULL REFERENCES games(id),

    season              INT NOT NULL,
    week                INT NOT NULL,
    team_id             BIGINT NOT NULL REFERENCES teams(id),
    opponent_team_id    BIGINT NOT NULL REFERENCES teams(id),
    home_away           TEXT NOT NULL,       -- 'HOME' or 'AWAY'
    game_type           TEXT NOT NULL,       -- 'REG','POST','PRE'

    snaps_offense       INT,                 -- if you ingest snap counts
    snaps_offense_pct   REAL,                -- percentage of team offensive snaps

    -- -------- Passing (primarily QBs, but works for WR passes, etc.) --------
    pass_att            INT DEFAULT 0,
    pass_cmp            INT DEFAULT 0,
    pass_yards          INT DEFAULT 0,
    pass_td             INT DEFAULT 0,
    interceptions       INT DEFAULT 0,

    sacks               INT DEFAULT 0,
    sack_yards          INT DEFAULT 0,

    pass_first_downs    INT DEFAULT 0,
    pass_air_yards      INT DEFAULT 0,       -- sum of air_yards
    pass_yac_yards      INT DEFAULT 0,       -- yards after catch from passes

    -- Passing efficiency / advanced
    pass_yards_per_att  REAL,               -- pass_yards / pass_att
    pass_any_a          REAL,               -- Adjusted Net Yards/Attempt
    passer_rating       REAL,               -- NFL formula, season-level recomputed later
    cpoe                REAL,               -- completion % over expected (avg over plays)
    pass_epa_total      REAL,               -- sum of EPA on pass plays
    pass_epa_per_play   REAL,               -- pass_epa_total / pass_dropbacks (or pass_att + sacks)
    pass_success_rate   REAL,               -- fraction of pass plays with EPA > 0

    -- -------- Rushing (QB or RB/WR, doesn’t matter) --------
    rush_att            INT DEFAULT 0,
    rush_yards          INT DEFAULT 0,
    rush_td             INT DEFAULT 0,
    rush_long           INT,                -- longest rush
    rush_first_downs    INT DEFAULT 0,
    rush_fumbles        INT DEFAULT 0,

    rush_epa_total      REAL,
    rush_epa_per_carry  REAL,
    rush_success_rate   REAL,               -- EPA > 0 on rush plays

    -- -------- Receiving (WR/TE/RB, but also QBs on trick plays) --------
    targets             INT DEFAULT 0,
    receptions          INT DEFAULT 0,
    rec_yards           INT DEFAULT 0,
    rec_td              INT DEFAULT 0,
    rec_long            INT,
    rec_first_downs     INT DEFAULT 0,

    rec_air_yards       INT DEFAULT 0,
    rec_yac_yards       INT DEFAULT 0,

    rec_epa_total       REAL,
    rec_epa_per_target  REAL,
    rec_success_rate    REAL,               -- EPA > 0 on targets

    -- -------- Usage / share metrics (relative to team in that game) --------
    team_pass_att       INT,                -- total team pass attempts that game
    team_rush_att       INT,                -- total team rush attempts
    team_targets        INT,                -- total team targets
    team_air_yards      INT,                -- total team air yards

    target_share        REAL,               -- targets / team_targets
    air_yards_share     REAL,               -- rec_air_yards / team_air_yards
    rush_attempt_share  REAL,               -- rush_att / team_rush_att

    -- -------- Fantasy / composite --------
    fantasy_points      REAL,               -- standard scoring
    fantasy_points_ppr  REAL,               -- PPR scoring

    -- Audit
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (player_id, game_id)
);
```