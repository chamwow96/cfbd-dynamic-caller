# dynamic_call_tk.py
import os
import cfbd
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox
from cfbd_endpoints import api_methods  # your mapped endpoints
import csv
from ast import literal_eval


# --- API Setup ---
configuration = cfbd.Configuration(
    access_token=os.environ["BEARER_TOKEN"]
)
api_client = cfbd.ApiClient(configuration)

# --- Tkinter window ---
root = tk.Tk()
root.title("CFBD Dynamic API Caller")
root.geometry("500x300")

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

        # Convert response to DataFrame if possible
        if response:
            if isinstance(response, list) and hasattr(response[0], '__dict__'):
                df = pd.DataFrame([r.__dict__ for r in response])
            elif hasattr(response, '__dict__'):
                df = pd.DataFrame([response.__dict__])
            else:
                df = pd.DataFrame(response)
            df.to_csv('cfbd_api_output.csv', index=False)
            messagebox.showinfo("Success", f"CSV saved! Shape: {df.shape}")
        else:
            messagebox.showinfo("Info", "API returned no data.")

    except Exception as e:
        messagebox.showerror("API Error", str(e))

tk.Button(root, text="Call API & Save CSV", command=call_api).pack(pady=20)

root.mainloop()

