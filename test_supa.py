import sqlalchemy
print("SQLAlchemy version:", sqlalchemy.__version__)
from sqlalchemy import create_engine
url = "postgresql://postgres.udyztmgkhrnsaksqyglq:Ale175715%40%23@aws-1-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
engine = create_engine(url)
try:
    with engine.connect() as conn:
        print("Connected!")
except Exception as e:
    print(f"Error: {type(e).__name__} - {e}")
