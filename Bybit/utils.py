import json
import pandas as pd

def load_data(file):
    with open(file, "r") as f:
        return json.load(f)
    
def save_data(file, data):
    with open(file, "w") as f:
        json.dump(data, f)

def list_to_pd(data):
    return pd.DataFrame(data, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume", "Turnover"])

def pd_to_list(data):
    return data.to_dict(orient="records")