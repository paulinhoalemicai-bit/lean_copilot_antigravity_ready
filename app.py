from __future__ import annotations

from datetime import datetime
import io
import json
from typing import Any, Dict, List

import streamlit as st
import pandas as pd
import altair as alt

import db
from config import TOOLS, VOCVOB_COLUMNS
from coach import (
    coach_run,
    new_session_id,
    suggest_serpentes_steps,
    suggest_sipoc_by_step,
    suggest_charter_from_vocvob,
)

st.set_page_config(page_title="Lean Copilot MVP", layout="wide", page_icon="🏥")
db.init_db()


def inject_custom_css():
    st.markdown("""
        <style>
        /* Cor de fundo primária do Sidebar: Azul Sírio Libanês */
        [data-testid="stSidebar"] {
            background-color: #001C59 !important;
            border-right: 1px solid #E2E8F0;
        }
        /* Garantir texto branco no sidebar */
        [data-testid="stSidebar"] * {
            color: #FFFFFF !important;
        }
        /* Header principal branco com texto azul escuro */
        header {
            background-color: #F7F7F7 !important;
        }
        /* Botões Primários - Azul Claro */
        div.stButton > button {
            background-color: #00AEEF;
            color: white !important;
            border-radius: 8px;
            font-weight: 600;
            border: none;
            transition: all 0.2s;
        }
        div.stButton > button:hover {
            background-color: #004992;
            color: white !important;
            transform: scale(1.02);
            border: none;
        }
        /* Botões desabilitados do Professor */
        div.stButton > button:disabled {
            background-color: #CCCCCC;
            color: #666666 !important;
            transform: none;
        }
        /* Títulos principais cor Azul Escuro e Títulos secundários Verde */
        h1, h2 {
            color: #001C59 !important;
            font-weight: 700 !important;
        }
        h3, h4, h5 {
            color: #00AEEF !important;
            font-weight: 600 !important;
        }
        /* Dataframes com estilo limpo */
        .stDataFrame {
            border-radius: 10px;
            border: 1px solid #E6E6E6;
        }
        </style>
    """, unsafe_allow_html=True)


inject_custom_css()

# --- Auth Layer ---
if "user" not in st.session_state:
    st.session_state.user = None

