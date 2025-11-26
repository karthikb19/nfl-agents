import os
import psycopg2
from dotenv import load_dotenv, find_dotenv

def create_teams_table():
    """Create the teams table if it doesn't exist."""
    # Load environment variables
    load_dotenv(find_dotenv())
    
    # Get database URL from environment
    db_url = os.getenv('SUPABASE_DB_URL')
    
    if not db_url:
        raise ValueError("SUPABASE_DB_URL not found in environment variables")
    
    # Remove pgbouncer parameter if present (not supported by psycopg2)
    if '?pgbouncer=' in db_url:
        db_url = db_url.split('?pgbouncer=')[0]
    
    # Connect to the database
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    try:
        # Create teams table if it doesn't exist
        create_table_query = """
        CREATE TABLE IF NOT EXISTS teams (
            id SERIAL PRIMARY KEY,
            team_id INTEGER,
            team_abbr VARCHAR(10),
            team_name VARCHAR(100),
            team_nick VARCHAR(100),
            team_conf VARCHAR(10),
            team_division VARCHAR(10),
            team_color VARCHAR(20),
            team_color2 VARCHAR(20),
            team_color3 VARCHAR(20),
            team_color4 VARCHAR(20),
            team_logo_wikipedia TEXT
        );
        """
        
        cursor.execute(create_table_query)
        conn.commit()
        
        print("✓ Teams table created successfully (or already exists)")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Error creating teams table: {e}")
        raise
    
    finally:
        cursor.close()
        conn.close()

def create_players_table():
    """Create the players table if it doesn't exist."""
    # Load environment variables
    load_dotenv(find_dotenv())
    
    # Get database URL from environment
    db_url = os.getenv('SUPABASE_DB_URL')
    
    if not db_url:
        raise ValueError("SUPABASE_DB_URL not found in environment variables")
    
    # Remove pgbouncer parameter if present (not supported by psycopg2)
    if '?pgbouncer=' in db_url:
        db_url = db_url.split('?pgbouncer=')[0]
    
    # Connect to the database
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    try:
        # Create players table if it doesn't exist
        create_table_query = """
        CREATE TABLE IF NOT EXISTS players (
            gsis_id VARCHAR(50) PRIMARY KEY,
            nfl_id VARCHAR(50) UNIQUE,
            pfr_id VARCHAR(50) UNIQUE,
            espn_id VARCHAR(50) UNIQUE,


            display_name VARCHAR(100),
            common_first_name VARCHAR(50),
            first_name VARCHAR(50),
            last_name VARCHAR(50),
            short_name VARCHAR(50),
            football_name VARCHAR(50),
            suffix VARCHAR(10),


            birth_date DATE,
            position_group VARCHAR(20),
            position VARCHAR(10),
            height SMALLINT,
            weight SMALLINT,
            headshot TEXT,
            college_name VARCHAR(100),
            college_conference VARCHAR(50),


            jersey_number SMALLINT,
            rookie_season SMALLINT,
            last_season SMALLINT,
            latest_team_id INTEGER,
            status VARCHAR(20),
            years_of_experience SMALLINT,
            draft_year SMALLINT,
            draft_round SMALLINT,
            draft_pick SMALLINT,
            draft_team_id INTEGER,
            FOREIGN KEY (latest_team_id) REFERENCES teams(id),
            FOREIGN KEY (draft_team_id) REFERENCES teams(id)
        );
        """
        
        cursor.execute(create_table_query)
        conn.commit()
        
        print("✓ Players table created successfully (or already exists)")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Error creating players table: {e}")
        raise
    
    finally:
        cursor.close()
        conn.close()

def create_player_aliases_table():
    load_dotenv(find_dotenv())
    
    # Get database URL from environment
    db_url = os.getenv('SUPABASE_DB_URL')
    
    if not db_url:
        raise ValueError("SUPABASE_DB_URL not found in environment variables")
    
    # Remove pgbouncer parameter if present (not supported by psycopg2)
    if '?pgbouncer=' in db_url:
        db_url = db_url.split('?pgbouncer=')[0]
    
    # Connect to the database
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    try:
        # Create players table if it doesn't exist
        create_table_query = """
        CREATE TABLE IF NOT EXISTS player_aliases (
            alias_id    INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            player_id   TEXT NOT NULL REFERENCES players(gsis_id)
                        ON DELETE CASCADE,
            alias       TEXT NOT NULL,
            created_at  TIMESTAMP DEFAULT NOW(),

            UNIQUE(player_id, alias)
        );

        """
        
        cursor.execute(create_table_query)
        conn.commit()
        
        print("✓ Players Aliases table created successfully (or already exists)")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Error creating players aliases table: {e}")
        raise
    
    finally:
        cursor.close()
        conn.close() 

