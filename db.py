import json
import os
import bcrypt
from datetime import datetime
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

from sqlalchemy import create_engine, Column, String, Integer, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

load_dotenv()

# Tenta usar o banco da nuvem (Postgres) se a variável DATABASE_URL existir.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///leancopilot.db")

# Render/Heroku as vezes passam "postgres://" mas o sqlalchemy exige "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# A mágica do Supabase Transaction Pooler: Evitar o erro OperationalError de Sessão!
engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True, 
    execution_options={"isolation_level": "AUTOCOMMIT"}
)
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

Base = declarative_base()


class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class LicenseKey(Base):
    __tablename__ = "license_keys"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False, unique=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    is_used = Column(Boolean, default=False)
    used_by = Column(String(50), ForeignKey("users.username"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    username = Column(String(50), primary_key=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="aluno") # "aluno" ou "professor"
    full_name = Column(String(100), nullable=True) # made optional theoretically for legacy compatibility initially
    email = Column(String(100), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    password_reset_req = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Project(Base):
    __tablename__ = "projects"
    project_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    state_json = Column(Text, nullable=False)
    user_id = Column(String(50), ForeignKey("users.username"), nullable=False)
    allow_teacher_edit = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Draft(Base):
    __tablename__ = "drafts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), ForeignKey("projects.project_id"), nullable=False)
    tool = Column(String(50), nullable=False)
    draft_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint('project_id', 'tool', name='_project_tool_uc'),)


class SessionLog(Base):
    __tablename__ = "session_logs"
    session_id = Column(String(50), primary_key=True)
    project_id = Column(String(50), nullable=False)
    tool = Column(String(50), nullable=False)
    event_type = Column(String(50), nullable=False)
    user_delta = Column(Text, nullable=True)
    coach_payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    
    # Auto-migração raw para SQLite/Postgres (Nuvem usa banco pré-existente e Base.metadata não cria colunas novas em tabelas existentes)
    from sqlalchemy import text
    with engine.connect() as conn:
        try: conn.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR(100)"))
        except Exception: pass
        try: conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(100)"))
        except Exception: pass
        try: conn.execute(text("ALTER TABLE users ADD COLUMN client_id INTEGER"))
        except Exception: pass
        try: conn.execute(text("ALTER TABLE users ADD COLUMN password_reset_req BOOLEAN DEFAULT False"))
        except Exception: pass
        try: conn.commit()
        except: pass
        
    # Criar um professor padrão se não existir na inicialização (somente para testes/MVP rápido)
    create_user("prof", "prof123", role="professor")


# --- User Methods ---
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

def create_user(username: str, password: str, role: str = "aluno") -> bool:
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            return False # Usuário já existe
        new_user = User(username=username, password_hash=hash_password(password), role=role)
        db.add(new_user)
        db.commit()
        return True
    finally:
        db.close()

def authenticate_user(username: str, password: str) -> Optional[Dict[str, str]]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user and verify_password(password, user.password_hash):
            return {"username": user.username, "role": user.role}
        return None
    finally:
        db.close()

# --- Project Methods ---
def list_projects(user_role: str, username: str) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        if user_role == "professor":
            # Professor vê todos (exceto a gaveta de configs)
            projects = db.query(Project).filter(Project.project_id != "SYSTEM_CONFIG").order_by(Project.updated_at.desc()).all()
        else:
            projects = db.query(Project).filter(Project.user_id == username, Project.project_id != "SYSTEM_CONFIG").order_by(Project.updated_at.desc()).all()
        
        return [
            {
                "project_id": p.project_id,
                "name": p.name,
                "user_id": p.user_id,
                "allow_teacher_edit": p.allow_teacher_edit,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None
            }
            for p in projects
        ]
    finally:
        db.close()


def upsert_project(project_id: str, name: str, state: Dict[str, Any], user_id: str, allow_teacher_edit: bool = False) -> None:
    db = SessionLocal()
    try:
        state_json = json.dumps(state, ensure_ascii=False)
        proj = db.query(Project).filter(Project.project_id == project_id).first()
        if proj:
            proj.name = name
            proj.state_json = state_json
            # Não atualiza o dono (user_id) de quem criou primeiro.
            proj.allow_teacher_edit = allow_teacher_edit
            proj.updated_at = datetime.utcnow()
        else:
            new_proj = Project(
                project_id=project_id,
                name=name,
                state_json=state_json,
                user_id=user_id,
                allow_teacher_edit=allow_teacher_edit,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(new_proj)
        db.commit()
    finally:
        db.close()


def get_project_state(project_id: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        proj = db.query(Project).filter(Project.project_id == project_id).first()
        if not proj:
            return None
        state = json.loads(proj.state_json)
        # Injeta as pemissões e autoria no state para a interface saber
        state["user_id"] = proj.user_id
        state["allow_teacher_edit"] = proj.allow_teacher_edit
        return state
    finally:
        db.close()


# --- Draft and Session Methods ---
def save_draft(project_id: str, tool: str, payload: Dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        draft_json = json.dumps(payload, ensure_ascii=False)
        draft = db.query(Draft).filter(Draft.project_id == project_id, Draft.tool == tool).first()
        if draft:
            draft.draft_json = draft_json
            draft.updated_at = datetime.utcnow()
        else:
            new_draft = Draft(project_id=project_id, tool=tool, draft_json=draft_json)
            db.add(new_draft)
        db.commit()
    finally:
        db.close()


def load_draft(project_id: str, tool: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        draft = db.query(Draft).filter(Draft.project_id == project_id, Draft.tool == tool).first()
        if not draft:
            return None
        return json.loads(draft.draft_json)
    finally:
        db.close()


def add_session_log(
    session_id: str,
    project_id: str,
    tool: str,
    event_type: str,
    user_delta: str,
    coach_payload: Dict[str, Any],
) -> None:
    db = SessionLocal()
    try:
        log = SessionLog(
            session_id=session_id,
            project_id=project_id,
            tool=tool,
            event_type=event_type,
            user_delta=user_delta,
            coach_payload=json.dumps(coach_payload, ensure_ascii=False)
        )
        db.add(log)
        db.commit()
    finally:
        db.close()


def list_recent_sessions(project_id: str, limit: int = 6) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        logs = db.query(SessionLog).filter(SessionLog.project_id == project_id).order_by(SessionLog.created_at.desc()).limit(limit).all()
        out = []
        for l in logs:
            d = {
                "session_id": l.session_id,
                "project_id": l.project_id,
                "tool": l.tool,
                "event_type": l.event_type,
                "user_delta": l.user_delta,
                "created_at": l.created_at
            }
            d["coach"] = json.loads(l.coach_payload or "{}")
            out.append(d)
        return out
    finally:
        db.close()

# --- Configurações Globais (Professor Admin) ---
def get_global_model() -> str:
    db = SessionLocal()
    try:
        cfg = db.query(Project).filter(Project.project_id == "SYSTEM_CONFIG").first()
        if cfg and cfg.state_json:
            import json
            state = json.loads(cfg.state_json)
            return state.get("openai_model", "gpt-4o-mini")
        return "gpt-4o-mini"
    except Exception:
        return "gpt-4o-mini"
    finally:
        db.close()

def set_global_model(model_name: str) -> None:
    db = SessionLocal()
    try:
        import json
        cfg = db.query(Project).filter(Project.project_id == "SYSTEM_CONFIG").first()
        if not cfg:
            cfg = Project(
                project_id="SYSTEM_CONFIG",
                name="[ADMIN] System Configuration",
                state_json=json.dumps({"openai_model": model_name}),
                user_id="prof"
            )
            db.add(cfg)
        else:
            state = json.loads(cfg.state_json) if cfg.state_json else {}
            state["openai_model"] = model_name
            cfg.state_json = json.dumps(state)
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
