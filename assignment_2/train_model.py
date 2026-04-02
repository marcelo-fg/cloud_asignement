import os
import sys
from dotenv import load_dotenv

# Add backend to path to import db
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from db import run_query

def main():
    load_dotenv()
    
    print("Starting BigQuery ML model training...")
    with open(os.path.join(os.path.dirname(__file__), "backend", "train_model.sql"), "r") as f:
        sql = f.read()
    
    try:
        run_query(sql)
        print("Model training initiated successfully (it may take a few minutes to complete in BQ).")
    except Exception as e:
        print(f"Error training model: {e}")

if __name__ == "__main__":
    main()
