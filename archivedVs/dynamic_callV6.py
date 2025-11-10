# dynamic_call_streamlit_v6.py
import os
import cfbd
import pandas as pd
import streamlit as st
from datetime import datetime
import inspect

# --- CFBD API setup ---
configuration = cfbd.Configuration(access_token=os.environ["BEARER_TOKEN"])
api_client = cfbd.ApiClient(configuration)

# --- Reference endpoints mapping ---
# Replace with your cfbd_endpoints.py contents
from cfbd_endpoints import api_methods  

# --- Load Teams ---
try:
    teams_df = pd.read_csv("teams.csv")  # must have 'School' column
    all_teams = sorted(teams_df['School'].dropna().unique())
except Exception as e:
    st.error(f"Failed to load teams.csv: {e}")
    all_teams = []

# --- Helper: Flatten API objects for CSV ---
def flatten(obj, parent_key='', sep='_'):
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
            if hasattr(v, 'value'):  # enum
                v = v.value
            items.update(flatten(v, f"{parent_key}{sep}{k}" if parent_key else k, sep=sep))
    else:
        items[parent_key] = obj
    return items

# --- Helper: Generate CSV filename ---
def generate_csv_filename(endpoint, years=None, teams=None):
    years_str = f"{min(years)}-{max(years)}" if years else "all_years"
    if teams:
        teams_str = "-".join([t.replace(" ", "") for t in teams[:5]])
        if len(teams) > 5: teams_str += "-etc"
    else:
        teams_str = "all_teams"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{endpoint}_{years_str}_{teams_str}_{timestamp}.csv"

# --- Helper: Save API response ---
def save_api_response(response, endpoint, years=None, teams=None):
    rows = []
    if isinstance(response, list):
        for item in response:
            rows.append(flatten(item))
    else:
        rows.append(flatten(response))
    if rows:
        df = pd.DataFrame(rows)
        filename = generate_csv_filename(endpoint, years, teams)
        df.to_csv(filename, index=False)
        st.success(f"CSV saved: {filename}")
        return df
    st.info("API returned no data.")
    return None

# --- Streamlit UI ---
st.title("CFBD Dynamic API Caller V6")

# 1. Select API class
selected_class = st.selectbox("API Class", list(api_methods.keys()))

# 2. Select endpoint/method
methods = list(api_methods[selected_class].keys())
selected_method = st.selectbox("API Endpoint", methods)

# --- Dynamically detect API method parameters ---
api_cls = getattr(cfbd, selected_class)(api_client)
method = getattr(api_cls, api_methods[selected_class][selected_method])
sig = inspect.signature(method)

# Optional dictionary for user inputs
user_inputs = {}

st.subheader("Optional Parameters")

for param_name, param in sig.parameters.items():
    if param_name == "self":
        continue

    annotation = param.annotation
    default = param.default if param.default != inspect.Parameter.empty else None

    # Show proper widget based on type
    if annotation == int:
        user_inputs[param_name] = st.text_input(param_name, value=str(default) if default else "")
    elif annotation == float:
        user_inputs[param_name] = st.text_input(param_name, value=str(default) if default else "")
    elif annotation == bool:
        user_inputs[param_name] = st.checkbox(param_name, value=default if default else False)
    elif hasattr(annotation, "__members__"):  # enum
        options = [m for m in annotation.__members__]
        user_inputs[param_name] = st.selectbox(param_name, options, index=0 if default is None else options.index(default.value))
    else:
        user_inputs[param_name] = st.text_input(param_name, value=default if default else "")

# --- Call API Button ---
if st.button("Call API & Save CSV"):

    call_args = {}

    for k, v in user_inputs.items():
        if v in [None, ""]:
            continue  # skip empty optional params
        ann = sig.parameters[k].annotation

        # Convert types properly
        try:
            if ann == int:
                v = int(v)
            elif ann == float:
                v = float(v)
            elif ann == bool:
                v = bool(v)
            elif hasattr(ann, "__members__"):  # Enum
                v = ann(v)
            # else string
        except Exception as e:
            st.error(f"Failed to convert parameter {k}: {e}")
            continue

        call_args[k] = v

    try:
        response = method(**call_args)
        save_api_response(response, selected_method, years=call_args.get("year"), teams=[call_args.get("team")] if call_args.get("team") else None)
    except Exception as e:
        st.error(f"API Error: {e}")
