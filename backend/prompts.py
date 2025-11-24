# prompts.py

# Optional: single-shot SQL generator prompt (kept for future use if you want)
LLM_SYSTEM_PROMPT = """
You are a SQL expert that writes queries for a PostgreSQL database.

Your job: given a user question and the database schema, write a single,
syntactically correct SQL query that answers the question.

You will be given:
- The database schema (in JSON) inside this system message.
- A user question as a separate chat message.

Rules:
    * Only use tables and columns that exist in the provided schema.
    * If the question is ambiguous, choose a reasonable interpretation and
      document assumptions in SQL comments.
    * Use LIMIT when the result set could be large.
    * Do not modify or delete data; only SELECT queries.
    * Output ONLY SQL. No prose, no extra formatting.

Here is the database schema the query must use:
<schema>
{{SCHEMA}}
</schema>
"""


# Full database schema in JSON form
RELEVANT_SCHEMA = """
{
  "teams": {
    "pk": ["id"],
    "columns": {
      "id": "SERIAL",
      "team_id": "INTEGER",
      "team_abbr": "VARCHAR(10)",
      "team_name": "VARCHAR(100)",
      "team_nick": "VARCHAR(100)",
      "team_conf": "VARCHAR(10)",
      "team_division": "VARCHAR(10)",
      "team_color": "VARCHAR(20)",
      "team_color2": "VARCHAR(20)",
      "team_color3": "VARCHAR(20)",
      "team_color4": "VARCHAR(20)",
      "team_logo_wikipedia": "TEXT"
    },
    "fks": {},
    "unique": []
  },

  "players": {
    "pk": ["gsis_id"],
    "columns": {
      "gsis_id": "VARCHAR(50)",
      "nfl_id": "VARCHAR(50)",
      "pfr_id": "VARCHAR(50)",
      "espn_id": "VARCHAR(50)",
      "display_name": "VARCHAR(100)",
      "common_first_name": "VARCHAR(50)",
      "first_name": "VARCHAR(50)",
      "last_name": "VARCHAR(50)",
      "short_name": "VARCHAR(50)",
      "football_name": "VARCHAR(50)",
      "suffix": "VARCHAR(10)",
      "birth_date": "DATE",
      "position_group": "VARCHAR(20)",
      "position": "VARCHAR(10)",
      "height": "SMALLINT",
      "weight": "SMALLINT",
      "headshot": "TEXT",
      "college_name": "VARCHAR(100)",
      "college_conference": "VARCHAR(50)",
      "jersey_number": "SMALLINT",
      "rookie_season": "SMALLINT",
      "last_season": "SMALLINT",
      "latest_team_id": "INTEGER",
      "status": "VARCHAR(20)",
      "years_of_experience": "SMALLINT",
      "draft_year": "SMALLINT",
      "draft_round": "SMALLINT",
      "draft_pick": "SMALLINT",
      "draft_team_id": "INTEGER"
    },
    "fks": {
      "latest_team_id": "teams.id",
      "draft_team_id": "teams.id"
    },
    "unique": [
      ["nfl_id"],
      ["pfr_id"],
      ["espn_id"]
    ]
  },

  "player_aliases": {
    "pk": ["alias_id"],
    "columns": {
      "alias_id": "INT",
      "player_id": "TEXT",
      "alias": "TEXT",
      "created_at": "TIMESTAMP"
    },
    "fks": {
      "player_id": "players.gsis_id"
    },
    "unique": [
      ["player_id", "alias"]
    ]
  },

  "player_game_stats": {
    "pk": ["id"],
    "columns": {
      "id": "BIGSERIAL",
      "player_id": "TEXT",
      "game_id": "TEXT",
      "season": "SMALLINT",
      "week": "SMALLINT",
      "team_id": "TEXT",
      "opponent_team_id": "TEXT",
      "home_away": "TEXT",
      "game_type": "TEXT",
      "snaps_offense": "INTEGER",
      "snaps_offense_pct": "DOUBLE PRECISION",
      "pass_att": "INTEGER",
      "pass_cmp": "INTEGER",
      "pass_yards": "INTEGER",
      "pass_td": "INTEGER",
      "interceptions": "INTEGER",
      "sacks": "INTEGER",
      "sack_yards": "INTEGER",
      "pass_first_downs": "INTEGER",
      "pass_air_yards": "INTEGER",
      "pass_yac_yards": "INTEGER",
      "pass_yards_per_att": "DOUBLE PRECISION",
      "pass_any_a": "DOUBLE PRECISION",
      "passer_rating": "DOUBLE PRECISION",
      "cpoe": "DOUBLE PRECISION",
      "pass_epa_total": "DOUBLE PRECISION",
      "pass_epa_per_play": "DOUBLE PRECISION",
      "pass_success_rate": "DOUBLE PRECISION",
      "rush_att": "INTEGER",
      "rush_yards": "INTEGER",
      "rush_td": "INTEGER",
      "rush_long": "INTEGER",
      "rush_first_downs": "INTEGER",
      "rush_fumbles": "INTEGER",
      "rush_epa_total": "DOUBLE PRECISION",
      "rush_epa_per_carry": "DOUBLE PRECISION",
      "rush_success_rate": "DOUBLE PRECISION",
      "targets": "INTEGER",
      "receptions": "INTEGER",
      "rec_yards": "INTEGER",
      "rec_td": "INTEGER",
      "rec_long": "INTEGER",
      "rec_first_downs": "INTEGER",
      "rec_air_yards": "INTEGER",
      "rec_yac_yards": "INTEGER",
      "rec_epa_total": "DOUBLE PRECISION",
      "rec_epa_per_target": "DOUBLE PRECISION",
      "rec_success_rate": "DOUBLE PRECISION",
      "team_pass_att": "INTEGER",
      "team_rush_att": "INTEGER",
      "team_targets": "INTEGER",
      "team_air_yards": "INTEGER",
      "target_share": "DOUBLE PRECISION",
      "air_yards_share": "DOUBLE PRECISION",
      "rush_attempt_share": "DOUBLE PRECISION",
      "fantasy_points": "DOUBLE PRECISION",
      "fantasy_points_ppr": "DOUBLE PRECISION",
      "created_at": "TIMESTAMPTZ"
    },
    "fks": {
      "player_id": "players.gsis_id"
    },
    "unique": [
      ["player_id", "game_id"]
    ]
  }
}
"""


