import os
import urllib.parse
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

url = "postgresql://postgres.udyztmgkhrnsaksqyglq:Ale175715%40%23@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

print("Testando conexão...")
try:
    engine = create_engine(url)
    connection = engine.connect()
    print("Sucesso!")
    connection.close()
except Exception as e:
    print("Falha:", str(e))