def handle_login():
    st.markdown("<h1 style='text-align: center; color: #001C59;'>🏥 Copiloto de Melhoria Contínua</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #00AEEF;'>Acesso ao Sistema</h3>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_reg = st.tabs(["Entrar", "Criar Conta"])
        
        with tab_login:
            u_log = st.text_input("Usuário", key="log_u")
            p_log = st.text_input("Senha", type="password", key="log_p")
            if st.button("Fazer Login", use_container_width=True):
                user = db.authenticate_user(u_log, p_log)
                if user:
                    st.session_state.user = user
                    st.session_state.active_project_id = None
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")
                    
        with tab_reg:
            st.info("Alunos podem criar conta livremente. Contas de professor são configuradas manualmente (usar padrão 'prof').")
            u_reg = st.text_input("Novo Usuário", key="reg_u")
            p_reg = st.text_input("Nova Senha", type="password", key="reg_p")
            if st.button("Registrar Aluno", use_container_width=True):
                if u_reg and p_reg:
                    if db.create_user(u_reg, p_reg, role="aluno"):
                        st.success("Conta criada com sucesso! Faça login ao lado.")
                    else:
                        st.error("Nome de usuário já existe.")


if not st.session_state.user:
    handle_login()
    st.stop()


# --- Main App ---
user = st.session_state.user
ROLE = user["role"]
USERNAME = user["username"]

with st.sidebar:
    st.markdown(f"### Olá, {USERNAME}!")
    st.markdown(f"Perfil: **{ROLE.title()}**")
    if st.button("Sair (Logout)"):
        st.session_state.user = None
        st.session_state.active_project_id = None
        st.rerun()
    st.markdown("---")

def get_project_list():
    return db.list_projects(ROLE, USERNAME)

def normalize_tool_for_coach(tool_label: str) -> str:
    return tool_label

def _filled_or_marker(value: str, marker: str) -> str:
    v = (value or "").strip()
    return v if v else f"<PREENCHER_{marker}>"

def pretty_gap_id(gid: str) -> str:
    if not gid:
        return gid
    if gid.startswith("RUBRIC."):
        parts = gid.split(".")
        last = parts[-1] if parts else gid
        mapping = {
            "PROBLEM": "Gap Problema",
            "GOAL": "Gap Objetivo",
            "OBJECTIVE": "Gap Objetivo",
            "BUSINESS_CASE": "Gap Business Case",
            "SCOPE": "Gap Escopo",
            "CTQ": "Gap CTQ",
            "Y": "Gap Y",
            "STAKE": "Gap Stakeholders",
            "TIME": "Gap Cronograma",
        }
        return mapping.get(last, f"Gap {last}")
    return gid

def default_project_state(name: str, uid: str) -> dict:
    return {
        "project_id": "",
        "name": name,
        "method": "DMAIC",
        "phase": "Define",
        "status": "active",
        "user_id": uid,
        "allow_teacher_edit": False,
        "context": {},
        "voc_vob": {"voc": [], "vob": [], "notes": ""},
        "charter": {
            "problem": "",
            "goal": "",
            "business_case": "",
            "scope_in": "",
            "scope_out": "",
            "stakeholders_struct": {
                "sponsor": "",
                "lider_projeto": "",
                "dono_processo": "",
                "time": "",
                "areas_impactadas": "",
                "outros": "",
            },
            "stakeholders": "",
            "ctq": "",
            "y": "",
            "timeline_weeks": {
                "Define": 0, "Measure": 0, "Analyze": 0, "Improve": 0, "Control": 0,
            },
        },
        "sipoc": {"serpentes": [], "rows": [], "notes": ""},
        "metrics": [],
        "baseline": {"period": "", "values": {}, "notes": ""},
        "hypotheses": [],
        "solutions": [],
        "pilots": [],
        "control_plan": [],
        "open_gaps": [],
        "last_session_summary": "",
    }

# Render Sidebar Projects
st.sidebar.title("Projetos")

if ROLE == "aluno":
    with st.sidebar.expander("➕ Criar novo projeto", expanded=False):
        new_name = st.text_input("Nome do projeto", "")
        if st.button("Criar"):
            pid = f"P{int(datetime.utcnow().timestamp())}"
            state = default_project_state(new_name or pid, USERNAME)
            state["project_id"] = pid
            db.upsert_project(pid, state["name"], state, user_id=USERNAME, allow_teacher_edit=False)
            st.session_state.active_project_id = pid
            st.rerun()

projects = get_project_list()
if projects:
    st.sidebar.caption("Seus Projetos" if ROLE == "aluno" else "Projetos dos Alunos")
    for p in projects:
        owner_str = f" ({p['user_id']})" if ROLE == "professor" else ""
        if st.sidebar.button(f"📁 {p['name']}{owner_str}", key=f"open_{p['project_id']}"):
            st.session_state.active_project_id = p["project_id"]
            st.rerun()
else:
    if ROLE == "aluno":
        st.sidebar.info("Crie um projeto para começar.")
    else:
        st.sidebar.info("Nenhum projeto de aluno encontrado no sistema.")

pid = st.session_state.get("active_project_id")
if not pid:
    st.title("Bem-vindo ao Lean Copilot")
    st.write("Abra um projeto no menu para começar.")
    st.stop()

project_state = db.get_project_state(pid)
if not project_state:
    st.error("Projeto não encontrado.")
    st.stop()

# --- Permissions Logic ---
is_owner = (project_state.get("user_id") == USERNAME)
allow_edit = project_state.get("allow_teacher_edit", False)

# Se é professor e não tem permissão DE EDIÇÃO
read_only = (ROLE == "professor" and not allow_edit)
if read_only:
    st.warning("⚠️ **Modo Leitura:** O aluno não habilitou edição para professores neste projeto.")

colA, colB = st.columns([2, 1])
with colA:
    owner_str = f" [Dono: {project_state.get('user_id')}]" if ROLE == "professor" else ""
    st.title(f"{project_state['name']}{owner_str}")
with colB:
    if ROLE == "aluno":
        # Toggle permission
        new_permit = st.toggle("Permitir edições do Professor", value=allow_edit)
        if new_permit != allow_edit:
            project_state["allow_teacher_edit"] = new_permit
            db.upsert_project(pid, project_state['name'], project_state, USERNAME, new_permit)
            st.success("Permissão atualizada!")
            st.rerun()

tool_col1, tool_col2 = st.columns([1, 1])
with tool_col1:
    default_tool = st.session_state.get("active_tool", TOOLS[0])
    tool = st.selectbox("Ferramenta Analítica", TOOLS, index=TOOLS.index(default_tool) if default_tool in TOOLS else 0)
    st.session_state.active_tool = tool
with tool_col2:
    mode = st.radio("Ação da IA (Coach)", ["review", "generate"], horizontal=True, disabled=read_only)

left, right = st.columns([1.6, 1.0], gap="large")
new_text = ""

with left:
    if tool == "VOC/VOB":
        st.subheader("VOC/VOB (Voz do Cliente e Negócio)")

        draft = db.load_draft(pid, tool) or {}
        stored = draft.get("voc_vob") or project_state.get("voc_vob") or {"voc": [], "vob": [], "notes": ""}

        def build_df(rows: List[Dict[str, Any]], n: int = 6) -> pd.DataFrame:
            if rows:
                df = pd.DataFrame(rows)
            else:
                df = pd.DataFrame([{c: "" for c in VOCVOB_COLUMNS} for _ in range(n)])
            for c in VOCVOB_COLUMNS:
                if c not in df.columns:
                    df[c] = ""
            return df[VOCVOB_COLUMNS]

        tab1, tab2 = st.tabs(["Voz do Cliente (VOC)", "Voz do Negócio (VOB)"])
        with tab1:
            df_voc = build_df(stored.get("voc", []))
            df_voc_edit = st.data_editor(df_voc, num_rows="dynamic", use_container_width=True, key=f"voc_{pid}", disabled=read_only)
        with tab2:
            df_vob = build_df(stored.get("vob", []))
            df_vob_edit = st.data_editor(df_vob, num_rows="dynamic", use_container_width=True, key=f"vob_{pid}", disabled=read_only)

        notes = st.text_area("Anotações Adicionais (opcional)", value=stored.get("notes", ""), height=100, disabled=read_only)

        voc_out = df_voc_edit.fillna("").to_dict(orient="records")
        vob_out = df_vob_edit.fillna("").to_dict(orient="records")
        
        # Gerar o texto a partir do formulário p/ análise da IA
        new_text = f"VOC Rows: {len(voc_out)}\nVOB Rows: {len(vob_out)}\nNotas: {notes}"

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("💾 Salvar Planilha", disabled=read_only):
                payload = {"voc_vob": {"voc": voc_out, "vob": vob_out, "notes": notes}, "text": new_text}
                db.save_draft(pid, tool, payload)
                project_state["voc_vob"] = {"voc": voc_out, "vob": vob_out, "notes": notes}
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.success("Salvo com sucesso!")
        
        key_charter_sug = f"vocvob_to_charter_sug_{pid}"
        if key_charter_sug not in st.session_state:
            st.session_state[key_charter_sug] = None

        with c2:
            if st.button("🧠 IA: Sugerir Problema", disabled=read_only):
                st.session_state[key_charter_sug] = suggest_charter_from_vocvob(project_state, new_text)
                st.success("Analise as opções abaixo.")

        sug = st.session_state.get(key_charter_sug)
        if sug and sug.get("candidates") and not read_only:
            st.markdown("### Sugestões para o Project Charter")
            for idx, c in enumerate(sug["candidates"], start=1):
                with st.expander(f"📌 Opção {idx}: {c.get('title','(sem título)')}"):
                    st.write("**Rascunho:**", c.get("draft", ""))
                    if st.button(f"✅ Aceitar e Aplicar", key=f"apply_{idx}"):
                        ch = project_state.get("charter", {})
                        # Fake apply for MVP
                        ch["problem"] = c.get("draft")
                        project_state["charter"] = ch
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.success("Problema Aplicado no Charter!")
                        st.rerun()

    elif tool == "Project Charter":
        st.subheader("Project Charter (Contrato de Melhoria)")
        storage_tool = tool

        draft = db.load_draft(pid, storage_tool) or {}
        charter = draft.get("charter") or project_state.get("charter") or {}
        timeline = charter.get("timeline_weeks") or {"Define": 0, "Measure": 0, "Analyze": 0, "Improve": 0, "Control": 0}
        st_struct = charter.get("stakeholders_struct") or {}

        # Ajuste de layout de blocos para visual Sírio Premium
        with st.container(border=True):
            problem = st.text_area("O Problema de Negócio (1 frase clara)", value=charter.get("problem", ""), height=80, disabled=read_only)
            goal = st.text_area("O Objetivo Desejado (Critério SMART)", value=charter.get("goal", ""), height=80, disabled=read_only)
        
        with st.container(border=True):
            sA, sB = st.columns(2)
            with sA:
                scope_in = st.text_area("Dentro do Escopo (IN)", value=charter.get("scope_in", ""), height=80, disabled=read_only)
            with sB:
                scope_out = st.text_area("Fora do Escopo (OUT)", value=charter.get("scope_out", ""), height=80, disabled=read_only)

        with st.container(border=True):
            st.markdown("#### Matriz de Envolvidos (Stakeholders)")
            sA, sB = st.columns(2)
            with sA:
                sponsor = st.text_input("Patrocinador (Sponsor)", value=st_struct.get("sponsor", ""), disabled=read_only)
                lider_projeto = st.text_input("Líder da Melhoria", value=st_struct.get("lider_projeto", ""), disabled=read_only)
                dono_processo = st.text_input("Dono do Processo", value=st_struct.get("dono_processo", ""), disabled=read_only)
            with sB:
                time_txt = st.text_area("Equipe Técnica", value=st_struct.get("time", ""), height=65, disabled=read_only)
                areas_txt = st.text_area("Áreas Modificadas", value=st_struct.get("areas_impactadas", ""), height=65, disabled=read_only)

        with st.container(border=True):
            st.markdown("#### Cronograma Previsto DMAIC (em Semanas)")
            cA, cB, cC, cD, cE = st.columns(5)
            with cA:
                d_w = st.number_input("Define", value=int(timeline.get("Define", 0) or 0), step=1, disabled=read_only)
            with cB:
                m_w = st.number_input("Measure", value=int(timeline.get("Measure", 0) or 0), step=1, disabled=read_only)
            with cC:
                a_w = st.number_input("Analyze", value=int(timeline.get("Analyze", 0) or 0), step=1, disabled=read_only)
            with cD:
                i_w = st.number_input("Improve", value=int(timeline.get("Improve", 0) or 0), step=1, disabled=read_only)
            with cE:
                c_w = st.number_input("Control", value=int(timeline.get("Control", 0) or 0), step=1, disabled=read_only)

        charter_obj = {
            "problem": problem, "goal": goal, "scope_in": scope_in, "scope_out": scope_out,
            "stakeholders_struct": {"sponsor": sponsor, "lider_projeto": lider_projeto, "dono_processo": dono_processo, "time": time_txt, "areas_impactadas": areas_txt},
            "timeline_weeks": {"Define": d_w, "Measure": m_w, "Analyze": a_w, "Improve": i_w, "Control": c_w},
        }
        new_text = "Charter Data: " + json.dumps(charter_obj)

        if st.button("💾 Salvar Project Charter", disabled=read_only):
            db.save_draft(pid, storage_tool, {"charter": charter_obj, "text": new_text})
            project_state["charter"] = charter_obj
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.success("Charter salvo no sistema.")

    else:
        st.info("Outras ferramentas (SIPOC, Ishikawa, etc.) estão na fila de atualização para a nuvem.")
        draft = db.load_draft(pid, tool) or {}
        draft_text = draft.get("text", "")
        new_text = st.text_area("Borrão da Ferramenta (Para Análise da IA):", value=draft_text, height=420, disabled=read_only)
        if st.button("💾 Salvar Rascunho", disabled=read_only):
            db.save_draft(pid, tool, {"text": new_text})
            st.success("Salvo!")

with right:
    st.subheader("👨🏻‍⚕️ Coach IA - Doutor Lean")
    if st.button("🔎 Analisar Preenchimento", disabled=read_only):
        with st.spinner("Analisando gargalos usando gpt-4..."):
            coach_json, rubric_scores, _ = coach_run(tool, project_state, new_text, mode=mode)
            sid = new_session_id()
            db.add_session_log(
                session_id=sid, project_id=pid, tool=tool,
                event_type="REQUEST_REVIEW_NOW", user_delta="Análise de Rotina", coach_payload=coach_json,
            )

            st.markdown("### ✅ Acertos (OK)")
            if coach_json.get("ok"):
                for ok in coach_json["ok"]:
                    st.success(f"✔ {ok}")
            else:
                st.write("-")

            st.markdown("### ⚠️ Diagnóstico de Gaps")
            if coach_json.get("gaps"):
                for g in coach_json["gaps"]:
                    st.error(f"**{pretty_gap_id(g.get('id', ''))}**: {g.get('reason', '')}")
            else:
                st.write("- Todos os critérios base parecem atendidos.")

            st.markdown("### 🏹 Plano de Ação (Próximo Passo)")
            st.info(coach_json.get("next_action", ""))

    st.markdown("---")
    st.markdown("### 📜 Memória de Sessões")
    recent = db.list_recent_sessions(pid, limit=4)
    if not recent:
        st.write("Sem sessões salvas.")
    else:
        for s in recent:
            with st.expander(f"{s['created_at'].strftime('%d/%m %H:%M')} · {s['tool']}"):
                st.json(s["coach"])