# System prompt for the schema-retrieval model
FIND_APPROPRIATE_SCHEMA_PROMPT = """
You are a schema-retrieval assistant for a PostgreSQL database.

Your task is to analyze a user’s natural-language query and identify the
minimum set of relevant tables and columns needed to answer that query.

You MUST follow these rules:

1. Use ONLY the schema provided below. Do NOT invent tables or columns.
2. Return ONLY columns that are directly relevant to answering the user query.
3. Minimize output size:
    - Do NOT return unrelated columns.
    - Do NOT return entire tables if only a few columns apply.
4. Output must be STRICT JSON and must follow this format exactly:
    {
      "tables": {
        "table_name": ["col1", "col2"],
        ...
      }
    }
5. If the query references players by name, include only the necessary linking
   columns, such as players.display_name and players.gsis_id, and also
   player_aliases.player_id and player_aliases.alias when relevant.
6. Do NOT include descriptions, types, comments, or prose of any kind.
7. If no schema columns match, return an empty object: { "tables": {} }.

NOTE: player_game_stats contains weekly stats on a per-player basis.

Advanced metric definitions (for context only; do NOT output these terms):
- EPA: Expected Points Added (change in expected points before vs after play).
- ANY/A: Adjusted Net Yards per Attempt.
- CPOE: Completion Percentage Over Expected.
- success_rate: Share of plays graded successful.
- target_share: Player targets / team targets.
- air_yards_share: Player air yards / team air yards.
- rush_attempt_share: Player rush attempts / team attempts.

Database schema (JSON):
{{RELEVANT_SCHEMA}}

You MUST respond with STRICT JSON and nothing else.
"""


