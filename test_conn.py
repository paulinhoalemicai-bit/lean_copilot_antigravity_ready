import socket

hosts = [
    ("aws-0-sa-east-1.pooler.supabase.com", 6543),
    ("aws-1-sa-east-1.pooler.supabase.com", 6543),
    ("db.udyztmgkhrnsaksqyglq.supabase.co", 5432)
]

for host, port in hosts:
    try:
        s = socket.create_connection((host, port), timeout=5)
        print(f"SUCESSO: {host}:{port}")
        s.close()
    except Exception as e:
        print(f"FALHA: {host}:{port} -> {e}")
