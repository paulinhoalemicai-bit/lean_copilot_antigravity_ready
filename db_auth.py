from db import SessionLocal, LicenseKey, User

def create_user_with_license(username, password, full_name, email, code):
    db_session = SessionLocal()
    try:
        if db_session.query(User).filter(User.username == username).first():
            return False, "Usuário já existe."
            
        license = db_session.query(LicenseKey).filter(LicenseKey.code == code).first()
        if not license:
            return False, "Código de licença inválido."
        if license.is_used:
            return False, "Este código já foi utilizado."
            
        from db import hash_password
        new_user = User(
            username=username, 
            password_hash=hash_password(password), 
            role="aluno",
            full_name=full_name,
            email=email,
            client_id=license.client_id
        )
        db_session.add(new_user)
        
        license.is_used = True
        license.used_by = username
        
        db_session.commit()
        return True, "Registrado com sucesso!"
    except Exception as e:
        db_session.rollback()
        return False, str(e)
    finally:
        db_session.close()

def request_password_reset(username):
    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.username == username).first()
        if not user:
            return False, "Usuário não encontrado."
        user.password_reset_req = True
        db_session.commit()
        return True, "Solicitação de redefinição de senha enviada ao administrador. Em caso de urgência, contate-o."
    except Exception as e:
        db_session.rollback()
        return False, str(e)
    finally:
        db_session.close()

def change_password(username, new_password):
    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.username == username).first()
        if not user: return False
        from db import hash_password
        user.password_hash = hash_password(new_password)
        user.password_reset_req = False
        db_session.commit()
        return True
    finally:
        db_session.close()
