import pandas as pd

def process_data(file_path):
    df = pd.read_csv(file_path)
    # Filter rows
    df_filtered = df[df["age"] > 30]
    # Group by department and aggregate salary
    result = df_filtered.groupby("department").agg({"salary": "mean"}).reset_index()
    return result
