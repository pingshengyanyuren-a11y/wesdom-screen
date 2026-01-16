import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# 加载环境变量
load_dotenv('.env')

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Error: Missing Supabase credentials")
    sys.exit(1)

supabase = create_client(url, key)

try:
    print("Checking 'predictions' table...")
    res = supabase.table('predictions').select('*').limit(5).execute()
    
    if not res.data:
        print("No data found in 'predictions' table.")
    else:
        print(f"Found {len(res.data)} records.")
        print(f"Columns: {res.data[0].keys()}")
        for row in res.data:
            p_json = row.get('prediction_json') or {}
            preds = p_json.get('predictions') or []
            p_len = len(preds)
            print(f"Point: {row['point_name']}, Predictions Length: {p_len}")

except Exception as e:
    print(f"Error: {e}")
