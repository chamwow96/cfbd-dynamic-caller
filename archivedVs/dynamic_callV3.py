# dynamic_call_tk_full.py
import os
import cfbd
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox
from cfbd_endpoints import api_methods  # your mapped endpoints
from datetime import datetime

# --- API Setup ---
configuration = cfbd.Configuration(access_token=os.environ["BEARER_TOKEN"])
api_client = cfbd.ApiClient(configuration)

# --- Tkinter window ---
root = tk.Tk()
root.title("CFBD Dynamic API Caller")
root.geometry("600x400")

# --- Variables ---
selected_class = tk.StringVar()
selected_method = tk.StringVar()
year_var = tk.StringVar()
team_var = tk.StringVar()

# --- Load Teams ---
try:
    teams_df = pd.read_csv("teams.csv")  # should have a column 'School'
    all_teams = sorted(teams_df['School'].dropna().unique())
except Exception as e:
    messagebox.showerror("Error", f"Failed to load teams.csv: {e}")
    all_teams = []

# --- Widgets ---
tk.Label(root, text="Select API Class:").pack(pady=5)
class_dropdown = ttk.Combobox(root, textvariable=selected_class, values=list(api_methods.keys()))
class_dropdown.pack(pady=5)

tk.Label(root, text="Select API Method:").pack(pady=5)
method_dropdown = ttk.Combobox(root, textvariable=selected_method)
method_dropdown.pack(pady=5)

tk.Label(root, text="Years (comma-separated, e.g., 2019,2020):").pack(pady=5)
year_entry = tk.Entry(root, textvariable=year_var)
year_entry.pack(pady=5)

tk.Label(root, text="Teams (comma-separated or leave blank for all):").pack(pady=5)
team_entry = tk.Entry(root, textvariable=team_var)
team_entry.pack(pady=5)


# --- Update Methods on Class Change ---
def update_methods(*args):
    cls = selected_class.get()
    if cls in api_methods:
        method_dropdown['values'] = list(api_methods[cls].keys())
        selected_method.set('')


selected_class.trace_add('write', update_methods)


# --- Flatten function for any API response ---
def flatten(obj, parent_key='', sep='_'):
    """Flatten CFBD API response objects into a CSV-safe dict."""
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


# --- Generate a dynamic CSV filename ---
def generate_csv_filename(endpoint, years=None, teams=None):
    if years:
        if isinstance(years, list):
            years_str = f"{min(years)}-{max(years)}"
        else:
            years_str = str(years)
    else:
        years_str = "all_years"

    if teams:
        if isinstance(teams, list):
            teams_str = "-".join([t.replace(" ", "") for t in teams[:5]])
            if len(teams) > 5:
                teams_str += "-etc"
        else:
            teams_str = teams.replace(" ", "")
    else:
        teams_str = "all_teams"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{endpoint}_{years_str}_{teams_str}_{timestamp}.csv"


# --- Save API response to CSV ---
def save_api_response_to_csv(response, endpoint, years=None, teams=None):
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
        print(f"\n✅ Saved CSV: {filename}")
        print(f"Shape: {df.shape}\n")
        return df
    return None


# --- Main API Call ---
def call_api():
    cls_name = selected_class.get()
    method_name = selected_method.get()
    years_input = year_var.get()
    teams_input = team_var.get()

    if not cls_name or not method_name:
        messagebox.showerror("Error", "Please select both class and method.")
        return

    # Parse years
    if years_input:
        try:
            years = [int(y.strip()) for y in years_input.split(",") if y.strip()]
        except:
            messagebox.showerror("Error", "Years must be integers separated by commas.")
            return
    else:
        years = list(range(2001, 2026))

    # Parse teams
    if teams_input:
        teams = [t.strip() for t in teams_input.split(",") if t.strip()]
    else:
        teams = all_teams

    api_cls = getattr(cfbd, cls_name)(api_client)
    method = getattr(api_cls, api_methods[cls_name][method_name])

    all_data = []

    try:
        for year in years:
            for team in teams:
                kwargs = {'year': year, 'team': team}
                response = method(**kwargs)
                if response:
                    if isinstance(response, list):
                        all_data.extend(response)
                    else:
                        all_data.append(response)

        if all_data:
            df = save_api_response_to_csv(all_data, endpoint=method_name, years=years, teams=teams)
            messagebox.showinfo("Success", f"CSV saved!\nShape: {df.shape}")
        else:
            messagebox.showinfo("Info", "API returned no data.")

    except Exception as e:
        messagebox.showerror("API Error", str(e))


# --- Button ---
tk.Button(root, text="Call API & Save CSV", command=call_api).pack(pady=20)

root.mainloop()
