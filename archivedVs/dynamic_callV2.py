# dynamic_call_tk.py
import os
import cfbd
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox
from cfbd_endpoints import api_methods  # your mapped endpoints
import csv

# --- API Setup ---
configuration = cfbd.Configuration(
    access_token=os.environ["BEARER_TOKEN"]
)
api_client = cfbd.ApiClient(configuration)

# --- Tkinter window ---
root = tk.Tk()
root.title("CFBD Dynamic API Caller")
root.geometry("500x350")

# --- Variables ---
selected_class = tk.StringVar()
selected_method = tk.StringVar()
year_var = tk.StringVar()
team_var = tk.StringVar()

# --- Widgets ---
tk.Label(root, text="Select API Class:").pack(pady=5)
class_dropdown = ttk.Combobox(root, textvariable=selected_class, values=list(api_methods.keys()))
class_dropdown.pack(pady=5)

tk.Label(root, text="Select API Method:").pack(pady=5)
method_dropdown = ttk.Combobox(root, textvariable=selected_method)
method_dropdown.pack(pady=5)

tk.Label(root, text="Year (optional):").pack(pady=5)
year_entry = tk.Entry(root, textvariable=year_var)
year_entry.pack(pady=5)

tk.Label(root, text="Team (optional):").pack(pady=5)
team_entry = tk.Entry(root, textvariable=team_var)
team_entry.pack(pady=5)

def update_methods(*args):
    cls = selected_class.get()
    if cls in api_methods:
        method_dropdown['values'] = list(api_methods[cls].keys())
        selected_method.set('')

selected_class.trace_add('write', update_methods)

# --- Generic object flattener ---
def flatten_obj(obj, parent_key='', sep='_'):
    """
    Recursively flattens an object or dict into a flat dictionary.
    Handles nested objects, lists, and attributes.
    """
    items = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            items.update(flatten_obj(v, new_key, sep=sep))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            new_key = f"{parent_key}{sep}{i}" if parent_key else str(i)
            items.update(flatten_obj(v, new_key, sep=sep))
    elif hasattr(obj, '__dict__'):
        items.update(flatten_obj(obj.__dict__, parent_key, sep=sep))
    else:
        items[parent_key] = obj
    return items

# --- Generic CSV saver ---
def save_to_csv(data, filename="cfbd_api_output.csv"):
    """
    Generic CSV saver for any CFBD API response.
    Works with single object, list of objects, or nested objects.
    """
    if not data:
        print("No data to save.")
        return

    # Ensure it's a list
    if not isinstance(data, list):
        data = [data]

    flat_rows = [flatten_obj(item) for item in data]

    # Get all possible columns
    fieldnames = set()
    for row in flat_rows:
        fieldnames.update(row.keys())
    fieldnames = list(fieldnames)

    # Write CSV
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat_rows)

    print(f"Saved {len(flat_rows)} rows to {filename}")
    return filename

# --- API Call Handler ---
def call_api():
    cls_name = selected_class.get()
    method_name = selected_method.get()
    year = year_var.get()
    team = team_var.get()

    if not cls_name or not method_name:
        messagebox.showerror("Error", "Please select both class and method.")
        return

    try:
        # Get the API class object
        api_cls = getattr(cfbd, cls_name)(api_client)
        method = getattr(api_cls, api_methods[cls_name][method_name])

        # Build kwargs dynamically
        kwargs = {}
        if year: kwargs['year'] = int(year)
        if team: kwargs['team'] = team

        # Call API
        response = method(**kwargs)

        if response:
            csv_file = save_to_csv(response)
            messagebox.showinfo("Success", f"CSV saved: {csv_file}")
        else:
            messagebox.showinfo("Info", "API returned no data.")

    except Exception as e:
        messagebox.showerror("API Error", str(e))

tk.Button(root, text="Call API & Save CSV", command=call_api).pack(pady=20)

root.mainloop()
