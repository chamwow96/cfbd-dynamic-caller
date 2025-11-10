import os
import pandas as pd
import cfbd
from cfbd.rest import ApiException

# ---------- USER INPUT ----------
years_input = input("Enter season years (comma-separated, e.g., 2024,2025): ")
teams_input = input("Enter teams (comma-separated, e.g., indiana,purdue): ")

# Optional filters
week_input = input("Enter week (leave blank if not filtering): ")
conference_input = input("Enter conference (leave blank if not filtering): ")

# Process input into lists
years = [int(y.strip()) for y in years_input.split(',')]
teams = [t.strip() for t in teams_input.split(',')]
week = int(week_input) if week_input else None
conference = conference_input if conference_input else None

# ---------- API CONFIG ----------
configuration = cfbd.Configuration(
    access_token=os.environ["BEARER_TOKEN"]
)

all_rows = []

with cfbd.ApiClient(configuration) as api_client:
    api_instance = cfbd.GamesApi(api_client)

    for year in years:
        for team in teams:
            try:
                api_response = api_instance.get_game_team_stats(
                    year=year,
                    team=team,
                    week=week,
                    conference=conference
                )
                print(f"Fetched {len(api_response)} games for {team} in {year}")
            except ApiException as e:
                print(f"Error fetching data for {team} {year}: {e}")
                api_response = []

            # Process API response
            for game in api_response:
                game_id = game.id
                for team_obj in game.teams:
                    row = {
                        'year': year,
                        'team': team_obj.team,
                        'game_id': game_id,
                        'team_id': team_obj.team_id,
                        'conference': team_obj.conference,
                        'home_away': team_obj.home_away,
                        'points': team_obj.points
                    }
                    for stat in team_obj.stats:
                        row[stat.category] = stat.stat
                    all_rows.append(row)

# ---------- CREATE DATAFRAME ----------
df = pd.DataFrame(all_rows)

# Reorder columns
base_cols = ['year', 'team', 'game_id', 'team_id', 'conference', 'home_away', 'points']
df = df[base_cols + [c for c in df.columns if c not in base_cols]]

# ---------- SAVE TO CSV ----------
filename = f"cfb_stats_{'_'.join(map(str, years))}.csv"
df.to_csv(filename, index=False)
print(f"CSV saved as '{filename}' with shape: {df.shape}")