def create_player_game_stats_table():
    load_dotenv(find_dotenv())
    db_url = os.getenv('SUPABASE_DB_URL')
    
    if not db_url:
        raise ValueError("SUPABASE_DB_URL not found in environment variables")
    
    if '?pgbouncer=' in db_url:
        db_url = db_url.split('?pgbouncer=')[0]
    
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    try:
        create_table_query = """
        CREATE TABLE IF NOT EXISTS player_game_stats (
            id              BIGSERIAL PRIMARY KEY,
            player_id       TEXT NOT NULL
                                REFERENCES players(gsis_id) ON DELETE CASCADE,
            game_id         TEXT,

            season          SMALLINT NOT NULL,
            week            SMALLINT NOT NULL,
            team_id         INTEGER REFERENCES teams(id),
            opponent_team_id INTEGER REFERENCES teams(id),
            home_away       TEXT CHECK (home_away IN ('HOME', 'AWAY')),
            game_type       TEXT CHECK (game_type IN ('REG', 'POST', 'PRE')),

            snaps_offense       INTEGER,
            snaps_offense_pct   DOUBLE PRECISION,

            pass_att        INTEGER NOT NULL DEFAULT 0,
            pass_cmp        INTEGER NOT NULL DEFAULT 0,
            pass_yards      INTEGER NOT NULL DEFAULT 0,
            pass_td         INTEGER NOT NULL DEFAULT 0,
            interceptions   INTEGER NOT NULL DEFAULT 0,
            sacks           INTEGER NOT NULL DEFAULT 0,
            sack_yards      INTEGER NOT NULL DEFAULT 0,
            pass_first_downs    INTEGER NOT NULL DEFAULT 0,
            pass_air_yards      INTEGER NOT NULL DEFAULT 0,
            pass_yac_yards      INTEGER NOT NULL DEFAULT 0,
            pass_yards_per_att  DOUBLE PRECISION,
            pass_any_a          DOUBLE PRECISION,
            passer_rating       DOUBLE PRECISION,
            cpoe                DOUBLE PRECISION,
            pass_epa_total      DOUBLE PRECISION,
            pass_epa_per_play   DOUBLE PRECISION,
            pass_success_rate   DOUBLE PRECISION,

            rush_att        INTEGER NOT NULL DEFAULT 0,
            rush_yards      INTEGER NOT NULL DEFAULT 0,
            rush_td         INTEGER NOT NULL DEFAULT 0,
            rush_long       INTEGER,
            rush_first_downs    INTEGER NOT NULL DEFAULT 0,
            rush_fumbles        INTEGER NOT NULL DEFAULT 0,
            rush_epa_total      DOUBLE PRECISION,
            rush_epa_per_carry  DOUBLE PRECISION,
            rush_success_rate   DOUBLE PRECISION,

            targets         INTEGER NOT NULL DEFAULT 0,
            receptions      INTEGER NOT NULL DEFAULT 0,
            rec_yards       INTEGER NOT NULL DEFAULT 0,
            rec_td          INTEGER NOT NULL DEFAULT 0,
            rec_long        INTEGER,
            rec_first_downs     INTEGER NOT NULL DEFAULT 0,
            rec_air_yards       INTEGER NOT NULL DEFAULT 0,
            rec_yac_yards       INTEGER NOT NULL DEFAULT 0,
            rec_epa_total       DOUBLE PRECISION,
            rec_epa_per_target  DOUBLE PRECISION,
            rec_success_rate    DOUBLE PRECISION,

            team_pass_att       INTEGER,
            team_rush_att       INTEGER,
            team_targets        INTEGER,
            team_air_yards      INTEGER,
            target_share        DOUBLE PRECISION,
            air_yards_share     DOUBLE PRECISION,
            rush_attempt_share  DOUBLE PRECISION,

            fantasy_points      DOUBLE PRECISION,
            fantasy_points_ppr  DOUBLE PRECISION,

            -- Bookkeeping
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            -- Avoid dup rows per player/game when game_id is known
            UNIQUE (player_id, game_id)    
        );
        """
        
        cursor.execute(create_table_query)
        conn.commit()
        
        print("✓ Player game stats table created successfully (or already exists)")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Error creating player game stats table: {e}")
        raise
    
    finally:
        cursor.close()
        conn.close()

