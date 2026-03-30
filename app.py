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
    suggest_sipoc_macro,
    suggest_sipoc_io,
    suggest_saving_rationale,
    suggest_matriz_indicadores
)

try:
    from custom_components.bpmn_editor import st_bpmn
except ImportError:
    st_bpmn = None

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

    if ROLE == "professor":
        st.markdown("### 🛠️ Painel Admin")
        st.caption("Configurações Globais (Afeta todos os alunos)")
        current_ai = db.get_global_model()
        
        # Mapeamento oficial 2026 (Atualizado pela Doc OpenAI - ChatGPT)
        model_options = {
            "gpt-5.4": "🟣 gpt-5.4 (Padrão 2026 - Uso Geral)",
            "gpt-5.4-pro": "🔴 gpt-5.4-pro (Alta inteligência - Problemas Difíceis)",
            "gpt-5.4-mini": "🟡 gpt-5.4-mini (Rápido e Barato - Automações)",
            "gpt-5.4-nano": "🟢 gpt-5.4-nano (Extrema economia - Alto Volume)",
            "gpt-4.1": "🟤 gpt-4.1 (Manter Compatibilidade)",
            "gpt-4.1-mini": "🟠 gpt-4.1-mini (Menor e mais rápida do 4.1)",
            "gpt-4o-mini": "🛜 gpt-4o-mini (Modelo leve 2024)",
            "o3-mini": "🔵 o3-mini (Raciocínio Avançado)",
            "Outro": "⚙️ Outro (Digitar Manualmente)"
        }
        
        options_list = list(model_options.values())
        
        # Qual o index do modelo atual?
        default_idx = 2 # Padrão cai no gpt-4o-mini se não achar
        for idx, k in enumerate(model_options.keys()):
            if k == current_ai:
                default_idx = idx
                break
        
        # Se for um modelo alienígena que o prof digitou antes, força cair no 'Outro'
        if current_ai not in model_options:
            default_idx = len(options_list) - 1 
            
        selected_display = st.selectbox("Selecione a Engine de IA:", options_list, index=default_idx)
        
        # Mapeamento reverso
        new_ai = ""
        for k, v in model_options.items():
            if v == selected_display:
                new_ai = k
                break
                
        # Só exibe a caixa de texto se o Dropdown estiver fisicamente selecionado na opção 'Outro'
        if new_ai == "Outro":
            custom_input = st.text_input(
                "Digite o nome exato da versão:", 
                value=current_ai if current_ai not in model_options else ""
            )
            if custom_input.strip(): 
                new_ai = custom_input.strip()

        if st.button("Salvar Modelo para Todos", use_container_width=True):
            if new_ai and new_ai != "Outro":
                db.set_global_model(new_ai)
                st.success(f"Plataforma roteada para {new_ai}!")
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
        "raci": [],
        "sipoc": {"serpentes": [], "rows": [], "notes": ""},
        "matriz_indicadores": [],
        "fluxograma_xml": "",
        "saving_projetado": {
            "hard": 0.0, "hard_racional": "",
            "soft": 0.0, "soft_racional": "",
            "avoidance": 0.0, "avoidance_racional": "",
            "faturamento": 0.0, "faturamento_racional": "",
            "notas_gerais": ""
        },
        "metrics": [],
        "baseline": {"period": "", "values": {}, "notes": ""},
        "hypotheses": [],
        "solutions": [],
        "pilots": [],
        "control_plan": [],
        "saving_realizado": {
            "hard": 0.0, "hard_racional": "",
            "soft": 0.0, "soft_racional": "",
            "avoidance": 0.0, "avoidance_racional": "",
            "faturamento": 0.0, "faturamento_racional": "",
            "notas_gerais": ""
        },
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
            
            cap1, cap2, cap3 = st.columns(3)
            with cap1:
                lider = st.text_input("Líder do Projeto (Yellow / Green / Black Belt)", value=project_state.get("leader", ""), disabled=read_only)
            with cap2:
                sponsor = st.text_input("Patrocinador (Sponsor)", value=project_state.get("sponsor", ""), disabled=read_only)
            with cap3:
                start_str = project_state.get("start_date", "")
                try:
                    default_date = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else datetime.now().date()
                except:
                    default_date = datetime.now().date()
                start_date = st.date_input("Data de Início do Projeto", value=default_date, disabled=read_only, format="DD/MM/YYYY")
            
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
                        project_state["start_date"] = start_date.strftime("%Y-%m-%d")
                        project_state["executive_summary"] = resumo.strip()
                        
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.rerun()

        # Alimenta o contexto do Doutor Lean com os campos exclusivos da Capa
        new_text = f"Nome do Projeto: {novo_nome}\nLíder: {lider}\nSponsor: {sponsor}\nInício: {start_date}\nResumo Executivo: {resumo}"


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
                
            benefits = st.text_area("Benefícios", value=charter.get("benefits", ""), key="charter_benefits", height=150, disabled=read_only)
        
        with st.container(border=True):
            sA, sB = st.columns(2)
            with sA:
                scope_in = st.text_area("Dentro do Escopo (IN)", value=charter.get("scope_in", ""), height=80, disabled=read_only)
            with sB:
                scope_out = st.text_area("Fora do Escopo (OUT)", value=charter.get("scope_out", ""), height=80, disabled=read_only)

        with st.container(border=True):
            hdr1, hdr2 = st.columns([4, 1.5], vertical_alignment="center")
            with hdr1:
                st.markdown("#### Matriz de Envolvidos (Stakeholders)")
            with hdr2:
                if st.button("📥 Preencher da Capa", help="Copiar o Líder e o Sponsor oficiais definidos na Capa do Projeto", use_container_width=True, disabled=read_only):
                    st_struct["sponsor"] = project_state.get("sponsor", "")
                    st_struct["lider_projeto"] = project_state.get("leader", "")
                    charter["stakeholders_struct"] = st_struct
                    project_state["charter"] = charter
                    db.save_draft(pid, tool, {"charter": charter, "text": "Stakeholders Importados"})
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.rerun()
                    
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
            
            from datetime import timedelta
            start_str = project_state.get("start_date", "")
            try:
                current_date = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else datetime.now().date()
            except:
                current_date = datetime.now().date()

            total_weeks = d_w + m_w + a_w + i_w + c_w
            
            if total_weeks > 0:
                phases = [("Define", d_w), ("Measure", m_w), ("Analyze", a_w), ("Improve", i_w), ("Control", c_w)]
                colors = ["#1f77b4", "#d62728", "#ff7f0e", "#2ca02c", "#9467bd"]
                
                tasks = []
                for i, (p_name, w) in enumerate(phases):
                    if w > 0:
                        end_date = current_date + timedelta(weeks=int(w))
                        tasks.append({
                            "Fase": p_name,
                            "Início": current_date,
                            "Fim": end_date,
                            "Cor": colors[i]
                        })
                        current_date = end_date
                
                if tasks:
                    df_gantt = pd.DataFrame(tasks)
                    df_gantt["Início"] = pd.to_datetime(df_gantt["Início"])
                    df_gantt["Fim"] = pd.to_datetime(df_gantt["Fim"])
                    
                    chart = alt.Chart(df_gantt).mark_bar(cornerRadius=4, height=20).encode(
                        x=alt.X('Início:T', title='Data do Cronograma DMAIC', axis=alt.Axis(format='%d/%m/%Y', labelAngle=-45, grid=True)),
                        x2='Fim:T',
                        y=alt.Y('Fase:N', sort=["Define", "Measure", "Analyze", "Improve", "Control"], title='', axis=alt.Axis(labelPadding=10, labelFontWeight="bold")),
                        color=alt.Color('Fase:N', scale=alt.Scale(domain=[p[0] for p in phases], range=colors), legend=None),
                        tooltip=[
                            alt.Tooltip('Fase:N', title='Etapa'), 
                            alt.Tooltip('Início:T', format='%d/%m/%Y', title='Data Início'), 
                            alt.Tooltip('Fim:T', format='%d/%m/%Y', title='Data Fim')
                        ]
                    ).properties(
                        height=250
                    ).configure_view(
                        strokeWidth=0
                    )
                    st.markdown("---")
                    st.markdown("**Gráfico de Gantt do Projeto (Baseado na Capa e nas Semanas)**")
                    st.altair_chart(chart, use_container_width=True)

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

    elif tool == "SIPOC (por etapa)":
        st.subheader("SIPOC (Mapeamento de Processo Nível Macro)")
        st.markdown("Preencha de *Dentro para Fora*: **Comece pela Etapa do Processo (P)** no centro. Depois, liste as múltiplas Entradas (I) e seus Fornecedores (S) de um lado, e as Saídas (O) e Clientes (C) do outro, clicando nos botões de ➕.")
        
        draft = db.load_draft(pid, tool) or {}
        stored_sipoc = draft.get("sipoc") or project_state.get("sipoc") or []
        
        # Correção Blindada do BUG Fantasma / Migração do Legado:
        # Se a interface mudou e o que está salvo no banco não reflete o novo modelo de Dict focado no Node 'P', zera e dá o overwrite.
        if not isinstance(stored_sipoc, list) or (len(stored_sipoc) > 0 and not isinstance(stored_sipoc[0], dict)) or (len(stored_sipoc) > 0 and "P" not in stored_sipoc[0]):
            stored_sipoc = []
            
        def render_sipoc_blocks(data_list):
            if not data_list:
                data_list = [{"P": "", "inputs": [{"S": "", "I": ""}], "outputs": [{"O": "", "C": ""}]} for _ in range(4)]
                
            st.markdown(
                '<div style="background-color: #001C59; color: white; padding: 10px; border-radius: 6px;">'
                '<div style="display: flex; text-align: center;">'
                '<div style="flex: 1; padding: 0 5px;"><b>S (Fornecedores)</b></div>'
                '<div style="flex: 1; padding: 0 5px;"><b>I (Entradas)</b></div>'
                '<div style="flex: 1; padding: 0 5px;"><b>P (Processo Central)</b></div>'
                '<div style="flex: 1; padding: 0 5px;"><b>O (Saídas)</b></div>'
                '<div style="flex: 1; padding: 0 5px;"><b>C (Clientes)</b></div>'
                '</div></div><br>', 
                unsafe_allow_html=True
            )
            
            out_rows = []
            for i, step in enumerate(data_list):
                with st.container(border=True):
                    c_s, c_i, c_p, c_o, c_c = st.columns(5)
                    
                    # Coluna do Meio (Mãe): Processo
                    with c_p:
                        p_val = st.text_area(f"p_{i}", value=step.get("P", ""), placeholder="Descreva a Etapa do Processo...", height=150, label_visibility="collapsed", disabled=read_only)
                        
                    # Lado Esquerdo: Entradas e Fornecedores
                    inps = step.get("inputs", [])
                    if not isinstance(inps, list) or len(inps) == 0: inps = [{"S": "", "I": ""}]
                    
                    new_inps = []
                    for j, inp in enumerate(inps):
                        with c_s:
                            s_v = st.text_input(f"s_{i}_{j}", value=inp.get("S", ""), placeholder="Fornecedor...", label_visibility="collapsed", disabled=read_only)
                        with c_i:
                            i_v = st.text_input(f"i_{i}_{j}", value=inp.get("I", ""), placeholder="Entrada / Matéria...", label_visibility="collapsed", disabled=read_only)
                        new_inps.append({"S": s_v, "I": i_v})
                        
                    with c_i:
                        if not read_only:
                            c_add, c_rem = st.columns(2)
                            with c_add:
                                if st.button("➕", help="Adicionar Fornecedor/Entrada", key=f"btn_add_inp_{i}", use_container_width=True):
                                    inps.append({"S": "", "I": ""})
                                    project_state["sipoc"] = data_list
                                    project_state["sipoc"][i]["inputs"] = inps
                                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                    st.rerun()
                            with c_rem:
                                if st.button("➖", help="Remover última Entrada", key=f"btn_rem_inp_{i}", use_container_width=True, disabled=(len(inps) <= 1)):
                                    inps.pop()
                                    project_state["sipoc"] = data_list
                                    project_state["sipoc"][i]["inputs"] = inps
                                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                    st.rerun()
                                
                    # Lado Direito: Saídas e Clientes
                    outs = step.get("outputs", [])
                    if not isinstance(outs, list) or len(outs) == 0: outs = [{"O": "", "C": ""}]
                    
                    new_outs = []
                    for k, out in enumerate(outs):
                        with c_o:
                            o_v = st.text_input(f"o_{i}_{k}", value=out.get("O", ""), placeholder="Saída / Produto...", label_visibility="collapsed", disabled=read_only)
                        with c_c:
                            c_v = st.text_input(f"c_{i}_{k}", value=out.get("C", ""), placeholder="Cliente...", label_visibility="collapsed", disabled=read_only)
                        new_outs.append({"O": o_v, "C": c_v})
                        
                    with c_o:
                        if not read_only:
                            c_add2, c_rem2 = st.columns(2)
                            with c_add2:
                                if st.button("➕", help="Adicionar Saída/Cliente", key=f"btn_add_out_{i}", use_container_width=True):
                                    outs.append({"O": "", "C": ""})
                                    project_state["sipoc"] = data_list
                                    project_state["sipoc"][i]["outputs"] = outs
                                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                    st.rerun()
                            with c_rem2:
                                if st.button("➖", help="Remover última Saída", key=f"btn_rem_out_{i}", use_container_width=True, disabled=(len(outs) <= 1)):
                                    outs.pop()
                                    project_state["sipoc"] = data_list
                                    project_state["sipoc"][i]["outputs"] = outs
                                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                    st.rerun()
                                
                    out_rows.append({"P": p_val, "inputs": new_inps, "outputs": new_outs})
                    
            return out_rows

        sipoc_out = render_sipoc_blocks(stored_sipoc)
        
        if not read_only:
            b1, b2, _ = st.columns([1.5, 1.5, 3])
            with b1:
                if st.button("➕ Nova Etapa de Processo Mestre", key="btn_add_sipoc_master", use_container_width=True):
                    stored_sipoc = sipoc_out + [{"P": "", "inputs": [{"S": "", "I": ""}], "outputs": [{"O": "", "C": ""}]}]
                    project_state["sipoc"] = stored_sipoc
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.rerun()
            with b2:
                if len(sipoc_out) > 1:
                    if st.button("🗑️ Remover Último Processo", key="btn_rem_sipoc_master", use_container_width=True):
                        stored_sipoc = sipoc_out[:-1]
                        project_state["sipoc"] = stored_sipoc
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.rerun()
        
        notes = draft.get("notes", project_state.get("sipoc_notes", ""))
        notas_out = st.text_area("Comentários; Notas; Questões (Opcional)", value=notes, height=80, disabled=read_only)

        new_text = f"SIPOC Master Rows: {len(sipoc_out)}\nNotas: {notas_out}"

        c1, c2 = st.columns([1, 3])
        with c1:
            if st.button("💾 Salvar SIPOC Completo", disabled=read_only):
                payload = {"sipoc": sipoc_out, "notes": notas_out, "text": new_text}
                db.save_draft(pid, tool, payload)
                project_state["sipoc"] = sipoc_out
                project_state["sipoc_notes"] = notas_out
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.success("SIPOC salvo com sucesso!")

    elif tool == "Matriz de Indicadores":
        st.subheader("Matriz de Indicadores (Métricas por Etapa do SIPOC)")
        st.info("💡 Liste as métricas e os indicadores associados a cada macro etapa mapeada.")
        
        draft = db.load_draft(pid, tool) or {}
        indicadores_data = project_state.get("matriz_indicadores", [])
        
        col_import, col_space = st.columns([2, 5])
        with col_import:
            if st.button("📥 Importar Etapas (P) do SIPOC", use_container_width=True, disabled=read_only):
                sipoc_data = project_state.get("sipoc", [])
                novas_linhas = []
                for s in sipoc_data:
                    p_text = str(s.get("P", "")).strip()
                    if p_text:
                        novas_linhas.append({
                            "Processo": p_text,
                            "Quantidade/Volume": "",
                            "Quantidade em processamento (WIP)": "",
                            "Tempo (Lead/Cycle Time)": "",
                            "Percentual (%)": "",
                            "Qualidade (Erro/NPS)": "",
                            "Financeiro (R$)": ""
                        })
                if not novas_linhas:
                     st.warning("Seu SIPOC parece estar vazio ou sem Etapas P cadastradas.")
                else:
                    project_state["matriz_indicadores"] = novas_linhas
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.success("Etapas importadas com sucesso do SIPOC!")
                    st.rerun()

        if not indicadores_data:
            indicadores_data = [{
                "Processo": "",
                "Quantidade/Volume": "",
                "Quantidade em processamento (WIP)": "",
                "Tempo (Lead/Cycle Time)": "",
                "Percentual (%)": "",
                "Qualidade (Erro/NPS)": "",
                "Financeiro (R$)": ""
            }]
            
        edited_ind = st.data_editor(
            indicadores_data,
            num_rows="dynamic",
            use_container_width=True,
            disabled=read_only,
            column_config={
                "Processo": st.column_config.TextColumn("Processo", help="Copiado do SIPOC", width="medium"),
                "Quantidade/Volume": st.column_config.TextColumn("Quantidade / Volume", width="medium"),
                "Quantidade em processamento (WIP)": st.column_config.TextColumn("Quantidade em Processamento (WIP)", width="medium"),
                "Tempo (Lead/Cycle Time)": st.column_config.TextColumn("Tempo", width="medium"),
                "Percentual (%)": st.column_config.TextColumn("%", width="small"),
                "Qualidade (Erro/NPS)": st.column_config.TextColumn("Qualidade", width="small"),
                "Financeiro (R$)": st.column_config.TextColumn("R$ (Financeiro)", width="small")
            }
        )
        
        # Gerar o texto a partir do formulário p/ análise da IA
        new_text = "Matriz de Indicadores:\n" + json.dumps(edited_ind, ensure_ascii=False)
        
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("💾 Salvar Matriz", disabled=read_only, use_container_width=True):
                project_state["matriz_indicadores"] = edited_ind
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                db.save_draft(pid, tool, {"text": new_text})
                st.success("Matriz de Indicadores salva!")

    elif tool in ["Saving Projetado", "Saving Realizado"]:
        st.subheader(f"Cálculo de {tool}")
        st.info("Desdobre o impacto financeiro. O 'Saving Total' será calculado automaticamente ao salvar.")
        state_key = "saving_projetado" if tool == "Saving Projetado" else "saving_realizado"
        sav = project_state.get(state_key) or {}
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Hard Saving")
            st.markdown("<div style='height:40px; font-size:13px; color:gray;'>(Impacto Direto no DRE - Ex: Materiais, Faturado)</div>", unsafe_allow_html=True)
            h_val = st.number_input("Valor (R$)", value=float(sav.get("hard", 0.0)), disabled=read_only, key=f"hard_{state_key}")
            h_rac = st.text_area("Memorial de Cálculo (Como chegou no valor)", value=sav.get("hard_racional", ""), height=150, disabled=read_only, key=f"hr_{state_key}")
        with c2:
            st.markdown("#### Soft Saving")
            st.markdown("<div style='height:40px; font-size:13px; color:gray;'>(Ganho Operacional / Liberação de Capacidade)</div>", unsafe_allow_html=True)
            s_val = st.number_input("Valor (R$)", value=float(sav.get("soft", 0.0)), disabled=read_only, key=f"soft_{state_key}")
            s_rac = st.text_area("Memorial de Cálculo (Como chegou no valor)", value=sav.get("soft_racional", ""), height=150, disabled=read_only, key=f"sr_{state_key}")
        
        c3, c4 = st.columns(2)
        with c3:
            st.markdown("#### Cost Avoidance")
            st.markdown("<div style='height:40px; font-size:13px; color:gray;'>(Fuga de Custo - Ex: Evitou contratar, Multas)</div>", unsafe_allow_html=True)
            a_val = st.number_input("Valor (R$)", value=float(sav.get("avoidance", 0.0)), disabled=read_only, key=f"avoid_{state_key}")
            a_rac = st.text_area("Memorial de Cálculo (Como chegou no valor)", value=sav.get("avoidance_racional", ""), height=150, disabled=read_only, key=f"ar_{state_key}")
        with c4:
            st.markdown("#### Ganho de Faturamento")
            st.markdown("<div style='height:40px; font-size:13px; color:gray;'>(Novas Receitas - Ex: Aumento de Capacidade e Venda)</div>", unsafe_allow_html=True)
            f_val = st.number_input("Valor (R$)", value=float(sav.get("faturamento", 0.0)), disabled=read_only, key=f"fatu_{state_key}")
            f_rac = st.text_area("Memorial de Cálculo (Como chegou no valor)", value=sav.get("faturamento_racional", ""), height=150, disabled=read_only, key=f"fr_{state_key}")
            
        total = h_val + s_val + a_val + f_val
        st.markdown(f"**Total Saving Combinado (Estimativa da Aba):** `R$ {total:,.2f}`".replace(",", "X").replace(".", ",").replace("X", "."))
        
        notas = st.text_area("Notas Gerais / Justificativa Lógica de Negócio (Business Case)", value=sav.get("notas_gerais", project_state.get("charter", {}).get("benefits", "")), height=200, disabled=read_only)

        c1_b, c2_b = st.columns([1, 3])
        with c1_b:
            if st.button("💾 Salvar Memória de Cálculo", disabled=read_only, use_container_width=True):
                project_state[state_key] = {
                    "hard": h_val, "hard_racional": h_rac,
                    "soft": s_val, "soft_racional": s_rac,
                    "avoidance": a_val, "avoidance_racional": a_rac,
                    "faturamento": f_val, "faturamento_racional": f_rac,
                    "notas_gerais": notas
                }
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                
                payload = json.dumps(project_state[state_key], ensure_ascii=False)
                db.save_draft(pid, tool, {"text": payload})
                st.success("Cálculo e racional salvos com sucesso!")
                st.rerun()

    elif tool == "Matriz RACI":
        st.subheader("Matriz RACI (Papéis e Responsabilidades)")
        st.info("💡 Defina quem são as pessoas envolvidas em cada fase do seu projeto (DMAIC).")
        
        raci_data = project_state.get("raci", [])
        if not raci_data:
            raci_data = [{"Nome": "", "Posição / Cargo": "", "Definição": "", "Medição": "", "Análise": "", "Melhoria": "", "Controle": ""}]
            
        edited_raci = st.data_editor(
            raci_data,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Nome": st.column_config.TextColumn("Nome Regulamentar (ou Área)"),
                "Posição / Cargo": st.column_config.TextColumn("Posição / Cargo"),
                "Definição": st.column_config.SelectboxColumn("Definição", options=["R", "A", "C", "I", ""]),
                "Medição": st.column_config.SelectboxColumn("Medição", options=["R", "A", "C", "I", ""]),
                "Análise": st.column_config.SelectboxColumn("Análise", options=["R", "A", "C", "I", ""]),
                "Melhoria": st.column_config.SelectboxColumn("Melhoria", options=["R", "A", "C", "I", ""]),
                "Controle": st.column_config.SelectboxColumn("Controle", options=["R", "A", "C", "I", ""])
            },
            disabled=read_only
        )
        
        with st.expander("❔ Entenda o que significa R, A, C, I", expanded=True):
            st.markdown("""
            **Legenda da Matriz RACI:**
            - **[R] Responsible (Responsável):** Quem de fato executa a tarefa/atividade. Quem "põe a mão na massa".
            - **[A] Accountable (Aprovador/Autoridade):** Quem tem a palavra final e responde pelo resultado da etapa. (Para evitar paralisia decisória, o ideal é ter apenas 1 "A" por fase).
            - **[C] Consulted (Consultado):** Quem precisa ser consultado para dar opiniões técnicas, fornecer dados ou validar o que está sendo construído (Comunicação de via dupla).
            - **[I] Informed (Informado):** Quem apenas precisa receber comunicados sobre o andamento e decisões daquela etapa, mas sem gerência de voto (Comunicação de via única).
            """)
            
        st.markdown("<br>", unsafe_allow_html=True)
        cR1, cR2 = st.columns([1, 4])
        with cR1:
            if st.button("💾 Salvar Matriz", disabled=read_only, use_container_width=True):
                project_state["raci"] = edited_raci
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                db.save_draft(pid, tool, {"text": str(edited_raci)})
                st.success("Matriz RACI salva!")

    elif tool == "Fluxograma":
        st.subheader("Modelador de Fluxograma BPMN (As-Is / To-Be)")
        st.info("💡 Desenhe o processo arrastando Swimlanes (Raias), Tarefas, Decisões e Conectores da paleta do Bizagi-JS (BPMN.io) à esquerda.")
        
        # O Componente recebe espaço de tela grande (800px)
        xml_state = project_state.get("fluxograma_xml", "")
        
        if st_bpmn:
            # Renderiza o visual customizado
            new_xml = st_bpmn(xml=xml_state, height=750, key="bpmn_editor_instance")
            
            # Se a string XML retornou preenchida através de botões nativos do JS e for diferente do salvo
            if new_xml and new_xml != xml_state:
                project_state["fluxograma_xml"] = new_xml
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                
                # Salvamos draft text com length/status apenas
                db.save_draft(pid, tool, {"text": f"BPMN Model: {len(new_xml)} chars"})
        else:
            st.error("Componente BPMN editor não carregado. Contate o administrador do sistema.")

    else:
        st.info("Outras ferramentas (Ishikawa, etc.) estão na fila de atualização para a nuvem.")
        draft = db.load_draft(pid, tool) or {}
        draft_text = draft.get("text", "")
        new_text = st.text_area("Borrão da Ferramenta (Para Análise da IA):", value=draft_text, height=420, disabled=read_only)
        if st.button("💾 Salvar Rascunho", disabled=read_only):
            db.save_draft(pid, tool, {"text": new_text})
            st.success("Salvo!")

