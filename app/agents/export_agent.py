#export_agent
import pandas as pd
import os

def export_agent(state):
    os.makedirs("exports", exist_ok=True)

    df = pd.DataFrame(state["ranking"])
    path = "exports/candidate_ranking.xlsx"
    df.to_excel(path, index=False)

    return {"excel_path": path}
