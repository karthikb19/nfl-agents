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
    
    create_teams_table()
    create_players_table()   
    create_player_aliases_table()
    create_player_game_stats_table()
    create_team_game_stats_table()

if __name__ == "__main__":
    main()