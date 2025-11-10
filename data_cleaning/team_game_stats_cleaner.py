import pandas as pd

# --- Load flattened CSV ---
df = pd.read_csv("texas_game_stats.csv")

all_rows = []

# --- Efficiency Conversion Function ---
def convert_efficiency(eff_str):
    """
    Convert 'made-attempted' string (e.g., '7-15') to decimal (e.g., 0.4667).
    Returns None if invalid or missing.
    """
    try:
        eff_str = str(eff_str).strip()
        if '-' not in eff_str or eff_str in ['', 'nan', 'None']:
            return None
        made, attempts = map(int, eff_str.split('-'))
        if attempts == 0:
            return 0.0
        return round(made / attempts, 4)
    except Exception:
        return None

# --- Normalize each row ---
for _, row in df.iterrows():
    game_id = row['id']
    year = row['year']

    # Process both home and away teams
    for team_idx in [0, 1]:
        team_data = {
            'game_id': game_id,
            'year': year,
            'team': row.get(f'teams_{team_idx}_team'),
            'home_away': row.get(f'teams_{team_idx}_home_away'),
            'points': row.get(f'teams_{team_idx}_points')
        }

        stat_num = 0
        while f'teams_{team_idx}_stats_{stat_num}_category' in row:
            cat_col = f'teams_{team_idx}_stats_{stat_num}_category'
            val_col = f'teams_{team_idx}_stats_{stat_num}_stat'
            category = row.get(cat_col)
            value = row.get(val_col)
            
            if pd.isna(category) or pd.isna(value):
                break
            
            # --- Convert efficiency stats to decimals ---
            if category in ['thirdDownEff', 'fourthDownEff', 'completionAttempts']:
                value = convert_efficiency(value)
            
            # Add stat to team dictionary
            team_data[category] = value
            stat_num += 1

        all_rows.append(team_data)

# --- Convert to DataFrame ---
normalized_df = pd.DataFrame(all_rows)

# --- Save to CSV ---
normalized_df.to_csv("game_stats_wide.csv", index=False)
print("✅ Saved wide-format CSV with efficiency stats converted to decimals.")