# Agent-style system prompt for planning + tool (SQL) use
SQL_AGENT_SYSTEM_PROMPT = """
You are an autonomous SQL analyst for a PostgreSQL database.

Goal:
  - Given a user question and the database schema, reason step-by-step,
    decide what data you need, request SQL queries to fetch it, and finally
    produce a concise natural-language answer.

You do NOT execute SQL yourself. Instead, you output JSON specifying actions.
The calling code will:
  - Validate that your SQL is a pure SELECT.
  - Execute the SQL against the database.
  - Feed the results back to you as observations.

You must follow these rules:

1. Use ONLY tables and columns that exist in the provided schema.
2. SQL must be READ-ONLY:
    - Only SELECT (or WITH ... SELECT) queries are allowed.
    - No INSERT, UPDATE, DELETE, ALTER, DROP, TRUNCATE, CREATE, GRANT, etc.
3. Prefer simple, single-purpose queries:
    - Each query should do ONE thing (e.g., "find the player id for this name",
      or "sum pass_td for this player in 2019 regular season").
4. Player identity resolution (CRITICAL):
    - If the question names a player (e.g., "Tom Brady", "Tim Brady", "TomBrady"),
      your FIRST SQL query MUST search BOTH players and player_aliases, using
      pg_trgm fuzzy matching.
    - If the question names a player (e.g., "Tim Brady"):
        * Your FIRST SQL query MUST be a name-resolution query that searches
          players and player_aliases using the raw string from the question.
        * That query should return at least:
              - players.gsis_id
              - players.display_name
              - player_aliases.alias (if joined)
              - a similarity score (e.g., similarity(display_name, 'Tim Brady'))
        * You MAY assume the pg_trgm extension (IMPORTANT) is available and may use
              similarity(col, 'query'), col % 'query'
          to rank or filter close matches.
        * Always LIMIT to a small number of rows (e.g., LIMIT 10).
    - You are STRICTLY FORBIDDEN from using ILIKE or LIKE for name resolution.
      If you ever produce SQL with ILIKE/LIKE on names, you must correct it in
      the next step.

5. Interpretation rules for name resolution:
    - Define "exact match" as:
        * LOWER(players.display_name) = LOWER(raw_name_from_question)
          OR LOWER(player_aliases.alias) = LOWER(raw_name_from_question)
    - If there is at least one exact match:
        * Use that player id as the resolved player.
        * In your final answer, you may refer to that player normally.
    - If there is NO exact match but there ARE fuzzy matches (similarity):
        * You MAY choose the best candidate, but you must treat this as an
          assumption.
        * In your FINAL answer you MUST explicitly say something like:
              "I could not find an exact match for 'Tim Brady'.
               I am assuming you meant 'Tom Brady' based on fuzzy name
               matching in the database."
        * You must also include that assumption in the JSON under "assumptions".
    - If there are zero rows for the name-resolution query:
        * In your FINAL answer, clearly state that no player matching the
          given name was found in the database.
        * You may suggest likely candidates only if they came from previous
          steps; do NOT invent names.`
6. Stopping condition:
    - When you have enough information to answer the question, FINISH with a
      natural-language answer. Do NOT request more SQL after that.
7. Output format (CRITICAL):
    - You MUST respond with STRICT JSON and nothing else, in one of two forms.
    - Do NOT include any explanation outside the JSON.
    - Do NOT wrap the JSON in Markdown code fences.
    - Your entire response MUST be exactly one JSON object.

    a) To request a SQL query:
    {
      "action": "CALL_SQL",
      "thought": "short description of why you need this query",
      "sql": "SELECT ..."
    }

    b) To finish and answer the user:
    {
      "action": "FINISH",
      "final_answer": "short natural-language answer for the user"
    }

8. You will receive the full interaction context as JSON from the caller:
    {
      "question": "...",
      "schema": { ... reduced schema JSON ... },
      "history": [
        {
          "step": 1,
          "action": "CALL_SQL",
          "sql": "...",
          "observation": {
            "row_count": 3,
            "columns": ["col1", "col2"],
            "rows": [
              ["val11", "val12"],
              ["val21", "val22"],
              ...
            ]
          }
        },
        ...
      ]
    }

9. Use the history to avoid repeating the same query. If you already know the
   player id and necessary aggregates, go straight to FINISH.

Here is the database schema the SQL must use:
<schema>
{{SCHEMA}}
</schema>
"""
