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
    generate_problem_benefits_from_vocvob,
    generate_smart_goal_from_charter_context,
    suggest_vocvob_row,
)

st.set_page_config(page_title="Lean Copilot MVP", layout="wide", page_icon="🏥")
db.init_db()


def inject_custom_css(is_logged_in: bool):
    if not is_logged_in:
        # Fundo Azul Escuro total para a tela de Login (Estilo Capa do PPT)
        st.markdown("""
            <style>
            .stApp {
                background-color: #001C59 !important;
                background-image: radial-gradient(circle at top right, #00AEEF 0%, transparent 35%);
            }
            /* Textos brancos padrão */
            h1, h2, h3, p, label, .stMarkdown, .stTabs [data-baseweb="tab-list"] button {
                color: #FFFFFF !important;
            }
            /* Forçar as cores da Logo Box especificamente para sobrepor a regra anterior */
            .logo-box * {
                color: #001C59 !important;
            }
            .logo-box .azul-claro {
                color: #00AEEF !important;
            }
            
            /* Destaque da aba ativa em Verde Sírio */
            .stTabs [aria-selected="true"] {
                color: #93E07E !important;
                border-bottom-color: #93E07E !important;
                font-weight: bold;
            }
            /* Caixas de Texto (Off-white para contraste) */
            .stTextInput > div > div > input {
                background-color: #F4F0E3 !important;
                color: #07223A !important;
                border-radius: 6px;
                border: none;
            }
            .stTextInput label {
                color: #F4F0E3 !important;
            }
            /* Botões de Ação na Aba Login */
            div.stButton > button {
                background-color: #00AEEF !important;
                color: white !important;
                border-radius: 8px;
                font-weight: 600;
                border: none;
                transition: all 0.2s;
            }
            div.stButton > button:hover {
                background-color: #93E07E !important;
                color: #001C59 !important;
                transform: scale(1.02);
            }
            </style>
        """, unsafe_allow_html=True)
    else:
        # Fundo claro para área logada (Visualização dos Dados)
        st.markdown("""
            <style>
            [data-testid="stSidebar"] {
                background-color: #001C59 !important;
                border-right: 1px solid #E2E8F0;
            }
            [data-testid="stSidebar"] * {
                color: #FFFFFF !important;
            }
            header { background-color: #F7F7F7 !important; }
            .stApp { background-color: #F7F7F7 !important; }
            
            div.stButton > button {
                background-color: #00AEEF !important;
                color: white !important;
                border-radius: 8px;
                font-weight: 600;
                border: none;
                transition: all 0.2s;
            }
            div.stButton > button:hover {
                background-color: #004992 !important;
                transform: scale(1.02);
            }
            h1, h2 { color: #001C59 !important; font-weight: 700 !important; }
            h3, h4, h5 { color: #00AEEF !important; font-weight: 600 !important; }
            .stDataFrame { border-radius: 10px; border: 1px solid #E6E6E6; }
            </style>
        """, unsafe_allow_html=True)

# --- Auth Layer ---
if "user" not in st.session_state:
    st.session_state.user = None

inject_custom_css(bool(st.session_state.user))

