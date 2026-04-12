import os
from sqlalchemy import create_engine, text
from db import Base, SessionLocal, Client, User

# Ensure that DATABASE_URL works (sqlite by default locally)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///leancopilot.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

def add_column(engine, table_name, column_name, data_type):
    with engine.connect() as conn:
        try:
            # We try to add the column
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {data_type}"))
            conn.commit()
            print(f"Added column {column_name} to {table_name}.")
        except Exception as e:
            # If it fails, column likely exists. Just ignore.
            print(f"Column {column_name} might already exist or error: {e}")

# Add columns to users table
add_column(engine, "users", "full_name", "VARCHAR(100)")
add_column(engine, "users", "email", "VARCHAR(100)")
add_column(engine, "users", "client_id", "INTEGER")
add_column(engine, "users", "password_reset_req", "BOOLEAN DEFAULT False")

# This will create any missing tables (like clients and license_keys)
Base.metadata.create_all(bind=engine)

# Create "teste" client and bind the user "paulo"
db = SessionLocal()
try:
    cliente_teste = db.query(Client).filter(Client.name == "teste").first()
    if not cliente_teste:
        cliente_teste = Client(name="teste")
        db.add(cliente_teste)
        db.commit()
        db.refresh(cliente_teste)
        print("Cliente 'teste' criado.")
    
    # Associate user paulo
    paulo = db.query(User).filter(User.username == "paulo").first()
    if paulo:
        if not paulo.client_id:
            paulo.client_id = cliente_teste.id
            paulo.full_name = "Paulo"
            db.commit()
            print("Usuário 'paulo' associado ao cliente 'teste'.")
        else:
            print("Usuário 'paulo' já estava associado a um cliente.")
    else:
        print("Usuário 'paulo' não encontrado.")
finally:
    db.close()
    
print("Migração concluída.")