def create_team_game_stats_table():
    load_dotenv(find_dotenv())
    db_url = os.getenv('SUPABASE_DB_URL')
    
    if not db_url:
        raise ValueError("SUPABASE_DB_URL not found in environment variables")
    
    if '?pgbouncer=' in db_url:
        db_url = db_url.split('?pgbouncer=')[0]
    
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    try:
        create_table_query = """
        CREATE TABLE IF NOT EXISTS team_game_stats (
            id                  BIGSERIAL PRIMARY KEY,

            -- nflreadpy / nflfastR game id (same as player_game_stats)
            game_id             TEXT,

            season              SMALLINT NOT NULL,
            week                SMALLINT NOT NULL,
            game_type           TEXT CHECK (game_type IN ('REG', 'POST', 'PRE')),

            team_id             INTEGER NOT NULL REFERENCES teams(id),
            opponent_team_id    INTEGER REFERENCES teams(id),
            home_away           TEXT CHECK (home_away IN ('HOME', 'AWAY')),

            -- Result / scoreboard
            points_for          INTEGER,
            points_against      INTEGER,
            point_diff          INTEGER,
            result              TEXT CHECK (result IN ('W', 'L', 'T')),

            -- Pace / volume
            total_plays         INTEGER,
            total_drives        INTEGER,
            time_of_possession  INTERVAL,

            -- Passing offense
            completions                 INTEGER NOT NULL DEFAULT 0,
            attempts                    INTEGER NOT NULL DEFAULT 0,
            passing_yards               INTEGER NOT NULL DEFAULT 0,
            passing_tds                 INTEGER NOT NULL DEFAULT 0,
            passing_interceptions       INTEGER NOT NULL DEFAULT 0,
            sacks_suffered              INTEGER NOT NULL DEFAULT 0,
            sack_yards_lost             INTEGER NOT NULL DEFAULT 0,
            sack_fumbles                INTEGER NOT NULL DEFAULT 0,
            sack_fumbles_lost           INTEGER NOT NULL DEFAULT 0,
            passing_air_yards           INTEGER NOT NULL DEFAULT 0,
            passing_yards_after_catch   INTEGER NOT NULL DEFAULT 0,
            passing_first_downs         INTEGER NOT NULL DEFAULT 0,
            passing_epa                 DOUBLE PRECISION,
            passing_cpoe                DOUBLE PRECISION,
            passing_2pt_conversions     INTEGER NOT NULL DEFAULT 0,

            -- Derived passing efficiency
            pass_yards_per_att          DOUBLE PRECISION,
            pass_epa_per_play           DOUBLE PRECISION,
            pass_success_rate           DOUBLE PRECISION,
            dropbacks                   INTEGER,
            neutral_pass_rate           DOUBLE PRECISION,

            -- Rushing offense
            carries                     INTEGER NOT NULL DEFAULT 0,
            rushing_yards               INTEGER NOT NULL DEFAULT 0,
            rushing_tds                 INTEGER NOT NULL DEFAULT 0,
            rushing_fumbles             INTEGER NOT NULL DEFAULT 0,
            rushing_fumbles_lost        INTEGER NOT NULL DEFAULT 0,
            rushing_first_downs         INTEGER NOT NULL DEFAULT 0,
            rushing_epa                 DOUBLE PRECISION,
            rushing_2pt_conversions     INTEGER NOT NULL DEFAULT 0,

            -- Derived rushing efficiency
            rush_yards_per_carry        DOUBLE PRECISION,
            rush_epa_per_carry          DOUBLE PRECISION,
            rush_success_rate           DOUBLE PRECISION,

            -- Receiving offense
            receptions                  INTEGER NOT NULL DEFAULT 0,
            targets                     INTEGER NOT NULL DEFAULT 0,
            receiving_yards             INTEGER NOT NULL DEFAULT 0,
            receiving_tds               INTEGER NOT NULL DEFAULT 0,
            receiving_fumbles           INTEGER NOT NULL DEFAULT 0,
            receiving_fumbles_lost      INTEGER NOT NULL DEFAULT 0,
            receiving_air_yards         INTEGER NOT NULL DEFAULT 0,
            receiving_yards_after_catch INTEGER NOT NULL DEFAULT 0,
            receiving_first_downs       INTEGER NOT NULL DEFAULT 0,
            receiving_epa               DOUBLE PRECISION,
            receiving_2pt_conversions   INTEGER NOT NULL DEFAULT 0,

            -- Defense
            def_tackles_solo            INTEGER NOT NULL DEFAULT 0,
            def_tackles_with_assist     INTEGER NOT NULL DEFAULT 0,
            def_tackle_assists          INTEGER NOT NULL DEFAULT 0,
            def_tackles_for_loss        INTEGER NOT NULL DEFAULT 0,
            def_tackles_for_loss_yards  INTEGER NOT NULL DEFAULT 0,
            def_fumbles_forced          INTEGER NOT NULL DEFAULT 0,
            def_sacks                   DOUBLE PRECISION,
            def_sack_yards              INTEGER NOT NULL DEFAULT 0,
            def_qb_hits                 INTEGER NOT NULL DEFAULT 0,
            def_interceptions           INTEGER NOT NULL DEFAULT 0,
            def_interception_yards      INTEGER NOT NULL DEFAULT 0,
            def_pass_defended           INTEGER NOT NULL DEFAULT 0,
            def_tds                     INTEGER NOT NULL DEFAULT 0,
            def_fumbles                 INTEGER NOT NULL DEFAULT 0,
            def_safeties                INTEGER NOT NULL DEFAULT 0,

            defense_epa_total           DOUBLE PRECISION,
            defense_epa_per_play        DOUBLE PRECISION,

            -- Fumbles / misc
            misc_yards                  INTEGER NOT NULL DEFAULT 0,
            fumble_recovery_own         INTEGER NOT NULL DEFAULT 0,
            fumble_recovery_yards_own   INTEGER NOT NULL DEFAULT 0,
            fumble_recovery_opp         INTEGER NOT NULL DEFAULT 0,
            fumble_recovery_yards_opp   INTEGER NOT NULL DEFAULT 0,
            fumble_recovery_tds         INTEGER NOT NULL DEFAULT 0,

            -- Penalties
            penalties                   INTEGER NOT NULL DEFAULT 0,
            penalty_yards               INTEGER NOT NULL DEFAULT 0,
            timeouts                    INTEGER NOT NULL DEFAULT 0,

            -- Returns / special teams
            punt_returns                INTEGER NOT NULL DEFAULT 0,
            punt_return_yards           INTEGER NOT NULL DEFAULT 0,
            kickoff_returns             INTEGER NOT NULL DEFAULT 0,
            kickoff_return_yards        INTEGER NOT NULL DEFAULT 0,
            special_teams_tds           INTEGER NOT NULL DEFAULT 0,

            -- Field goals
            fg_made                     INTEGER NOT NULL DEFAULT 0,
            fg_att                      INTEGER NOT NULL DEFAULT 0,
            fg_missed                   INTEGER NOT NULL DEFAULT 0,
            fg_blocked                  INTEGER NOT NULL DEFAULT 0,
            fg_long                     INTEGER,
            fg_pct                      DOUBLE PRECISION,

            fg_made_0_19                INTEGER NOT NULL DEFAULT 0,
            fg_made_20_29               INTEGER NOT NULL DEFAULT 0,
            fg_made_30_39               INTEGER NOT NULL DEFAULT 0,
            fg_made_40_49               INTEGER NOT NULL DEFAULT 0,
            fg_made_50_59               INTEGER NOT NULL DEFAULT 0,
            fg_made_60_                 INTEGER NOT NULL DEFAULT 0,

            fg_missed_0_19              INTEGER NOT NULL DEFAULT 0,
            fg_missed_20_29             INTEGER NOT NULL DEFAULT 0,
            fg_missed_30_39             INTEGER NOT NULL DEFAULT 0,
            fg_missed_40_49             INTEGER NOT NULL DEFAULT 0,
            fg_missed_50_59             INTEGER NOT NULL DEFAULT 0,
            fg_missed_60_               INTEGER NOT NULL DEFAULT 0,

            fg_made_list                TEXT,
            fg_missed_list              TEXT,
            fg_blocked_list             TEXT,
            fg_made_distance            TEXT,
            fg_missed_distance          TEXT,
            fg_blocked_distance         TEXT,

            -- PATs
            pat_made                    INTEGER NOT NULL DEFAULT 0,
            pat_att                     INTEGER NOT NULL DEFAULT 0,
            pat_missed                  INTEGER NOT NULL DEFAULT 0,
            pat_blocked                 INTEGER NOT NULL DEFAULT 0,
            pat_pct                     DOUBLE PRECISION,

            -- Game-winning FG
            gwfg_made                   INTEGER NOT NULL DEFAULT 0,
            gwfg_att                    INTEGER NOT NULL DEFAULT 0,
            gwfg_missed                 INTEGER NOT NULL DEFAULT 0,
            gwfg_blocked                INTEGER NOT NULL DEFAULT 0,
            gwfg_distance               INTEGER,

            -- Bookkeeping
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            -- Avoid dup rows per team/game
            UNIQUE (team_id, game_id)
        );
        """
        
        cursor.execute(create_table_query)
        conn.commit()
        
        print("✓ Team game stats table created successfully (or already exists)")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Error creating team game stats table: {e}")
        raise
    
    finally:
        cursor.close()
        conn.close()

def main():
    load_dotenv(find_dotenv())
    # create_teams_table()
    # create_players_table()   
    # create_player_aliases_table()
    # create_player_game_stats_table()
    create_team_game_stats_table()

if __name__ == "__main__":
    main()