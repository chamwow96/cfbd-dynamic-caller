# dynamic_call_streamlit.py
import os
import cfbd
import pandas as pd
import streamlit as st
from datetime import datetime
from cfbd_endpoints import api_methods  # your reference module
from pydantic import BaseModel
from typing import Any

# --- API Setup ---
configuration = cfbd.Configuration(access_token=os.environ.get("BEARER_TOKEN"))
api_client = cfbd.ApiClient(configuration)

# --- Helper functions ---
def flatten(obj, parent_key='', sep='_'):
    """Recursively flatten CFBD API response objects."""
    items = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            items.update(flatten(v, f"{parent_key}{sep}{k}" if parent_key else k, sep=sep))
    elif isinstance(obj, list):
        for idx, v in enumerate(obj):
            items.update(flatten(v, f"{parent_key}{sep}{idx}" if parent_key else str(idx), sep=sep))
    elif hasattr(obj, '__dict__'):
        for k, v in obj.__dict__.items():
            if k.startswith('_'):
                continue
            if hasattr(v, 'value'):
                v = v.value
            items.update(flatten(v, f"{parent_key}{sep}{k}" if parent_key else k, sep=sep))
    else:
        items[parent_key] = obj
    return items

def generate_csv_filename(endpoint, years=None, teams=None):
    years_str = f"{min(years)}-{max(years)}" if years else "all_years"
    if teams:
        teams_str = "-".join([t.replace(" ", "") for t in teams[:5]])
        if len(teams) > 5:
            teams_str += "-etc"
    else:
        teams_str = "all_teams"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{endpoint}_{years_str}_{teams_str}_{timestamp}.csv"

def save_api_response_to_csv(response, endpoint, years=None, teams=None):
    rows = [flatten(r) for r in (response if isinstance(response, list) else [response])]
    if rows:
        df = pd.DataFrame(rows)
        filename = generate_csv_filename(endpoint, years, teams)
        df.to_csv(filename, index=False)
        return df, filename
    return None, None

# --- Streamlit UI ---
st.title("CFBD Dynamic API Caller")

# API Class selection
api_class_name = st.selectbox("Select API Class", list(api_methods.keys()))
endpoint_name = st.selectbox("Select Endpoint", list(api_methods[api_class_name].keys()))
method_name = api_methods[api_class_name][endpoint_name]

# Dynamically show optional filters
st.subheader("Optional Filters")
filters = {}
# Here you can define your reference of types for each filter
filter_types = {
    "conference": str,
    "position": str,
    "game_id": int,
    "season_type": str,  # could map to Enum
    "week": int,
    "team": str,
    "home": str,
    "away": str,
    "provider": str,
    "first_name": str,
    "last_name": str,
    "year": int,
    "min_year": int,
    "max_year": int,
    "offense": str,
    "defense": str,
    "offense_conference": str,
    "defense_conference": str,
    "classification": str,  # Enum
    "id": int,
    "category": str,
    "media_type": str,
    "down": int,
    "distance": int,
    "exclude_garbage_time": bool,
    "player_id": str,
    "threshold": float,
    "search_term": str,
    "play_type": str,
    "recruit_type": str,
    "state": str,
    "athlete_id": int,
    "stat_type_id": int,
    "start_week": int,
    "end_week": int,
    "team1": str,
    "team2": str,
}

for f, f_type in filter_types.items():
    if f_type == int:
        filters[f] = st.number_input(f"{f} (int)", value=0, step=1)
    elif f_type == float:
        filters[f] = st.number_input(f"{f} (float)", value=0.0, step=0.1)
    elif f_type == bool:
        filters[f] = st.checkbox(f"{f} (bool)")
    else:
        filters[f] = st.text_input(f"{f} (str)")

# Multiple years selection
years_input = st.text_input("Years (comma-separated, e.g., 2019,2020)")
if years_input:
    years = [int(y.strip()) for y in years_input.split(",") if y.strip()]
else:
    years = list(range(2001, 2026))  # default

# Teams CSV
try:
    teams_df = pd.read_csv("teams.csv")
    all_teams = sorted(teams_df['School'].dropna().unique())
except:
    all_teams = []
teams_input = st.text_input("Teams (comma-separated or leave blank for all)")
teams = [t.strip() for t in teams_input.split(",") if t.strip()] if teams_input else all_teams

# Call API button
if st.button("Call API & Save CSV"):
    api_cls = getattr(cfbd, api_class_name)(api_client)
    method = getattr(api_cls, method_name)
    kwargs = {k: v for k, v in filters.items() if v not in [None, "", 0, 0.0, False]}  # remove empty values
    try:
        all_data = []
        for year in years:
            for team in teams:
                call_kwargs = kwargs.copy()
                call_kwargs.update({"year": year, "team": team})
                response = method(**call_kwargs)
                if response:
                    all_data.extend(response if isinstance(response, list) else [response])
        if all_data:
            df, filename = save_api_response_to_csv(all_data, endpoint_name, years, teams)
            st.success(f"CSV saved: {filename} (rows: {df.shape[0]})")
            st.dataframe(df)
        else:
            st.info("API returned no data.")
    except Exception as e:
        st.error(f"API Error: {e}")
