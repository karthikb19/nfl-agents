# Players Table Schema

## Table Name: players

### Columns:
player_id: Int32 (Primary Key)

gsis_id: String

display_name: String

common_first_name: String

first_name: String

last_name: String

short_name: String

football_name: String

suffix: String

nfl_id: String

pfr_id: String

espn_id: String

birth_date: Date

position_group: String

position: String

height: Int16 // store in inches

weight: Int16 // store in pounds

headshot: String // URL

college_name: String

college_conference: String

jersey_number: Int16

rookie_season: Int16

last_season: Int16

latest_team_id: Int32 // FK → teams.team_id

status: String

years_of_experience: Int16

draft_year: Int16

draft_round: Int16

draft_pick: Int16

draft_team_id: Int32 // FK → teams.team_id