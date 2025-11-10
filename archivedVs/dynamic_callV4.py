# This is a flexible CFBD API caller using Tkinter.
# 
# dynamic_call_tk_flex.py
import os
import cfbd
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox
from cfbd_endpoints import api_methods
from datetime import datetime

# --- API Setup ---
configuration = cfbd.Configuration(access_token=os.environ["BEARER_TOKEN"])
api_client = cfbd.ApiClient(configuration)

# --- Tkinter window ---
root = tk.Tk()
root.title("CFBD Dynamic API Caller")
root.geometry("700x700")

# --- Optional filters ---
optional_filters = {
    "conference": "Conference Abbreviation",
    "position": "Position",
    "game_id": "Game ID",
    "season_type": "Season Type",
    "week": "Week",
    "team": "Team",
    "home": "Home Team",
    "away": "Away Team",
    "provider": "Data Provider",
    "first_name": "First Name",
    "last_name": "Last Name",
    "min_year": "Min Year",
    "max_year": "Max Year",
    "school": "School",
    "offense": "Offense Team",
    "defense": "Defense Team",
    "offense_conference": "Offense Conference",
    "defense_conference": "Defense Conference",
    "classification": "Division Classification",
    "id": "Game ID (Required for some endpoints)",
    "category": "Player Stat Category",
    "media_type": "Media Type",
    "down": "Down (1-4)",
    "distance": "Distance (yards)",
    "exclude_garbage_time": "Exclude Garbage Time (True/False)",
    "player_id": "Player ID",
    "threshold": "Threshold (float)",
    "search_term": "Player Search Term",
    "play_type": "Play Type",
    "recruit_type": "Recruit Type (e.g. HighSchool)",
    "state": "State/Province",
    "athlete_id": "Athlete ID",
    "stat_type_id": "Stat Type ID",
    "start_week": "Start Week",
    "end_week": "End Week",
    "team1": "Team 1 (Comparison)",
    "team2": "Team 2 (Comparison)",
}

# --- Load Teams ---
try:
    teams_df = pd.read_csv("teams.csv")
    all_teams = sorted(teams_df["School"].dropna().unique())
except Exception as e:
    messagebox.showwarning("Warning", f"Could not load teams.csv: {e}")
    all_teams = []

# --- UI Variables ---
selected_class = tk.StringVar()
selected_method = tk.StringVar()
filter_vars = {k: tk.StringVar() for k in optional_filters.keys()}

# --- Dropdowns ---
tk.Label(root, text="Select API Class:").pack(pady=5)
class_dropdown = ttk.Combobox(root, textvariable=selected_class, values=list(api_methods.keys()))
class_dropdown.pack(pady=5)

tk.Label(root, text="Select API Method:").pack(pady=5)
method_dropdown = ttk.Combobox(root, textvariable=selected_method)
method_dropdown.pack(pady=5)

def update_methods(*args):
    cls = selected_class.get()
    if cls in api_methods:
        method_dropdown["values"] = list(api_methods[cls].keys())
        selected_method.set("")

selected_class.trace_add("write", update_methods)

# --- Scrollable Filter Frame ---
canvas = tk.Canvas(root)
scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
scrollable_frame = ttk.Frame(canvas)

scrollable_frame.bind(
    "<Configure>",
    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)
canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

tk.Label(root, text="Optional Filters:").pack(pady=5)
canvas.pack(side="left", fill="both", expand=True, pady=5)
scrollbar.pack(side="right", fill="y")

for key, label in optional_filters.items():
    frame = ttk.Frame(scrollable_frame)
    frame.pack(fill="x", pady=2)
    ttk.Label(frame, text=label, width=28, anchor="w").pack(side="left")
    ttk.Entry(frame, textvariable=filter_vars[key]).pack(side="left", fill="x", expand=True)

# --- Helper Functions ---
def flatten(obj, parent_key='', sep='_'):
    items = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            items.update(flatten(v, f"{parent_key}{sep}{k}" if parent_key else k))
    elif isinstance(obj, list):
        for idx, v in enumerate(obj):
            items.update(flatten(v, f"{parent_key}{sep}{idx}" if parent_key else str(idx)))
    elif hasattr(obj, '__dict__'):
        for k, v in obj.__dict__.items():
            if not k.startswith("_"):
                items.update(flatten(v, f"{parent_key}{sep}{k}" if parent_key else k))
    else:
        items[parent_key] = obj
    return items


def generate_csv_filename(endpoint, kwargs):
    parts = [endpoint]
    if "year" in kwargs:
        parts.append(str(kwargs["year"]))
    if "team" in kwargs:
        parts.append(kwargs["team"].replace(" ", ""))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return "_".join(parts) + f"_{timestamp}.csv"


def save_to_csv(response, endpoint, kwargs):
    rows = [flatten(item) for item in response] if isinstance(response, list) else [flatten(response)]
    if not rows:
        return None
    df = pd.DataFrame(rows)
    filename = generate_csv_filename(endpoint, kwargs)
    df.to_csv(filename, index=False)
    print(f"✅ Saved: {filename}")
    return df


# --- API Caller ---
def call_api():
    cls_name = selected_class.get()
    method_name = selected_method.get()

    if not cls_name or not method_name:
        messagebox.showerror("Error", "Select both an API class and method.")
        return

    kwargs = {}
    for key, var in filter_vars.items():
        val = var.get().strip()
        if val:
            if val.isdigit():
                val = int(val)
            elif val.lower() in ["true", "false"]:
                val = val.lower() == "true"
            kwargs[key] = val

    try:
        api_cls = getattr(cfbd, cls_name)(api_client)
        method = getattr(api_cls, api_methods[cls_name][method_name])
        response = method(**kwargs)
        if response:
            df = save_to_csv(response, method_name, kwargs)
            messagebox.showinfo("Success", f"Data saved to CSV.\nShape: {df.shape}")
        else:
            messagebox.showinfo("No Data", "API returned no results.")
    except Exception as e:
        messagebox.showerror("Error", str(e))


# --- Button ---
tk.Button(root, text="Call API & Save CSV", command=call_api).pack(pady=10)

root.mainloop()