def handle_login():
    # Logo Box do Sírio-Libanês para a Capa usando as classes corretas
    st.markdown("""
        <div style="display: flex; justify-content: center; align-items: center; padding: 20px;">
            <div class="logo-box" style="background-color: white; padding: 25px 40px; border-radius: 12px; display: inline-block; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                <h1 style='margin: 0; font-size: 2.8em; font-family: sans-serif; letter-spacing: -1px;'>
                    <span class="azul-claro">SÍRIO</span>·LIBANÊS
                </h1>
                <p style="margin: 0; font-size: 1.1em; text-align: right; font-weight: 300;">Consultoria</p>
            </div>
        </div>
        <br>
        <h3 style='text-align: center; color: #93E07E !important; margin-bottom: 40px; font-weight: 400;'>Copiloto de Melhoria Contínua</h3>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1.5, 2, 1.5])
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
    st.empty() # Radio button removido daqui para ficar na lateral direita do Coach

tool_container = st.container()
coach_container = st.container()
new_text = ""

with tool_container:
    if tool == "Capa do Projeto":
        st.subheader("Capa do Projeto")
        st.markdown("Bem-vindo! Documente a identidade oficial da sua iniciativa de melhoria.")
        
        with st.container(border=True):
            novo_nome = st.text_input("Nome Oficial do Projeto", value=project_state.get("name", ""), disabled=read_only)
            lider = st.text_input("Líder do Projeto (Green Belt / Black Belt)", value=project_state.get("leader", ""), disabled=read_only)
            sponsor = st.text_input("Patrocinador (Sponsor)", value=project_state.get("sponsor", ""), disabled=read_only)
            
            resumo = st.text_area("Resumo Executivo (Elevator Pitch)", value=project_state.get("executive_summary", ""), height=120, disabled=read_only, help="Opcional. Uma breve descrição executiva do seu propósito.")
            
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("💾 Salvar Capa", disabled=read_only, use_container_width=True):
                    if not novo_nome.strip():
                        st.error("⚠️ O nome do projeto não pode ficar em branco!")
                    else:
                        project_state["name"] = novo_nome.strip()
                        project_state["leader"] = lider.strip()
                        project_state["sponsor"] = sponsor.strip()
                        project_state["executive_summary"] = resumo.strip()
                        
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.success("Tudo salvo! Seu projeto foi atualizado.")
                        st.rerun()

    elif tool == "VOC/VOB":
        st.subheader("VOC/VOB (Voz do Cliente e Negócio)")

        draft = db.load_draft(pid, tool) or {}
        stored = draft.get("voc_vob") or project_state.get("voc_vob") or {"voc": [], "vob": [], "notes": ""}

        def render_custom_grid(data_list: List[Dict[str, Any]], prefix_key: str) -> List[Dict[str, Any]]:
            # Se não tiver linhas, inicia com 3 vazias
            if not data_list:
                data_list = [{"Voz (necessidade)": "", "Problema": "", "Requisito crítico": "", "Y (indicador)": ""} for _ in range(3)]
                
            # Cabeçalhos fixos com negrito
            st.markdown(
                '<div style="background-color: #001C59; color: white; padding: 10px; border-radius: 6px;">'
                '<div style="display: flex;">'
                '<div style="flex: 1; padding: 0 10px;"><b>Voz (necessidade)</b></div>'
                '<div style="flex: 1; padding: 0 10px;"><b>Problema</b></div>'
                '<div style="flex: 1; padding: 0 10px;"><b>Requisito crítico</b></div>'
                '<div style="flex: 1; padding: 0 10px;"><b>Y (indicador)</b></div>'
                '</div></div><br>', 
                unsafe_allow_html=True
            )
            
            out_rows = []
            for i, row in enumerate(data_list):
                c1, c2, c3, c4 = st.columns(4)
                
                v1_txt = str(row.get("Voz (necessidade)", ""))
                v2_txt = str(row.get("Problema", ""))
                v3_txt = str(row.get("Requisito crítico", ""))
                v4_txt = str(row.get("Y (indicador)", row.get("Y (como medir)", "")))
                
                # Calcular altura ideal baseando-se na caixa mais cheia (aprox. 35 chars por linha visual)
                max_len = max(len(v1_txt), len(v2_txt), len(v3_txt), len(v4_txt))
                linhas = max(2, (max_len // 35) + 1)
                altura_sincronizada = min(350, (linhas * 26) + 45) # limite de 350px para não estourar a tela
                
                # Caixas de texto configuradas para wrap, todas adotando a mesma altura na linha
                v1 = c1.text_area("v1", value=v1_txt, key=f"{prefix_key}_v_{i}", height=altura_sincronizada, label_visibility="collapsed", disabled=read_only)
                v2 = c2.text_area("v2", value=v2_txt, key=f"{prefix_key}_p_{i}", height=altura_sincronizada, label_visibility="collapsed", disabled=read_only)
                v3 = c3.text_area("v3", value=v3_txt, key=f"{prefix_key}_c_{i}", height=altura_sincronizada, label_visibility="collapsed", disabled=read_only)
                v4 = c4.text_area("v4", value=v4_txt, key=f"{prefix_key}_y_{i}", height=altura_sincronizada, label_visibility="collapsed", disabled=read_only)
                out_rows.append({"Voz (necessidade)": v1, "Problema": v2, "Requisito crítico": v3, "Y (indicador)": v4})
                
            return out_rows

        tab1, tab2 = st.tabs(["Voz do Cliente (VOC)", "Voz do Negócio (VOB)"])
        
        with tab1:
            voc_list = stored.get("voc", [])
            voc_out_raw = render_custom_grid(voc_list, "voc")
            
            # Botões de Adicionar/Remover Linhas
            if not read_only:
                b1, b2, _ = st.columns([1, 1, 4])
                with b1:
                    if st.button("➕ Adicionar Linha", key="btn_add_voc", use_container_width=True):
                        stored["voc"] = voc_out_raw + [{"Voz (necessidade)": "", "Problema": "", "Requisito crítico": "", "Y (indicador)": ""}]
                        project_state["voc_vob"] = stored
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.rerun()
                with b2:
                    if len(voc_out_raw) > 1:
                        if st.button("🗑️ Remover Última", key="btn_rem_voc", use_container_width=True):
                            stored["voc"] = voc_out_raw[:-1]
                            project_state["voc_vob"] = stored
                            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                            st.rerun()
            voc_out = voc_out_raw

        with tab2:
            vob_list = stored.get("vob", [])
            vob_out_raw = render_custom_grid(vob_list, "vob")
            
            if not read_only:
                b1, b2, _ = st.columns([1, 1, 4])
                with b1:
                    if st.button("➕ Adicionar Linha", key="btn_add_vob", use_container_width=True):
                        stored["vob"] = vob_out_raw + [{"Voz (necessidade)": "", "Problema": "", "Requisito crítico": "", "Y (indicador)": ""}]
                        project_state["voc_vob"] = stored
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.rerun()
                with b2:
                    if len(vob_out_raw) > 1:
                        if st.button("🗑️ Remover Última", key="btn_rem_vob", use_container_width=True):
                            stored["vob"] = vob_out_raw[:-1]
                            project_state["voc_vob"] = stored
                            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                            st.rerun()
            vob_out = vob_out_raw

        notes = st.text_area("Anotações Adicionais (opcional)", value=stored.get("notes", ""), height=100, disabled=read_only)
        
        # Gerar o texto a partir do formulário p/ análise da IA
        new_text = f"VOC Rows: {len(voc_out)}\nVOB Rows: {len(vob_out)}\nNotas: {notes}"

        c1, c2 = st.columns([1, 3])
        with c1:
            if st.button("💾 Salvar Planilha", disabled=read_only):
                payload = {"voc_vob": {"voc": voc_out, "vob": vob_out, "notes": notes}, "text": new_text}
                db.save_draft(pid, tool, payload)
                project_state["voc_vob"] = {"voc": voc_out, "vob": vob_out, "notes": notes}
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.success("Salvo com sucesso!")

    elif tool == "Project Charter":
        st.subheader("Project Charter (Contrato de Melhoria)")
        storage_tool = tool

        draft = db.load_draft(pid, storage_tool) or {}
        charter = draft.get("charter") or project_state.get("charter") or {}
        timeline = charter.get("timeline_weeks") or {"Define": 0, "Measure": 0, "Analyze": 0, "Improve": 0, "Control": 0}
        st_struct = charter.get("stakeholders_struct") or {}

        # Ajuste de layout de blocos para visual Sírio Premium
        with st.container(border=True):
            col_p1, col_p2 = st.columns([5, 1.8])
            with col_p1:
                st.markdown("**Problema / Justificativa**")
            with col_p2:
                if st.button("📥 Importar do VOC/VOB", help="Importa dados do VOC/VOB apenas para os campos ainda vazios", use_container_width=True, disabled=read_only):
                    # Força a leitura do que está escrito agora na tela (caso tenha apagado)
                    v_prob = str(st.session_state.get("charter_problem", charter.get("problem", ""))).strip()
                    v_ind = str(st.session_state.get("charter_ind", charter.get("main_indicator", ""))).strip()
                    v_goal = str(st.session_state.get("charter_goal", charter.get("goal", ""))).strip()
                    
                    tem_prob = (len(v_prob) > 0)
                    tem_ind = (len(v_ind) > 0)
                    tem_goal = (len(v_goal) > 0) and not v_goal.startswith("[INCOMPLETO")
                    
                    v_state = project_state.get("voc_vob", {})
                    linhas = v_state.get("voc", []) + v_state.get("vob", [])
                    
                    if not linhas:
                        st.error("⚠️ O banco de dados do seu VOC/VOB está vazio! Você preencheu mas esqueceu de Clicar em Salvar no final da página do VOC/VOB!")
                    else:
                        extraidos = []
                        indicadores = []
                        requisitos = []
                        
                        for row in linhas:
                            # Tenta caçar o Problema
                            p = str(row.get("Problema", "")).strip()
                            if p: extraidos.append(f"- {p}")
                            
                            # Tenta caçar o Indicador usando a coluna oficial nova ou a velha
                            y = str(row.get("Y (indicador)", "")).strip()
                            if not y: y = str(row.get("Y (como medir)", "")).strip()
                            if y: indicadores.append(y)
                                
                            # Tenta caçar Requisitos CTQ
                            r = str(row.get("Requisito crítico", "")).strip()
                            if r: requisitos.append(f"- {r}")
                            
                        atualizou = False
                        
                        # Só preenchemos o que o usuário não preencheu/apagou
                        if not tem_prob and extraidos:
                            charter["problem"] = "\n".join(extraidos)
                            atualizou = True
                            
                        if not tem_ind and indicadores:
                            charter["main_indicator"] = "\n".join(list(dict.fromkeys(indicadores)))
                            atualizou = True
                            
                        if not tem_goal and requisitos:
                            lista_reqs = "\n".join(list(dict.fromkeys(requisitos)))
                            charter["goal"] = f"[INCOMPLETO - Falta estrutura SMART]\nObjetivo final deve atingir os seguintes CTQs importados:\n{lista_reqs}"
                            atualizou = True
                            
                        if atualizou:
                            project_state["charter"] = charter
                            db.save_draft(pid, tool, {"charter": charter, "text": "Charter Data: " + json.dumps(charter)})
                            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                            st.rerun()
                        else:
                            if tem_prob and tem_ind and tem_goal:
                                st.warning("⚠️ Todos os campos vitais já estão preenchidos na tela.", icon="⚠️")
                            else:
                                st.toast("Não encontrei palavras preenchidas dentro das colunas lá do VOC/VOB para as lacunas daqui.", icon="🔍")

            problem = st.text_area("hidden_problem", value=charter.get("problem", ""), key="charter_problem", height=150, label_visibility="collapsed", disabled=read_only)
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Objetivo (SMART)**")
                goal = st.text_area("hidden_goal", value=charter.get("goal", ""), key="charter_goal", height=120, label_visibility="collapsed", disabled=read_only)
            with c2:
                st.markdown("**Indicador Principal**")
                main_indicator = st.text_area("hidden_ind", value=charter.get("main_indicator", ""), key="charter_ind", height=120, label_visibility="collapsed", disabled=read_only)
                
            benefits = st.text_area("Benefícios", value=charter.get("benefits", ""), height=150, disabled=read_only)
        
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
            "problem": problem, "benefits": benefits, "goal": goal, "main_indicator": main_indicator, "scope_in": scope_in, "scope_out": scope_out,
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

with coach_container:
    st.markdown("<br><hr>", unsafe_allow_html=True)
    st.subheader("👨🏻‍⚕️ Coach IA - Doutor Lean")
    
    # Alerta de que uma linha foi gerada com sucesso pela IA na última rodada (após o rerun)
    if st.session_state.get("ai_generated_warning"):
        st.warning(st.session_state["ai_generated_warning"])
        # Limpar para não ficar piscando pra sempre
        st.session_state["ai_generated_warning"] = ""

    # Nova interface intuitiva solicitada:
    ia_action = st.radio(
        "Como a IA pode te ajudar agora?",
        ["Revisão do Coach IA", "Gere uma Sugestão de Preenchimento"],
        disabled=read_only,
        key=f"ia_action_{tool}"
    )
    
    ai_context_prompt = ""
    target_voc = "Voz do Cliente (VOC)"
    q1 = q2 = q3 = ""
    q_impact = ""
    q_tempo = ""
    q_meta = ""
    target_charter = ""
    
    if ia_action == "Gere uma Sugestão de Preenchimento":
        if tool == "VOC/VOB":
            st.info("💡 **Preenchimento Guiado VOC/VOB:** A IA vai gerar uma linha de referência para sua tabela baseada nas 3 respostas abaixo.")
            target_voc = st.radio("Gerar sugestão para:", ["Voz do Cliente (VOC)", "Voz do Negócio (VOB)"], disabled=read_only)
            q1 = st.text_input("Qual a necessidade do cliente (ou negócio)?", disabled=read_only)
            q2 = st.text_input("Qual é o valor atual / performance atual?", disabled=read_only)
            q3 = st.text_input("Qual é o valor limite entre a satisfação e a insatisfação?", disabled=read_only)
        elif tool == "Project Charter":
            target_charter = st.radio("O que o Doutor Lean deve estruturar?", ["Problema e Benefícios", "Objetivo SMART"], disabled=read_only)
            
            if target_charter == "Problema e Benefícios":
                st.info("💡 **Geração Guiada (via VOC/VOB):** O Doutor Lean irá ler o VOC/VOB para narrar o Problema baseando-se no impacto no Negócio/Cliente.")
                v_state = project_state.get("voc_vob", {})
                has_voc_vob = (len(v_state.get("voc", [])) > 0) or (len(v_state.get("vob", [])) > 0)
                
                if not has_voc_vob:
                    st.warning("⚠️ **Bloqueado:** Para que o Doutor Lean construa o Problema e os Benefícios de forma coerente, você precisa preencher o **VOC/VOB** obrigatoriamente primeiro. Volte e salve o VOC/VOB.")
                    read_only = True
                else:
                    q_impact = st.text_area("Qual o impacto sofrido pelo cliente de não ter a sua necessidade atendida?", height=80, disabled=read_only)
            else:
                st.info("💡 **Geração SMART:** O Doutor Lean reescreverá o que estiver importado na caixa do Objetivo do seu Charter transformando numa meta oficial de excelência.")
                q_tempo = st.text_input("Prazo: Em quanto tempo atingiremos o objetivo? (Ex: até Dez/2024)", disabled=read_only)
                q_meta = st.text_input("Meta: Qual o número a ser atingido? (Ex: Reduzir tempo para 15min)", disabled=read_only)
        else:
            st.info("💡 **Dica:** A IA lerá todo o contexto do seu projeto automaticamente. Se quiser, você pode direcioná-la adicionando um pedido específico abaixo.")
            ai_context_prompt = st.text_area(
                "Contexto ou Pedido Específico (Opcional):",
                placeholder="Ex: Foque apenas em redução de tempo na área de triagem...",
                height=80,
                disabled=read_only
            )
        st.warning("⚠️ **Atenção:** As informações geradas por Inteligência Artificial são exclusivas para direcionamento metodológico e devem obrigatoriamente ser revisadas e validadas na tabela ao lado antes do uso.")
        
    btn_label = "🔎 Iniciar Revisão" if ia_action == "Revisão do Coach IA" else "✨ Gerar Sugestão"

    if st.button(btn_label, disabled=read_only, use_container_width=True):
        mode_str = "review" if ia_action == "Revisão do Coach IA" else "generate"
        
        # --- FLUXO ESPECIAL: Geração (Autocompletar) do VOC/VOB ---
        if tool == "VOC/VOB" and mode_str == "generate":
            with st.spinner(f"Doutor Lean gerando linha para {target_voc}..."):
                new_row = suggest_vocvob_row(target_voc, q1, q2, q3, project_state)
                # Onde inserir?
                t_key = "voc" if target_voc == "Voz do Cliente (VOC)" else "vob"
                if "voc_vob" not in project_state:
                    project_state["voc_vob"] = {"voc": [], "vob": [], "notes": ""}
                if t_key not in project_state["voc_vob"]:
                    project_state["voc_vob"][t_key] = []
                
                # Anexa a nova linha gerada
                project_state["voc_vob"][t_key].append(new_row)
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                
                # Mostra o alerta de sucesso e forca o reload pra tabela atualizar sozinha
                st.session_state["ai_generated_warning"] = "✨ ⚠️ Linha inserida automaticamente pela Inteligência Artificial na tabela. Por favor, releia, valide os campos e salve!"
                st.rerun()

        # --- FLUXO ESPECIAL: Geração do Charter via VOC/VOB (Problema) ---
        elif tool == "Project Charter" and mode_str == "generate" and target_charter == "Problema e Benefícios":
            if not q_impact:
                st.warning("Por favor, preencha o impacto percebido antes de gerar sugestões.")
            else:
                with st.spinner("Doutor Lean processando seu VOC/VOB e descrevendo o Problema..."):
                    new_data = generate_problem_benefits_from_vocvob(project_state, q_impact)
                    
                    if "charter" not in project_state:
                        project_state["charter"] = {}
                    project_state["charter"]["problem"] = new_data.get("problem", "")
                    project_state["charter"]["benefits"] = new_data.get("benefits", "")
                    
                    # Se o aluno pulou o botão de importação, vamos sugar o indicador quietamente pra ajudá-lo
                    if not project_state["charter"].get("main_indicator"):
                        v_state = project_state.get("voc_vob", {})
                        indics = []
                        for row in v_state.get("voc", []) + v_state.get("vob", []):
                            y_v = str(row.get("Y (indicador)", row.get("Y (como medir)", ""))).strip()
                            if y_v: indics.append(y_v)
                        if indics:
                            project_state["charter"]["main_indicator"] = " / ".join(list(dict.fromkeys(indics)))
                    
                    db.save_draft(pid, "Project Charter", {"charter": project_state["charter"], "text": "AI Generated Charter (Problem)"})
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    
                    st.session_state["ai_generated_warning"] = "✨ ⚠️ Problema e Benefícios gerados automaticamente associando o impacto da necessidade original transcrita do VOC/VOB! Releia e verifique se as premissas estão corretas."
                    st.rerun()

        # --- FLUXO ESPECIAL: Geração do Charter via VOC/VOB (SMART Goal) ---
        elif tool == "Project Charter" and mode_str == "generate" and target_charter == "Objetivo SMART":
            if not q_tempo or not q_meta:
                 st.warning("Por favor, preencha o prazo e a meta numérica para construirmos o SMART!")
            else:
                with st.spinner("Estruturando meta SMART e consolidando objetivo..."):
                    smart_goal = generate_smart_goal_from_charter_context(project_state, q_tempo, q_meta)
                    if "charter" not in project_state:
                        project_state["charter"] = {}
                    project_state["charter"]["goal"] = smart_goal
                    
                    # Força a captura do indicador caso ainda esteja vazia
                    if not project_state["charter"].get("main_indicator"):
                        v_state = project_state.get("voc_vob", {})
                        indics = []
                        for row in v_state.get("voc", []) + v_state.get("vob", []):
                            y_v = str(row.get("Y (indicador)", row.get("Y (como medir)", ""))).strip()
                            if y_v: indics.append(y_v)
                        if indics:
                            project_state["charter"]["main_indicator"] = " / ".join(list(dict.fromkeys(indics)))
                    
                    db.save_draft(pid, "Project Charter", {"charter": project_state["charter"], "text": "AI Generated Charter (SMART Goal)"})
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.session_state["ai_generated_warning"] = "✨ ⚠️ Objetivo construído segundo o padrão SMART! Releia e edite se necessário."
                    st.rerun()

        # --- FLUXO PADRÃO (Revisão ou Outras ferramentas) ---
        else:
            # Injeta o contexto extra do usuário no inicio do texto que a IA vai ler
            text_for_ai = new_text
            if mode_str == "generate" and ai_context_prompt.strip():
                 text_for_ai = f"PEDIDO ESPECÍFICO DO USUÁRIO PARA ESTA GERAÇÃO: {ai_context_prompt}\n\nDADOS ATUAIS DA FERRAMENTA:\n{new_text}"

            with st.spinner("Doutor Lean processando os dados..."):
                coach_json, rubric_scores, _ = coach_run(tool, project_state, text_for_ai, mode=mode_str)
                sid = new_session_id()
                db.add_session_log(
                    session_id=sid, project_id=pid, tool=tool,
                    event_type="REQUEST_COACH", user_delta=f"Modo: {mode_str}", coach_payload=coach_json,
                )

                st.markdown("### ✅ Pontos Positivos")
                if coach_json.get("ok"):
                    for ok in coach_json["ok"]:
                        st.success(f"✔ {ok}")
                else:
                    st.write("-")

                st.markdown("### ⚠️ Diagnóstico / Sugestões")
                if coach_json.get("gaps"):
                    for g in coach_json["gaps"]:
                        st.error(f"**{pretty_gap_id(g.get('id', ''))}**: {g.get('reason', '')}")
                else:
                    st.write("- A análise não encontrou gaps ou gerou novas propriedades.")

                st.markdown("### 🏹 Plano de Ação ou Conteúdo Gerado")
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