with coach_container:
    if tool in ["Matriz RACI", "Fluxograma"]:
        st.stop()
        
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
    target_sipoc = ""
    q_desc = ""
    
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
        elif tool == "SIPOC (por etapa)":
            st.info("💡 **Mapeamento Modular:** Diga qual parte do fluxo o Doutor Lean deve estruturar ativamente para você.")
            target_sipoc = st.radio("O que preencher automaticamente?", ["Etapas Mestre do Processo (P)", "Linhas de Entrada e Fornecedores (S/I)", "Linhas de Saídas e Clientes (O/C)"], disabled=read_only)

            if target_sipoc == "Etapas Mestre do Processo (P)":
                st.warning("⚠️ **Aviso de Sobrescrição:** A geração baseada em texto livre vai inicializar o tabuleiro do zero com novas Grandes Fases deduzidas, substituindo tudo atual.")
                q_desc = st.text_area("Descreva de forma simples como funciona o seu processo atual do início ao fim (Textão Livre):", disabled=read_only, height=100)
            elif target_sipoc == "Linhas de Entrada e Fornecedores (S/I)":
                st.info("💡 **Mapeamento de Esquerda:** A IA relerá as Etapas Centrais (P) que estão atualmente preenchidas e re-escreverá todos os Fornecedores e Entradas lógicas atreladas a elas.")
            else:
                st.info("💡 **Mapeamento de Direita:** A IA relerá as Etapas Centrais (P) que estão atualmente preenchidas e re-escreverá todas as Saídas e Clientes lógicas atreladas a elas.")
        elif tool in ["Saving Projetado", "Saving Realizado"]:
            st.info("💡 **Doutor Lean CFO:** Diga quais os ganhos imaginados neste projeto, e o Coach construirá um formato executivo guiando como precificar (e enquadrar em Hard/Soft) cada um deles.")
            
            # Garantir que a state session memorize as edições manuais
            if "coach_saving_desc" not in st.session_state:
                st.session_state["coach_saving_desc"] = project_state.get("charter", {}).get("benefits", "")
            
            def clear_saving_feedback():
                if "saving_coach_feedback" in st.session_state:
                    del st.session_state["saving_coach_feedback"]
                
            q_desc = st.text_area("Descreva os ganhos ou ideias (ou mantenha os importados do Project Charter da tela acima):", key="coach_saving_desc", height=250, disabled=read_only, on_change=clear_saving_feedback)
        elif tool == "Matriz de Indicadores":
            st.info("💡 **Geração Automática de Indicadores:** A IA analisará o problema do projeto e a natureza das etapas listadas (Processo) para sugerir preenchimentos para cada coluna.")
            st.warning("A IA apenas retornará dados preenchidos se detectar que a Tabela de Processos (no painel central) já possui Etapas (P) válidas.")
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

        # --- FLUXO ESPECIAL: Geração (Autocompletar) do SIPOC ---
        elif tool == "SIPOC (por etapa)" and mode_str == "generate":
            if target_sipoc == "Etapas Mestre do Processo (P)":
                if not q_desc.strip():
                    st.warning("Forneça pelo menos 1 frase ou passo-a-passo para a IA extrair a lógica macro!")
                else:
                    with st.spinner("Dedução Ativa: Mapeando macro etapas..."):
                        macro_etapas = suggest_sipoc_macro(project_state, q_desc)
                        new_sipoc = [{"P": m, "inputs": [{"S": "", "I": ""}], "outputs": [{"O": "", "C": ""}]} for m in macro_etapas]
                        if not new_sipoc:
                            st.error("Falha na geração das etapas lógicas. Tente reformular a descrição.")
                        else:
                            project_state["sipoc"] = new_sipoc
                            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                            st.session_state["ai_generated_warning"] = "✨ ⚠️ Etapas centrais do processo mapeadas! Agora preencha os lados ou peça pra IA completar."
                            st.rerun()

            elif target_sipoc == "Linhas de Entrada e Fornecedores (S/I)":
                with st.spinner("Análise Combinatória: Gerando entradas baseando-se nos nós centrais vigentes..."):
                    updated_sipoc = suggest_sipoc_io(project_state, "inputs")
                    project_state["sipoc"] = updated_sipoc
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.session_state["ai_generated_warning"] = "✨ ⚠️ Fornecedores e Entradas associados com sucesso aos blocos estruturais de processo da esquerda."
                    st.rerun()

            elif target_sipoc == "Linhas de Saídas e Clientes (O/C)":
                with st.spinner("Análise Combinatória: Gerando saídas baseando-se nos nós centrais vigentes..."):
                    updated_sipoc = suggest_sipoc_io(project_state, "outputs")
                    project_state["sipoc"] = updated_sipoc
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.session_state["ai_generated_warning"] = "✨ ⚠️ Saídas e Clientes resolvidos com sucesso nos blocos de direita. Finalize seu tabuleiro e salve."
                    st.rerun()

        # --- FLUXO ESPECIAL: Geração do Saving CFO ---
        elif tool in ["Saving Projetado", "Saving Realizado"] and mode_str == "generate":
            if not q_desc:
                st.warning("Eita! Você precisa descrever algum benefício preliminar ou ideia na caixa de texto pro CFO conseguir criar o modelo financeiro de conversão.")
            else:
                with st.spinner("O CFO Virtual está analisando as possibilidades de ganhos..."):
                    new_sav = suggest_saving_rationale(project_state, q_desc)
                    # Exibir apenas no rodapé da IA provisoriamente
                    st.session_state["saving_coach_feedback"] = new_sav
                    st.session_state["ai_generated_warning"] = "✨ ⚠️ Análise Financeira Concluída. Veja a classificação das oportunidades logo abaixo!"
                    st.rerun()

        # --- FLUXO ESPECIAL: Geração (Autocompletar) de Matriz de Indicadores ---
        elif tool == "Matriz de Indicadores" and mode_str == "generate":
            with st.spinner("Doutor Lean processando etapas e criando árvore de indicadores..."):
                new_matriz = suggest_matriz_indicadores(project_state)
                if not new_matriz:
                    st.error("Falha ao gerar indicadores. Certifique-se de que a coluna de Processos não está vazia.")
                else:
                    # Sobrescreve a matriz com a resposta
                    project_state["matriz_indicadores"] = new_matriz
                    db.save_draft(pid, tool, {"text": json.dumps(new_matriz, ensure_ascii=False)})
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.session_state["ai_generated_warning"] = "✨ ⚠️ Matriz preenchida com as métricas geradas pela IA. Releia os tópicos!"
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

    if st.session_state.get("saving_coach_feedback") and tool in ["Saving Projetado", "Saving Realizado"]:
        st.markdown("---")
        st.markdown("### 🏦 Classificação de Oportunidades do CFO Virtual")
        st.info("O Coach categorizou as suas ideias. Copie os racionais matemáticos que fizerem sentido e preencha nos blocos editáveis no topo desta página.")
        _sav = st.session_state["saving_coach_feedback"]
        cc1, cc2 = st.columns(2)
        with cc1:
            st.text_area("🔴 Sugestão Hard Saving", value=_sav.get("hard", ""), height=250, disabled=True, key="sav_h")
        with cc2:
            st.text_area("🟡 Sugestão Soft Saving", value=_sav.get("soft", ""), height=250, disabled=True, key="sav_s")
        
        cc3, cc4 = st.columns(2)
        with cc3:
            st.text_area("🟢 Sugestão Cost Avoidance", value=_sav.get("avoidance", ""), height=250, disabled=True, key="sav_a")
        with cc4:
            st.text_area("🔵 Sugestão de Faturamento", value=_sav.get("faturamento", ""), height=250, disabled=True, key="sav_f")

    st.markdown("---")
    st.markdown("### 📜 Memória de Sessões")
    recent = db.list_recent_sessions(pid, limit=4)
    if not recent:
        st.write("Sem sessões salvas.")
    else:
        for s in recent:
            with st.expander(f"{s['created_at'].strftime('%d/%m %H:%M')} · {s['tool']}"):
                st.json(s["coach"])
