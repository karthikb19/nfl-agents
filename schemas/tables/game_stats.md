```
CREATE TABLE team_game_stats (
    id                  BIGSERIAL PRIMARY KEY,

    -- Identity / joins
    game_id             BIGINT NOT NULL REFERENCES games(id),
    team_id             BIGINT NOT NULL REFERENCES teams(id),
    opponent_team_id    BIGINT NOT NULL REFERENCES teams(id),

    season              INT NOT NULL,
    week                INT NOT NULL,
    season_type         TEXT NOT NULL,          -- 'REG','POST','PRE'
    home_away           TEXT NOT NULL,          -- 'HOME','AWAY'

    -- Result / scoreboard
    points_for          INT NOT NULL,
    points_against      INT NOT NULL,
    point_diff          INT GENERATED ALWAYS AS (points_for - points_against) STORED,
    result              TEXT NOT NULL,          -- 'W','L','T'

    -- Pace / volume (you’ll derive from PBP)
    total_plays         INT,                    -- offensive plays
    total_drives        INT,
    time_of_possession  INTERVAL,

    -- ---------------- Passing offense ----------------
    completions                     INT,
    attempts                        INT,
    passing_yards                   INT,
    passing_tds                     INT,
    passing_interceptions           INT,
    sacks_suffered                  INT,
    sack_yards_lost                 INT,
    sack_fumbles                    INT,
    sack_fumbles_lost               INT,
    passing_air_yards               INT,
    passing_yards_after_catch       INT,
    passing_first_downs             INT,
    passing_epa                     REAL,
    passing_cpoe                    REAL,
    passing_2pt_conversions         INT,

    -- Derived passing efficiency
    pass_yards_per_att              REAL,
    pass_epa_per_play               REAL,
    pass_success_rate               REAL,       -- % of pass plays with EPA > 0
    dropbacks                       INT,        -- attempts + sacks + scrambles
    neutral_pass_rate               REAL,       -- pass% in neutral situations if you compute it

    -- ---------------- Rushing offense ----------------
    carries                         INT,
    rushing_yards                   INT,
    rushing_tds                     INT,
    rushing_fumbles                 INT,
    rushing_fumbles_lost            INT,
    rushing_first_downs             INT,
    rushing_epa                     REAL,
    rushing_2pt_conversions         INT,

    -- Derived rushing efficiency
    rush_yards_per_carry            REAL,
    rush_epa_per_carry              REAL,
    rush_success_rate               REAL,

    -- ---------------- Receiving offense ----------------
    receptions                      INT,
    targets                         INT,
    receiving_yards                 INT,
    receiving_tds                   INT,
    receiving_fumbles               INT,
    receiving_fumbles_lost          INT,
    receiving_air_yards             INT,
    receiving_yards_after_catch     INT,
    receiving_first_downs           INT,
    receiving_epa                   REAL,
    receiving_2pt_conversions       INT,

    -- ---------------- Defense ----------------
    def_tackles_solo                INT,
    def_tackles_with_assist         INT,
    def_tackle_assists              INT,
    def_tackles_for_loss            INT,
    def_tackles_for_loss_yards      INT,
    def_fumbles_forced              INT,
    def_sacks                       REAL,       -- can be .5
    def_sack_yards                  INT,
    def_qb_hits                     INT,
    def_interceptions               INT,
    def_interception_yards          INT,
    def_pass_defended               INT,
    def_tds                         INT,
    def_fumbles                     INT,
    def_safeties                    INT,

    -- (Optionally) defensive EPA split if you compute it:
    defense_epa_total               REAL,
    defense_epa_per_play            REAL,

    -- ---------------- Fumbles / misc ----------------
    misc_yards                      INT,
    fumble_recovery_own             INT,
    fumble_recovery_yards_own       INT,
    fumble_recovery_opp             INT,
    fumble_recovery_yards_opp       INT,
    fumble_recovery_tds             INT,

    -- ---------------- Penalties ----------------
    penalties                       INT,
    penalty_yards                   INT,
    timeouts                        INT,

    -- ---------------- Returns / special teams ----------------
    punt_returns                    INT,
    punt_return_yards               INT,
    kickoff_returns                 INT,
    kickoff_return_yards            INT,
    special_teams_tds               INT,

    -- Field goals
    fg_made                         INT,
    fg_att                          INT,
    fg_missed                       INT,
    fg_blocked                      INT,
    fg_long                         INT,
    fg_pct                          REAL,

    fg_made_0_19                    INT,
    fg_made_20_29                   INT,
    fg_made_30_39                   INT,
    fg_made_40_49                   INT,
    fg_made_50_59                   INT,
    fg_made_60_                     INT,

    fg_missed_0_19                  INT,
    fg_missed_20_29                 INT,
    fg_missed_30_39                 INT,
    fg_missed_40_49                 INT,
    fg_missed_50_59                 INT,
    fg_missed_60_                   INT,

    fg_made_list                    TEXT,
    fg_missed_list                  TEXT,
    fg_blocked_list                 TEXT,
    fg_made_distance                TEXT,
    fg_missed_distance              TEXT,
    fg_blocked_distance             TEXT,

    -- PATs
    pat_made                        INT,
    pat_att                         INT,
    pat_missed                      INT,
    pat_blocked                     INT,
    pat_pct                         REAL,

    -- Game-winning FG info
    gwfg_made                       INT,
    gwfg_att                        INT,
    gwfg_missed                     INT,
    gwfg_blocked                    INT,
    gwfg_distance                   INT,

    created_at                      TIMESTAMPTZ DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (team_id, game_id)
);

CREATE INDEX idx_tgs_team_season_week ON team_game_stats(team_id, season, week);
CREATE INDEX idx_tgs_season_week ON team_game_stats(season, week);
```