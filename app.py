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
    suggest_matriz_indicadores,
    suggest_causa_efeito_impacto,
    suggest_xs_consolidados,
    suggest_plano_coleta
)

from coach_extensions import (
    suggest_ishikawa_eval,
    suggest_acao_5w2h
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
        tab_login, tab_reg, tab_forg = st.tabs(["Entrar", "Criar Conta", "Esqueci a Senha"])
        
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
            st.warning("O acesso é exclusivo para alunos matriculados usando um Código de Licença válido.")
            r_name = st.text_input("Nome Completo", key="r_name")
            r_email = st.text_input("E-mail Escolar/Corp", key="r_email")
            r_code = st.text_input("Código de Licença (Token)", key="r_code")
            u_reg = st.text_input("Novo Usuário (Login)", key="reg_u")
            p_reg = st.text_input("Nova Senha", type="password", key="reg_p")
            if st.button("Registrar Aluno", use_container_width=True):
                if u_reg and p_reg and r_name and r_email and r_code:
                    import db_auth
                    success, msg = db_auth.create_user_with_license(u_reg, p_reg, r_name, r_email, r_code)
                    if success:
                        st.success(msg + " Por favor, volte a tela de Entrar.")
                    else:
                        st.error(msg)
                else:
                    st.error("Todos os campos devem ser preenchidos.")
                    
        with tab_forg:
            st.info("Insira seu nome de usuário. Iremos notificar o Administrador para gerar uma nova credencial.")
            f_user = st.text_input("Usuário", key="forg_u")
            if st.button("Solicitar Reset", use_container_width=True):
                if f_user:
                    import db_auth
                    succ, msg = db_auth.request_password_reset(f_user)
                    st.success(msg) if succ else st.error(msg)



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
    
    col_out, col_pass = st.columns(2)
    with col_out:
        if st.button("Sair (Logout)", use_container_width=True):
            st.session_state.user = None
            st.session_state.active_project_id = None
            st.rerun()
    with col_pass:
        @st.dialog("Trocar Minha Senha")
        def change_password_dialog():
            np = st.text_input("Nova Senha", type="password")
            ncp = st.text_input("Confirme a Senha", type="password")
            if st.button("Atualizar"):
                if np and np == ncp:
                    import db_auth
                    if db_auth.change_password(USERNAME, np):
                        st.success("Senha atualizada!")
                    else:
                        st.error("Erro.")
                else:
                    st.error("As senhas não coincidem ou estão vazias.")
        
        if st.button("Trocar Senha", use_container_width=True):
            change_password_dialog()
            
    st.markdown("---")
    
    # Se o professor está dentro de um projeto, dar opção para ele voltar ao painel Dashboard
    if ROLE == "professor" and st.session_state.get("active_project_id"):
        if st.button("⬅️ Voltar ao Painel Admin", type="primary", use_container_width=True):
            st.session_state.active_project_id = None
            st.rerun()
        st.markdown("---")

    if ROLE == "professor":
        st.markdown("""
        <style>
        /* Corrigir contraste do selectbox no painel admin */
        div[data-baseweb="select"] > div {
            color: #000000 !important;
        }
        div[role="listbox"] ul li {
            color: #000000 !important;
        }
        </style>
        """, unsafe_allow_html=True)
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

def get_dmaic_metrics(p_state: dict) -> dict:
    def safe_get(p_data, key, subkey):
        d = p_data.get(key)
        if isinstance(d, dict): return d.get(subkey)
        return None

    # CHECKLIST MAPPING: Retorna (Nome Ferramenta, Preenchido boolean)
    checklist_d = [
        ("VOC/VOB", bool(safe_get(p_state, "voc_vob", "voc"))),
        ("Project Charter", bool(safe_get(p_state, "charter", "main_indicator") or safe_get(p_state, "charter", "problem"))),
        ("Matriz RACI", bool(p_state.get("raci"))),
        ("SIPOC (por etapa)", bool(p_state.get("sipoc"))), # SIPOC é uma lista direta
        ("Saving Projetado", bool(p_state.get("saving_projetado"))),
        ("Capabilidade (Baseline)", bool(p_state.get("cap_discrete_D - Capabilidade (Baseline)") or p_state.get("cap_chat_historico_D - Capabilidade (Baseline)")))
    ]
    
    checklist_m = [
        ("Fluxograma", bool(p_state.get("fluxograma_xml"))),
        ("Matriz de Indicadores", bool(p_state.get("matriz_indicadores"))),
        ("Repositório de Medições", bool(p_state.get("measurement_reports") or (p_state.get("metrics") and len(p_state.get("metrics")) > 0))),
        ("Causa & Efeito", bool(p_state.get("causa_efeito"))),
        ("Plano de Coleta de Dados", bool(p_state.get("planos_validacao"))),
        ("Quick Wins", bool(p_state.get("quick_wins"))),
        ("Ishikawa", bool(p_state.get("ishikawas")))
    ]

    checklist_a = [
        ("5 Porquês", bool(p_state.get("cinco_pqs"))),
        ("Plano de Validação de Causas", bool(p_state.get("planos_validacao")))
    ]

    checklist_i = [
        ("Plano de Soluções", bool(p_state.get("planos_solucoes"))), # Chave correta é planos_solucoes
        ("Plano de Ação", bool(p_state.get("planos_acao"))), # Chave interna correta
        ("Capabilidade (Melhoria)", bool(p_state.get("cap_discrete_I - Capabilidade (Melhoria)") or p_state.get("cap_chat_historico_I - Capabilidade (Melhoria)")))
    ]

    # Correção: O Lean Copilot salva plano_acao sob `planos_acao` com um ID
    planos_acao_raw = p_state.get("planos_acao", [])
    has_acao = False
    total_acoes, concluidas = 0, 0
    if isinstance(planos_acao_raw, list):
        for pa in planos_acao_raw:
            if isinstance(pa, dict) and pa.get("rows"):
                has_acao = True
                for row in pa["rows"]:
                    total_acoes += 1
                    if row.get("status") == "Concluído": concluidas += 1
    checklist_i[1] = ("Plano de Ação", has_acao)

    checklist_c = [
        ("Saving Realizado", bool(safe_get(p_state, "saving_realizado", "hard"))),
        ("Plano de Controle", bool(p_state.get("plano_controle") or p_state.get("control_plan")))
    ]
    
    # % de preenchimento
    def calc_perc(chk_list):
        if not chk_list: return 0
        return int(sum(1 for _, v in chk_list if v) / len(chk_list) * 100)

    perc_d = calc_perc(checklist_d)
    perc_m = calc_perc(checklist_m)
    perc_a = calc_perc(checklist_a)
    perc_i = calc_perc(checklist_i)
    perc_c = calc_perc(checklist_c)

    # Global Tools (Contando únicos validos de D+M+A+I+C)
    all_chks = checklist_d + checklist_m + checklist_a + checklist_i + checklist_c
    total_tools = len(all_chks)
    completed_tools = sum(1 for _, v in all_chks if v)
    total_perc = int((completed_tools / total_tools) * 100) if total_tools > 0 else 0
    
    # Progresso Ação
    action_perc = int((concluidas / total_acoes) * 100) if total_acoes > 0 else 0

    return {
        "global_perc": total_perc,
        "d_perc": perc_d, "m_perc": perc_m, "a_perc": perc_a, "i_perc": perc_i, "c_perc": perc_c,
        "action_perc": action_perc,
        "action_stats": (total_acoes, concluidas),
        "checklist": {
            "Define": checklist_d,
            "Measure": checklist_m,
            "Analyze": checklist_a,
            "Improve": checklist_i,
            "Control": checklist_c
        }
    }

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
        "causa_efeito": [],
        "ishikawas": [],
        "cinco_pqs": [],
        "planos_validacao": [],
        "plano_solucoes": [],
        "plano_acao": [],
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
if ROLE == "aluno":
    if projects:
        st.sidebar.caption("Seus Projetos")
        for p in projects:
            if st.sidebar.button(f"📁 {p['name']}", key=f"open_{p['project_id']}"):
                st.session_state.active_project_id = p["project_id"]
                st.rerun()
    else:
        st.sidebar.info("Crie um projeto para começar.")
else:
    st.sidebar.caption("Painel do Professor - Área Corporativa")

pid = st.session_state.get("active_project_id")
if not pid:
    if ROLE == "professor":
        st.title("Gestão Corporativa & B2B")
        t_cli, t_proj, t_req, t_acesso = st.tabs(["🏢 Clientes & Licenças", "🚀 Evolução dos Projetos", "🔐 Solicitações de Senha", "📂 Acesso a Projetos"])
        
        with t_cli:
            st.subheader("Cadastro de Clientes e Geração de Códigos")
            cc1, cc2 = st.columns([1, 1])
            
            with cc1:
                with st.form("new_client_form", clear_on_submit=True):
                    st.markdown("**Novo Cliente**")
                    nc_name = st.text_input("Nome da Empresa/Cliente")
                    nc_submit = st.form_submit_button("Criar Cliente")
                    if nc_submit and nc_name:
                        import db
                        session = db.SessionLocal()
                        try:
                            if session.query(db.Client).filter(db.Client.name == nc_name).first():
                                st.error("Cliente já existe.")
                            else:
                                c = db.Client(name=nc_name)
                                session.add(c)
                                session.commit()
                                st.success("Cliente criado!")
                        except Exception as e:
                            st.error(f"Erro: {e}")
                        finally:
                            session.close()

            with cc2:
                with st.form("new_lic_form", clear_on_submit=True):
                    st.markdown("**Gerar Licenças por Cliente**")
                    import db
                    session = db.SessionLocal()
                    try:
                        all_c = session.query(db.Client).all()
                        c_dict = {c.name: c.id for c in all_c}
                        
                        sel_c = st.selectbox("Selecione o Cliente", list(c_dict.keys()) if c_dict else ["Nenhum"])
                        qtd_lic = st.number_input("Quantidade de Códigos", min_value=1, max_value=500, value=1)
                        nl_submit = st.form_submit_button("Gerar Códigos")
                        
                        if nl_submit and sel_c != "Nenhum":
                            import uuid
                            cid = c_dict[sel_c]
                            new_codes = []
                            for _ in range(qtd_lic):
                                lcode = f"{sel_c[:3].upper()}-{str(uuid.uuid4())[:6].upper()}"
                                session.add(db.LicenseKey(code=lcode, client_id=cid))
                                new_codes.append(lcode)
                            session.commit()
                            st.success(f"{qtd_lic} código(s) gerados com sucesso!")
                            with st.expander("Ver códigos novos", expanded=True):
                                st.code("\\n".join(new_codes))
                    finally:
                        session.close()
                        
            st.divider()
            st.subheader("Licenças Existentes")
            session = db.SessionLocal()
            try:
                # Joining licenses with clients
                raw_data = session.query(db.LicenseKey, db.Client.name).join(db.Client).all()
                if raw_data:
                    lic_df = pd.DataFrame([{
                        "Cliente": r[1],
                        "Código": r[0].code,
                        "Status": "Usado" if r[0].is_used else "Livre",
                        "Usado Por": r[0].used_by or "-",
                        "Criado Em": r[0].created_at
                    } for r in raw_data])
                    fil_c = st.selectbox("Filtrar Tabela por Cliente", ["Todos"] + list(c_dict.keys()) if c_dict else ["Todos"])
                    if fil_c != "Todos":
                        lic_df = lic_df[lic_df["Cliente"] == fil_c]
                    st.dataframe(lic_df, use_container_width=True)
                else:
                    st.info("Nenhuma licença gerada.")
            finally:
                session.close()

        with t_proj:
            st.subheader("Métricas Globais de Projetos")
            st.info("Aqui você acompanha o % de Evolução (Ferramentas preenchidas) e o Status do Cronograma.")
            
            session = db.SessionLocal()
            try:
                # Listar todos os usuários da base e seus clientes
                uv_data = session.query(db.User, db.Client.name).outerjoin(db.Client, db.User.client_id == db.Client.id).all()
                u_map = {r[0].username: r[1] or "Sem Cliente" for r in uv_data}
            finally:
                session.close()
                
            all_ps = db.list_projects("professor", "admin") # get all
            if all_ps:
                metrics_data = []
                for p in all_ps:
                    p_state = db.get_project_state(p["project_id"])
                    
                    dmaic_metrics = get_dmaic_metrics(p_state)
                    total_score = dmaic_metrics["global_perc"]
                    action_exec = dmaic_metrics["action_perc"]
                    
                    # Status Calculation
                    status_prazo = "Dentro do Prazo"
                    from datetime import datetime
                    hoje = datetime.utcnow().date()
                    
                    # Tenta ler as semanas (Legado: deixaremos estático por ora se on track, para MVP)
                    tw = p_state.get("charter", {}).get("timeline_weeks", {})
                    
                    c_name = u_map.get(p["user_id"], "Sem Cliente")
                    metrics_data.append({
                        "Cliente": c_name,
                        "Aluno (Dono)": p["user_id"],
                        "Evolução %": total_score,
                        "Define %": dmaic_metrics["d_perc"],
                        "Measure %": dmaic_metrics["m_perc"],
                        "Analyze %": dmaic_metrics["a_perc"],
                        "Improve %": dmaic_metrics["i_perc"],
                        "Control %": dmaic_metrics["c_perc"],
                        "Ações Realizadas %": action_exec,
                        "Status Prazo": status_prazo,
                        "Projeto": p["name"],
                    })
                    
                df_met = pd.DataFrame(metrics_data)
                
                cf = st.selectbox("Visualizar qual Cliente?", ["Todos"] + list(c_dict.keys()) if c_dict else ["Todos"])
                if cf != "Todos":
                    df_met = df_met[df_met["Cliente"] == cf]
                    
                st.dataframe(
                    df_met,
                    use_container_width=True,
                    column_config={
                        "Evolução %": st.column_config.ProgressColumn("Evolução %", help="Global Ferramentas", format="%f%%", min_value=0, max_value=100),
                        "Define %": st.column_config.ProgressColumn("Define %", format="%f%%", min_value=0, max_value=100),
                        "Measure %": st.column_config.ProgressColumn("Measure %", format="%f%%", min_value=0, max_value=100),
                        "Analyze %": st.column_config.ProgressColumn("Analyze %", format="%f%%", min_value=0, max_value=100),
                        "Improve %": st.column_config.ProgressColumn("Improve %", format="%f%%", min_value=0, max_value=100),
                        "Control %": st.column_config.ProgressColumn("Control %", format="%f%%", min_value=0, max_value=100),
                        "Ações Realizadas %": st.column_config.ProgressColumn("Ações Realizadas %", format="%f%%", min_value=0, max_value=100)
                    }
                )
            else:
                st.info("Nenhum projeto foi criado ainda por estudantes.")
                
        with t_req:
            st.subheader("Solicitações de Nova Senha")
            session = db.SessionLocal()
            try:
                users_req = session.query(db.User).filter(db.User.password_reset_req == True).all()
                if users_req:
                    for ur in users_req:
                        with st.expander(f"🔴 Reset solicitado por: {ur.username} ({ur.full_name})", expanded=True):
                            new_p = st.text_input(f"Digitar nova senha para {ur.username}", type="password", key=f"r_{ur.username}")
                            if st.button("Gravar Alteração e Limpar Pedido", key=f"b_{ur.username}"):
                                import db_auth
                                db_auth.change_password(ur.username, new_p)
                                st.success("Atualizado!")
                                st.rerun()
                else:
                    st.success("Tudo tranquilo! Nenhum aluno reportou esquecimento de senha.")
            finally:
                session.close()
                
        with t_acesso:
            st.subheader("Entrar no Projeto como 'Aluno'")
            
            import db
            session = db.SessionLocal()
            try:
                # Carregar usuários, clientes e montar mapeamento
                users = session.query(db.User).all()
                clients = session.query(db.Client).all()
                
                cl_dict = {c.id: c.name for c in clients}
                user_client_name = {u.username: cl_dict.get(u.client_id, "Sem Cliente") for u in users}
                
                # Lista de clientes válidos que possuem projetos
                projetos_prof = get_project_list()
                if not projetos_prof:
                    st.info("Nenhum projeto de aluno no sistema.")
                else:
                    # Enriquece projetos com informações do DB (leader) e cria map
                    projetos_ricos = []
                    clientes_existentes = set()
                    
                    for p in projetos_prof:
                        p_state = db.get_project_state(p["project_id"])
                        leader_name = p_state.get("leader", "Sem líder") if p_state else "Sem líder"
                        cliente_do_aluno = user_client_name.get(p["user_id"], "Sem Cliente")
                        
                        clientes_existentes.add(cliente_do_aluno)
                        
                        projetos_ricos.append({
                            "id": p["project_id"],
                            "name": p["name"],
                            "user": p["user_id"],
                            "client": cliente_do_aluno,
                            "leader": leader_name,
                            "label": f"[{p['name']}] Líder: {leader_name} | Aluno Dono: {p['user_id']}"
                        })
                    
                    # Interface 1: Escolher Cliente
                    sel_cliente = st.selectbox("1. Filtrar por Cliente", ["Todos os Clientes"] + sorted(list(clientes_existentes)))
                    
                    # Filtrar projetos
                    projetos_filtrados = projetos_ricos if sel_cliente == "Todos os Clientes" else [pr for pr in projetos_ricos if pr["client"] == sel_cliente]
                    
                    if not projetos_filtrados:
                        st.info("Nenhum projeto neste cliente.")
                    else:
                        mapa_lbl_id = {pr["label"]: pr["id"] for pr in projetos_filtrados}
                        # Interface 2: Escolher Projeto
                        sel_projeto_lbl = st.selectbox("2. Selecione o Projeto", list(mapa_lbl_id.keys()))
                        
                        if st.button("🚀 Acessar o Projeto (Visão do Aluno)", type="primary"):
                            st.session_state.active_project_id = mapa_lbl_id[sel_projeto_lbl]
                            st.rerun()
            finally:
                session.close()

    else:
        st.title("Bem-vindo ao Lean Copilot")
        st.write("Abra um projeto no menu esquerdo para começar a trabalhar.")
        
    st.stop()

project_state = db.get_project_state(pid)
if not project_state:
    st.error("Projeto não encontrado.")
    st.stop()

# --- Permissions Logic ---
is_owner = (project_state.get("user_id") == USERNAME)
allow_edit = project_state.get("allow_teacher_edit", True)
allow_view = project_state.get("allow_teacher_view", True)

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
        c_v, c_e = st.columns(2)
        with c_v:
            new_permit_view = st.toggle("Permitir visualização do Professor", value=allow_view)
        with c_e:
            new_permit_edit = st.toggle("Permitir edições do Professor", value=allow_edit, disabled=not new_permit_view)
            
        if new_permit_edit != allow_edit or new_permit_view != allow_view:
            project_state["allow_teacher_edit"] = new_permit_edit
            project_state["allow_teacher_view"] = new_permit_view
            db.upsert_project(pid, project_state['name'], project_state, USERNAME, new_permit_edit, new_permit_view)
            st.success("Permissões atualizadas!")
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

# --- SINCRONIZAÇÃO DE ESTADO (Background State Sync) ---
# Garante que edições manuais em tabelas dinâmicas não sejam perdidas ao trocar de ferramentas
# ou ao realizar importações em outras telas, capturando os valores atuais do st.session_state.
def sync_dynamic_tables():
    updated_ce = False
    updated_pl = False
    updated_ind = False
    updated_pa = False
    updated_qw = False

    # 1. Matriz Causa & Efeito
    if "causa_efeito" in project_state:
        ce_data = project_state["causa_efeito"]
        ce_id = project_state.get("causa_efeito_id", 0)
        for i, row in enumerate(ce_data):
            k_ind = f"ce_ind_{i}_{ce_id}"
            k_imp = f"ce_imp_{i}_{ce_id}"
            k_esf = f"ce_esf_{i}_{ce_id}"
            if k_ind in st.session_state:
                row["indicador"] = st.session_state[k_ind]
                updated_ce = True
            if k_imp in st.session_state:
                row["impacto"] = int(st.session_state[k_imp])
                updated_ce = True
            if k_esf in st.session_state:
                row["esforco"] = int(st.session_state[k_esf])
                updated_ce = True
        if updated_ce:
            project_state["causa_efeito"] = ce_data

    # 2. Plano de Coleta de Dados
    if "plano_coleta" in project_state:
        pl_data = project_state["plano_coleta"]
        pl_id = project_state.get("plano_id", 0)
        updated_pl = False
        for i, row in enumerate(pl_data):
            k_def = f"plano_def_{i}_{pl_id}"
            k_ind = f"plano_ind_{i}_{pl_id}"
            k_src = f"plano_src_{i}_{pl_id}"
            k_amo = f"plano_amo_{i}_{pl_id}"
            k_res = f"plano_res_{i}_{pl_id}"
            k_qnd = f"plano_qnd_{i}_{pl_id}"
            k_com = f"plano_com_{i}_{pl_id}"
            k_out = f"plano_out_{i}_{pl_id}"
            k_uso = f"plano_uso_{i}_{pl_id}"
            k_viz = f"plano_viz_{i}_{pl_id}"
            
            mapping = {
                k_def: "Definição", k_ind: "Indicador", k_src: "Fonte", k_amo: "Amostra", 
                k_res: "Responsável", k_qnd: "Quando", k_com: "Como", k_out: "Outros", 
                k_uso: "Uso", k_viz: "Mostrar"
            }
            for k, field in mapping.items():
                if k in st.session_state:
                    row[field] = st.session_state[k]
                    updated_pl = True
        if updated_pl:
            project_state["plano_coleta"] = pl_data

    # 3. Matriz de Indicadores
    if "matriz_indicadores" in project_state:
        ind_data = project_state["matriz_indicadores"]
        mat_id = project_state.get("matriz_id", 0)
        updated_ind = False
        cols_map = {
            "mat_p": "Processo", "mat_q": "Quantidade/Volume", "mat_qr": "Quantidade/Recursos",
            "mat_w": "Quantidade em processamento (WIP)", "mat_t": "Tempo (Lead/Cycle Time)",
            "mat_pc": "Percentual (%)", "mat_qu": "Qualidade (Erro/NPS)", "mat_f": "Financeiro (R$)"
        }
        for i, row in enumerate(ind_data):
            for k_prefix, field in cols_map.items():
                k = f"{k_prefix}_{i}_{mat_id}"
                if k in st.session_state:
                    row[field] = st.session_state[k]
                    updated_ind = True
        if updated_ind:
            project_state["matriz_indicadores"] = ind_data

    # 4. Plano de Ação 5W2H
    updated_pa = False
    if "planos_acao" in project_state and project_state["planos_acao"]:
        planos_acao = project_state["planos_acao"]
        active_plano = planos_acao[0]
        rows = active_plano.get("rows", [])
        for row in rows:
            rid = row.get("row_id")
            v = row.get("version_ai", 0)
            k_acao = f"paa_acao_{rid}_{v}"
            k_onde = f"paa_onde_{rid}"
            k_inip = f"paa_inip_{rid}"
            k_fimp = f"paa_fimp_{rid}"
            k_inir = f"paa_inir_{rid}"
            k_fimr = f"paa_fimr_{rid}"
            k_quem = f"paa_quem_{rid}"
            k_stat = f"paa_stat_{rid}"

            mapping_pa = {
                k_acao: "acao", k_onde: "onde", k_inip: "ini_prev", k_fimp: "fim_prev",
                k_inir: "ini_real", k_fimr: "fim_real", k_quem: "quem", k_stat: "status"
            }
            for k, field in mapping_pa.items():
                if k in st.session_state:
                    row[field] = st.session_state[k]
                    updated_pa = True

    # 5. Quick Wins
    updated_qw = False
    if "quick_wins" in project_state and project_state["quick_wins"]:
        qw_data = project_state["quick_wins"]
        active_qw = qw_data[0]
        rows = active_qw.get("rows", [])
        for row in rows:
            rid = row.get("row_id")
            v = row.get("version_ai", 0)
            
            # Mapeamento para Quick Wins (qw_ e qwa_)
            k_acao = f"qwa_acao_{rid}_{v}"
            k_onde = f"qwa_onde_{rid}"
            k_inip = f"qwa_inip_{rid}"
            k_fimp = f"qwa_fimp_{rid}"
            k_inir = f"qwa_inir_{rid}"
            k_fimr = f"qwa_fimr_{rid}"
            k_quem = f"qwa_quem_{rid}"
            k_stat = f"qwa_stat_{rid}"
            
            # Campos de texto livre (causa/solucao)
            k_causa = f"qw_causa_{rid}"
            k_sol = f"qw_sol_{rid}"

            mapping_qw = {
                k_acao: "acao", k_onde: "onde", k_inip: "ini_prev", k_fimp: "fim_prev",
                k_inir: "ini_real", k_fimr: "fim_real", k_quem: "quem", k_stat: "status",
                k_causa: "causa", k_sol: "solucao"
            }
            for k, field in mapping_qw.items():
                if k in st.session_state:
                    row[field] = st.session_state[k]
                    updated_qw = True

    # --- SALVAMENTO AUTOMÁTICO NA SINCRONIZAÇÃO ---
    if updated_ce or updated_pl or updated_ind or updated_pa or updated_qw:
        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])

if not read_only:
    sync_dynamic_tables()

with tool_container:
    if tool == "Capa do Projeto":
        st.subheader("Capa do Projeto")
        st.markdown("Bem-vindo! Documente a identidade oficial da sua iniciativa de melhoria.")
        
        # --- Lógica do KPI do Estudante (Dashboard DMAIC) ---
        d_metrics = get_dmaic_metrics(project_state)
        
        st.markdown("#### 🎯 Dashboard DMAIC")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric(label="Ferramentas (Global)", value=f"{d_metrics['global_perc']}%")
        with c2:
            st.metric(label="Execução do Plano de Ação", value=f"{d_metrics['action_perc']}%")
        with c3:
            s_acoes = d_metrics['action_stats']
            st.metric(label="Ações Concluídas", value=f"{s_acoes[1]} / {s_acoes[0]}")
            
        st.markdown("---")
        # Barras de Progresso por Fase
        st.markdown("**Evolução por Fase**")
        pcol1, pcol2, pcol3, pcol4, pcol5 = st.columns(5)
        def draw_phase(col, phase_name, perc):
            with col:
                st.caption(f"**{phase_name}** ({perc}%)")
                st.progress(perc / 100.0)
                
        draw_phase(pcol1, "Define", d_metrics["d_perc"])
        draw_phase(pcol2, "Measure", d_metrics["m_perc"])
        draw_phase(pcol3, "Analyze", d_metrics["a_perc"])
        draw_phase(pcol4, "Improve", d_metrics["i_perc"])
        draw_phase(pcol5, "Control", d_metrics["c_perc"])
        
        st.write("")
        with st.expander("Ver Checklist Completo de Ferramentas"):
            for phase, items in d_metrics["checklist"].items():
                st.markdown(f"**{phase}**")
                for tool_name, is_checked in items:
                    icon = "✅" if is_checked else "⚪"
                    st.markdown(f"- {icon} {tool_name}")
                st.divider()
        
        st.divider()
        
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


    elif tool == "D - VOC/VOB":
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

    elif tool == "D - Project Charter":
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

    elif tool == "D - SIPOC (por etapa)":
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

    elif tool == "M - Matriz de Indicadores":
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
                            "Quantidade/Recursos": "",
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
                    project_state["matriz_id"] = project_state.get("matriz_id", 0) + 1
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.success("Etapas importadas com sucesso do SIPOC!")
                    st.rerun()

        if not indicadores_data:
            indicadores_data = [{
                "Processo": "",
                "Quantidade/Volume": "",
                "Quantidade/Recursos": "",
                "Quantidade em processamento (WIP)": "",
                "Tempo (Lead/Cycle Time)": "",
                "Percentual (%)": "",
                "Qualidade (Erro/NPS)": "",
                "Financeiro (R$)": ""
            }]
            
        st.markdown(
            '<style>'
            '[data-testid="stTextArea"] textarea { font-size: 13px !important; line-height: 1.3 !important; resize: vertical !important; }'
            '[data-testid="column"] { padding: 0 4px !important; } /* Reduz espaço entre colunas */'
            'div[data-testid="stHorizontalBlock"] { min-width: 1400px !important; } /* Força barra de rolagem horizontal se tela menor */'
            '</style>'
            '<div style="background-color: #001C59; color: white; padding: 10px; border-radius: 6px; min-width: 1400px; margin-bottom: -10px;">'
            '<div style="display: flex;">'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>Processo</b></div>'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>Quantidade / Volume</b></div>'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>Quantidade / Recursos</b></div>'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>WIP</b></div>'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>Tempo</b></div>'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>%</b></div>'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>Qualidade</b></div>'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>Financeiro</b></div>'
            '<div style="flex: 0.4; padding: 0 5px; font-size: 0.85em;"><b>Ação</b></div>'
            '</div></div><br>', 
            unsafe_allow_html=True
        )

        mat_id = project_state.get("matriz_id", 0)
        out_rows = []
        
        for i, row in enumerate(indicadores_data):
            c1, c2, c2b, c3, c4, c5, c6, c7, c8 = st.columns([1, 1, 1, 1, 1, 1, 1, 1, 0.4])
            
            p_txt  = str(row.get("Processo", ""))
            q_txt  = str(row.get("Quantidade/Volume", ""))
            qr_txt = str(row.get("Quantidade/Recursos", ""))
            w_txt  = str(row.get("Quantidade em processamento (WIP)", ""))
            t_txt  = str(row.get("Tempo (Lead/Cycle Time)", ""))
            pc_txt = str(row.get("Percentual (%)", ""))
            qu_txt = str(row.get("Qualidade (Erro/NPS)", ""))
            f_txt  = str(row.get("Financeiro (R$)", ""))
            
            altura_sincronizada = 140 
            
            v1 = c1.text_area("p", value=p_txt, key=f"mat_p_{i}_{mat_id}", height=altura_sincronizada, label_visibility="collapsed", disabled=read_only)
            v2 = c2.text_area("q", value=q_txt, key=f"mat_q_{i}_{mat_id}", height=altura_sincronizada, label_visibility="collapsed", disabled=read_only)
            v2b = c2b.text_area("qr", value=qr_txt, key=f"mat_qr_{i}_{mat_id}", height=altura_sincronizada, label_visibility="collapsed", disabled=read_only)
            v3 = c3.text_area("w", value=w_txt, key=f"mat_w_{i}_{mat_id}", height=altura_sincronizada, label_visibility="collapsed", disabled=read_only)
            v4 = c4.text_area("t", value=t_txt, key=f"mat_t_{i}_{mat_id}", height=altura_sincronizada, label_visibility="collapsed", disabled=read_only)
            v5 = c5.text_area("pc", value=pc_txt, key=f"mat_pc_{i}_{mat_id}", height=altura_sincronizada, label_visibility="collapsed", disabled=read_only)
            v6 = c6.text_area("qu", value=qu_txt, key=f"mat_qu_{i}_{mat_id}", height=altura_sincronizada, label_visibility="collapsed", disabled=read_only)
            v7 = c7.text_area("f", value=f_txt, key=f"mat_f_{i}_{mat_id}", height=altura_sincronizada, label_visibility="collapsed", disabled=read_only)
            
            with c8:
                st.markdown("<div style='height: 45px;'></div>", unsafe_allow_html=True)
                if len(indicadores_data) > 1 and not read_only:
                    # Delete current row
                    if st.button("🗑️", key=f"mat_del_{i}_{mat_id}", help="Apagar esta linha"):
                        nova_tabela = list(indicadores_data)
                        nova_tabela.pop(i)
                        project_state["matriz_indicadores"] = nova_tabela
                        project_state["matriz_id"] = mat_id + 1
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.rerun()
                    # Add new row below current row
                    if st.button("➕", key=f"mat_add_below_{i}_{mat_id}", help="Adicionar linha abaixo"):
                        nova_tabela = list(indicadores_data)
                        nova_tabela.insert(i + 1, {
                            "Processo": "",
                            "Quantidade/Volume": "",
                            "Quantidade/Recursos": "",
                            "Quantidade em processamento (WIP)": "",
                            "Tempo (Lead/Cycle Time)": "",
                            "Percentual (%)": "",
                            "Qualidade (Erro/NPS)": "",
                            "Financeiro (R$)": ""
                        })
                        project_state["matriz_indicadores"] = nova_tabela
                        project_state["matriz_id"] = mat_id + 1
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.rerun()

            out_rows.append({
                "Processo": v1,
                "Quantidade/Volume": v2,
                "Quantidade/Recursos": v2b,
                "Quantidade em processamento (WIP)": v3,
                "Tempo (Lead/Cycle Time)": v4,
                "Percentual (%)": v5,
                "Qualidade (Erro/NPS)": v6,
                "Financeiro (R$)": v7
            })

        if not read_only:
            b1, b3, _ = st.columns([1.5, 1.5, 4])
            with b1:
                if st.button("➕ Adicionar Linha", key="btn_add_matriz", use_container_width=True):
                    out_rows.append({
                        "Processo": "", "Quantidade/Volume": "", "Quantidade/Recursos": "", "Quantidade em processamento (WIP)": "",
                        "Tempo (Lead/Cycle Time)": "", "Percentual (%)": "", "Qualidade (Erro/NPS)": "", "Financeiro (R$)": ""
                    })
                    project_state["matriz_indicadores"] = out_rows
                    project_state["matriz_id"] = mat_id + 1
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.rerun()
            with b3:
                if st.button("🚨 Apagar Tabela", key="btn_clear_matriz", use_container_width=True):
                    out_rows = [{
                        "Processo": "", "Quantidade/Volume": "", "Quantidade/Recursos": "", "Quantidade em processamento (WIP)": "",
                        "Tempo (Lead/Cycle Time)": "", "Percentual (%)": "", "Qualidade (Erro/NPS)": "", "Financeiro (R$)": ""
                    }]
                    project_state["matriz_indicadores"] = out_rows
                    project_state["matriz_id"] = mat_id + 1
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.rerun()
                        
        edited_ind = out_rows
        # Sincroniza em memória (transiente) para que o Coach IA consiga ler o que acabou de ser digitado sem precisar salvar no BD
        project_state["matriz_indicadores"] = edited_ind
        
        # Gerar o texto a partir do formulário p/ análise da IA
        new_text = "Matriz de Indicadores:\n" + json.dumps(edited_ind, ensure_ascii=False)

        
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("💾 Salvar Matriz", disabled=read_only, use_container_width=True):
                project_state["matriz_indicadores"] = edited_ind
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                db.save_draft(pid, tool, {"text": new_text})
                st.success("Matriz de Indicadores salva!")

    elif tool == "M - Causa & Efeito - Esforço Impacto":
        st.subheader("📊 Causa & Efeito — Esforço × Impacto")
        st.info("💡 Liste os principais X's (causas) do problema. Pontue o Impacto [0-100] e o Esforço [0-100] de cada X. O Dr. Lean (abaixo, no Coach IA) gera uma lista consolidada automaticamente. O gráfico será atualizado automaticamente.")

        causa_data = project_state.get("causa_efeito", [])
        ce_id = project_state.get("causa_efeito_id", 0)

        if not causa_data:
            causa_data = [{"indicador": "", "impacto": 0, "esforco": 0, "justificativa": ""}]

        # --- Header da tabela ---
        st.markdown(
            '<style>'
            '#ce_table_wrap [data-testid="column"] { padding: 0 1px !important; gap: 0 !important; }'
            '#ce_table_wrap button[kind="secondary"] { padding: 2px 4px !important; font-size: 0.72em !important; min-height: 24px !important; height: 24px !important; line-height: 1 !important; }'
            '#ce_table_wrap [data-testid="stNumberInput"] input { font-size: 0.80em !important; padding: 4px 4px !important; }'
            '</style>'
            '<div id="ce_table_wrap">'
            '<div style="background-color: #001C59; color: white; padding: 6px 8px; border-radius: 6px; margin-bottom: 2px;">'
            '<div style="display: flex; align-items: center;">'
            '<div style="width: 36px; font-size: 0.78em;"><b>#</b></div>'
            '<div style="flex: 5; font-size: 0.78em; padding: 0 2px;"><b>Indicador / Causa (X)</b></div>'
            '<div style="width: 62px; font-size: 0.78em; text-align: center;"><b>Impacto<br>[0-100]</b></div>'
            '<div style="width: 62px; font-size: 0.78em; text-align: center;"><b>Esforço<br>[0-100]</b></div>'
            '<div style="flex: 2.5; font-size: 0.78em; padding: 0 2px;"><b>Justificativa IA</b></div>'
            '<div style="width: 44px; font-size: 0.78em; text-align: center;"><b>×/+</b></div>'
            '</div></div>',
            unsafe_allow_html=True
        )

        out_causas = []
        for i, row in enumerate(causa_data):
            label = f"X{i+1}"
            c_lbl, c_ind, c_imp, c_esf, c_just, c_act = st.columns([0.33, 5, 0.62, 0.62, 2.5, 0.42])

            c_lbl.markdown(f"<div style='padding-top:10px; font-weight:bold; color:#001C59;'>{label}</div>", unsafe_allow_html=True)

            # Retrocompatibilidade: se vier no formato antigo com campos "causa" ou "etapa+indicador", unificar
            indicador_val = str(row.get("indicador", row.get("causa", "")))
            # Se tinha etapa preenchida e indicador vazio (formato antigo), combina ambos
            etapa_old = str(row.get("etapa", "")).strip()
            if etapa_old and not indicador_val.strip():
                indicador_val = etapa_old
            elif etapa_old and indicador_val.strip() and etapa_old not in indicador_val:
                indicador_val = f"{etapa_old} — {indicador_val}"

            v_ind = c_ind.text_area(
                "ind", value=indicador_val,
                key=f"ce_ind_{i}_{ce_id}", height=80,
                label_visibility="collapsed", disabled=read_only
            )

            imp_raw = int(row.get("impacto", 0) or 0)
            esf_raw = int(row.get("esforco", 0) or 0)

            v_imp = c_imp.number_input(
                "imp", min_value=0, max_value=100, step=1,
                value=max(0, min(100, imp_raw)),
                key=f"ce_imp_{i}_{ce_id}", label_visibility="collapsed", disabled=read_only
            )
            v_esf = c_esf.number_input(
                "esf", min_value=0, max_value=100, step=1,
                value=max(0, min(100, esf_raw)),
                key=f"ce_esf_{i}_{ce_id}", label_visibility="collapsed", disabled=read_only
            )
            v_just = c_just.text_area(
                "just", value=str(row.get("justificativa", "")),
                key=f"ce_just_{i}_{ce_id}", height=80,
                label_visibility="collapsed", disabled=True
            )

            with c_act:
                if not read_only:
                    # Botoes minúsculos lado a lado
                    ba, bb = st.columns(2)
                    if ba.button("×", key=f"ce_del_{i}_{ce_id}", help="Apagar esta linha", use_container_width=True):
                        nova = list(causa_data)
                        nova.pop(i)
                        project_state["causa_efeito"] = nova
                        project_state["causa_efeito_id"] = ce_id + 1
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.rerun()
                    if bb.button("+", key=f"ce_add_{i}_{ce_id}", help="Inserir linha abaixo", use_container_width=True):
                        nova = list(causa_data)
                        nova.insert(i + 1, {"indicador": "", "impacto": 0.0, "esforco": 0.0, "justificativa": ""})
                        project_state["causa_efeito"] = nova
                        project_state["causa_efeito_id"] = ce_id + 1
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.rerun()

            out_causas.append({
                "indicador": v_ind,
                "impacto": int(v_imp),
                "esforco": int(v_esf),
                "justificativa": str(row.get("justificativa", ""))
            })

        # --- Botões de controle da tabela ---
        if not read_only:
            ba1, ba2, _ = st.columns([1.5, 1.5, 5])
            with ba1:
                if st.button("➕ Adicionar Linha", key="ce_add_bottom", use_container_width=True):
                    out_causas.append({"indicador": "", "impacto": 0, "esforco": 0, "justificativa": ""})
                    project_state["causa_efeito"] = out_causas
                    project_state["causa_efeito_id"] = ce_id + 1
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.rerun()
            with ba2:
                if st.button("🚨 Apagar Tabela", key="ce_clear", use_container_width=True):
                    out_causas = [{"indicador": "", "impacto": 0, "esforco": 0, "justificativa": ""}]
                    project_state["causa_efeito"] = out_causas
                    project_state["causa_efeito_id"] = ce_id + 1
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.rerun()

        project_state["causa_efeito"] = out_causas
        new_text = "Matriz Causa Efeito:\n" + json.dumps(out_causas, ensure_ascii=False)

        # --- Gráfico Esforço x Impacto ---
        st.markdown("---")
        st.subheader("📈 Gráfico Esforço × Impacto")

        # Paleta de cores por quadrante (usada no fundo E nos pontos)
        COR_ALTA_PRIO   = "#1a6e36"  # Verde escuro  — Esforço baixo + Impacto alto
        COR_PROJ_MAIOR  = "#FFD700"  # Amarelo canário — Esforço alto + Impacto alto
        COR_BAIXA_PRIO  = "#d35400"  # Laranja       — Esforço baixo + Impacto baixo
        COR_DESCONS     = "#c0392b"  # Vermelho      — Esforço alto  + Impacto baixo

        def _quadrante(esf, imp):
            """Retorna o nome do quadrante e a cor do ponto para um X (Esforço e Impacto em escala 0-100)."""
            baixo_esf = esf <= 50
            alto_imp  = imp > 50
            if baixo_esf and alto_imp:
                return "Alta Prioridade",  COR_ALTA_PRIO
            elif not baixo_esf and alto_imp:
                return "Projeto Maior",    COR_PROJ_MAIOR
            elif baixo_esf and not alto_imp:
                return "Baixa Prioridade", COR_BAIXA_PRIO
            else:
                return "Desconsiderar",   COR_DESCONS

        # Considera válidos os X's com pelo menos um score > 0
        dados_validos = [
            r for r in out_causas
            if int(r.get("impacto", 0) or 0) > 0 or int(r.get("esforco", 0) or 0) > 0
        ]

        if not dados_validos:
            st.info("Preencha Impacto e/ou Esforço acima para visualizar o gráfico.")
        else:
            # Constrói o DataFrame com a coluna de quadrante e cor já calculadas em Python
            rows_plot = []
            for i, r in enumerate(dados_validos):
                esf = max(1, int(r.get("esforco", 0) or 0))
                imp = max(1, int(r.get("impacto", 0) or 0))
                quad, cor = _quadrante(esf, imp)
                rows_plot.append({
                    "X": f"X{i+1}",
                    "Esforço": esf,
                    "Impacto": imp,
                    "Causa": str(r.get("indicador", ""))[:70],
                    "Quadrante": quad,
                    "Cor": cor,
                })
            df_plot = pd.DataFrame(rows_plot)

            # Fundo dos quadrantes (escala 0-100 tanto para Esforço como Impacto)
            quadrantes = pd.DataFrame([
                {"x1": 0,  "x2": 50,  "y1": 50, "y2": 100, "quad": "Alta Prioridade",  "cor": "#d4edda"},
                {"x1": 50, "x2": 100, "y1": 50, "y2": 100, "quad": "Projeto Maior",    "cor": "#fff3cd"},
                {"x1": 0,  "x2": 50,  "y1": 0,  "y2": 50,  "quad": "Baixa Prioridade", "cor": "#ffe5b4"},
                {"x1": 50, "x2": 100, "y1": 0,  "y2": 50,  "quad": "Desconsiderar",    "cor": "#f8d7da"},
            ])
            bg = alt.Chart(quadrantes).mark_rect(opacity=0.40).encode(
                x=alt.X("x1:Q", scale=alt.Scale(domain=[0, 100])),
                x2="x2:Q",
                y=alt.Y("y1:Q", scale=alt.Scale(domain=[0, 100])),
                y2="y2:Q",
                color=alt.Color("cor:N", scale=None),
                tooltip=["quad:N"]
            )

            # Pontos coloridos de acordo com o quadrante calculado em Python
            _quad_names = ["Alta Prioridade", "Projeto Maior", "Baixa Prioridade", "Desconsiderar"]
            _quad_cores = [COR_ALTA_PRIO, COR_PROJ_MAIOR, COR_BAIXA_PRIO, COR_DESCONS]
            pontos = alt.Chart(df_plot).mark_circle(size=160, opacity=0.90).encode(
                x=alt.X("Esforço:Q", scale=alt.Scale(domain=[0, 100]), title="Esforço [0-100]"),
                y=alt.Y("Impacto:Q", scale=alt.Scale(domain=[0, 100]), title="Impacto [0-100]"),
                color=alt.Color(
                    "Quadrante:N",
                    scale=alt.Scale(domain=_quad_names, range=_quad_cores),
                    legend=None
                ),
                tooltip=["X:N", "Causa:N", "Impacto:Q", "Esforço:Q", "Quadrante:N"]
            )
            rotulos = alt.Chart(df_plot).mark_text(dy=-14, fontSize=12, fontWeight="bold", color="#001C59").encode(
                x="Esforço:Q", y="Impacto:Q", text="X:N"
            )
            linhas_v = alt.Chart(pd.DataFrame([{"v": 50}])).mark_rule(
                color="#888888", strokeDash=[4, 3]
            ).encode(x=alt.X("v:Q"))
            linhas_h = alt.Chart(pd.DataFrame([{"h": 50}])).mark_rule(
                color="#888888", strokeDash=[4, 3]
            ).encode(y=alt.Y("h:Q"))
            chart = (bg + linhas_v + linhas_h + pontos + rotulos).properties(
                width="container", height=430,
                title=alt.TitleParams("Esforço × Impacto — Priorização de Causas", fontSize=15)
            ).configure_view(strokeOpacity=0).interactive()
            st.altair_chart(chart, use_container_width=True)

            # Legenda dos quadrantes — estilo padronizado
            _legend_style = "border-radius:6px; padding:10px 14px; font-size:0.88em; font-weight:500;"
            l1, l2, l3, l4 = st.columns(4)
            l1.markdown(
                f"<div style='background:#d4edda; border-left:4px solid #1a6e36; {_legend_style}'>"
                "🟢 <b>Alta Prioridade</b><br><span style='font-weight:normal;font-size:0.9em;'>Esforço baixo + Impacto alto</span></div>",
                unsafe_allow_html=True)
            l2.markdown(
                f"<div style='background:#fff3cd; border-left:4px solid #c9900a; {_legend_style}'>"
                "🟡 <b>Projeto Maior</b><br><span style='font-weight:normal;font-size:0.9em;'>Esforço alto + Impacto alto</span></div>",
                unsafe_allow_html=True)
            l3.markdown(
                f"<div style='background:#ffe5b4; border-left:4px solid #d35400; {_legend_style}'>"
                "🟠 <b>Baixa Prioridade</b><br><span style='font-weight:normal;font-size:0.9em;'>Esforço baixo + Impacto baixo</span></div>",
                unsafe_allow_html=True)
            l4.markdown(
                f"<div style='background:#f8d7da; border-left:4px solid #c0392b; {_legend_style}'>"
                "🔴 <b>Desconsiderar</b><br><span style='font-weight:normal;font-size:0.9em;'>Esforço alto + Impacto baixo</span></div>",
                unsafe_allow_html=True)

        # --- Salvar ---
        c1, _ = st.columns([1, 5])
        with c1:
            if st.button("💾 Salvar Matriz C&E", disabled=read_only, use_container_width=True):
                project_state["causa_efeito"] = out_causas
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                db.save_draft(pid, tool, {"text": new_text})
                st.success("Causa & Efeito salva!")

    elif tool == "M - Plano de Coleta de Dados":
        st.subheader("📊 Plano de Coleta de Dados")
        st.info("💡 Detalhe como cada indicador ou causa prioritária será medido para garantir dados confiáveis.")
        
        plano_data = project_state.get("plano_coleta", [])
        plano_id = project_state.get("plano_id", 0)

        col_import, col_space = st.columns([2.5, 4.5])
        with col_import:
            if st.button("📥 Importar Causas de Alta Prioridade (Verde)", use_container_width=True, disabled=read_only):
                # O project_state["causa_efeito"] já foi sincronizado no topo do script com as edições do usuário!
                ce_data = project_state.get("causa_efeito", [])
                novas_linhas = []
                for c in ce_data:
                    try:
                        esf = int(float(c.get("esforco", 0) or 0))
                        imp = int(float(c.get("impacto", 0) or 0))
                    except (TypeError, ValueError):
                        esf = 0
                        imp = 0
                    
                    # Baixo Esforço (<=50) + Alto Impacto (>50) = Verde
                    if esf <= 50 and imp > 50:
                        ind_text = str(c.get("indicador", "")).strip()
                        if ind_text:
                            novas_linhas.append({
                                "Definição": f"Medir o impacto de: {ind_text}",
                                "Indicador": ind_text,
                                "Fonte": "", "Amostra": "", "Responsável": "",
                                "Quando": "", "Como": "", "Outros": "", "Uso": "", "Mostrar": ""
                            })
                
                if not novas_linhas:
                    st.warning("⚠️ Não foram encontradas causas no quadrante de Alta Prioridade (Verde) na Matriz C&E. Verifique se pontuou corretamente (Impacto > 50 e Esforço <= 50).")
                else:
                    project_state["plano_coleta"] = plano_data + novas_linhas
                    project_state["plano_id"] = plano_id + 1
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.success(f"✅ {len(novas_linhas)} causas importadas com o 'Esforço' e 'Impacto' mais recentes!")
                    st.rerun()

        if not plano_data:
            plano_data = [{
                "Definição": "", "Indicador": "", "Fonte": "", "Amostra": "", "Responsável": "",
                "Quando": "", "Como": "", "Outros": "", "Uso": "", "Mostrar": ""
            }]

        st.markdown(
            '<style>'
            '[data-testid="stTextArea"] textarea { font-size: 13px !important; line-height: 1.3 !important; resize: vertical !important; }'
            '[data-testid="column"] { padding: 0 4px !important; }'
            'div[data-testid="stHorizontalBlock"] { min-width: 1600px !important; }'
            '</style>'
            '<div style="background-color: #001C59; color: white; padding: 10px; border-radius: 6px; min-width: 1600px; margin-bottom: -10px;">'
            '<div style="display: flex;">'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>Definição Operacional</b></div>'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>Indicador</b></div>'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>Fonte</b></div>'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>Amostra</b></div>'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>Responsável</b></div>'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>Quando</b></div>'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>Como</b></div>'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>Outros Dados</b></div>'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>Uso dos Dados</b></div>'
            '<div style="flex: 1; padding: 0 5px; font-size: 0.85em;"><b>Visualização</b></div>'
            '<div style="flex: 0.4; padding: 0 5px; font-size: 0.85em;"><b>Ação</b></div>'
            '</div></div><br>', 
            unsafe_allow_html=True
        )

        out_plano = []
        for i, row in enumerate(plano_data):
            cols = st.columns([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.4])
            
            h = 140
            v1 = cols[0].text_area("def", value=row.get("Definição", ""), key=f"plano_def_{i}_{plano_id}", height=h, label_visibility="collapsed", disabled=read_only)
            v2 = cols[1].text_area("ind", value=row.get("Indicador", ""), key=f"plano_ind_{i}_{plano_id}", height=h, label_visibility="collapsed", disabled=read_only)
            v3 = cols[2].text_area("src", value=row.get("Fonte", ""), key=f"plano_src_{i}_{plano_id}", height=h, label_visibility="collapsed", disabled=read_only)
            v4 = cols[3].text_area("amo", value=row.get("Amostra", ""), key=f"plano_amo_{i}_{plano_id}", height=h, label_visibility="collapsed", disabled=read_only)
            v5 = cols[4].text_area("res", value=row.get("Responsável", ""), key=f"plano_res_{i}_{plano_id}", height=h, label_visibility="collapsed", disabled=read_only)
            v6 = cols[5].text_area("qnd", value=row.get("Quando", ""), key=f"plano_qnd_{i}_{plano_id}", height=h, label_visibility="collapsed", disabled=read_only)
            v7 = cols[6].text_area("com", value=row.get("Como", ""), key=f"plano_com_{i}_{plano_id}", height=h, label_visibility="collapsed", disabled=read_only)
            v8 = cols[7].text_area("out", value=row.get("Outros", ""), key=f"plano_out_{i}_{plano_id}", height=h, label_visibility="collapsed", disabled=read_only)
            v9 = cols[8].text_area("uso", value=row.get("Uso", ""), key=f"plano_uso_{i}_{plano_id}", height=h, label_visibility="collapsed", disabled=read_only)
            v10 = cols[9].text_area("viz", value=row.get("Mostrar", ""), key=f"plano_viz_{i}_{plano_id}", height=h, label_visibility="collapsed", disabled=read_only)
            
            with cols[10]:
                st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
                if len(plano_data) > 1 and not read_only:
                    if st.button("🗑️", key=f"plano_del_{i}_{plano_id}"):
                        nova_tabela = list(plano_data)
                        nova_tabela.pop(i)
                        project_state["plano_coleta"] = nova_tabela
                        project_state["plano_id"] = plano_id + 1
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.rerun()
                if not read_only:
                    if st.button("➕", key=f"plano_add_{i}_{plano_id}"):
                        nova_tabela = list(plano_data)
                        nova_tabela.insert(i + 1, {
                            "Definição": "", "Indicador": "", "Fonte": "", "Amostra": "", "Responsável": "",
                            "Quando": "", "Como": "", "Outros": "", "Uso": "", "Mostrar": ""
                        })
                        project_state["plano_coleta"] = nova_tabela
                        project_state["plano_id"] = plano_id + 1
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.rerun()

            out_plano.append({
                "Definição": v1, "Indicador": v2, "Fonte": v3, "Amostra": v4, "Responsável": v5,
                "Quando": v6, "Como": v7, "Outros": v8, "Uso": v9, "Mostrar": v10
            })

        if not read_only:
            b1, b3, _ = st.columns([1.5, 1.5, 4])
            with b1:
                if st.button("➕ Adicionar Linha", key="btn_add_plano", use_container_width=True):
                    out_plano.append({
                        "Definição": "", "Indicador": "", "Fonte": "", "Amostra": "", "Responsável": "",
                        "Quando": "", "Como": "", "Outros": "", "Uso": "", "Mostrar": ""
                    })
                    project_state["plano_coleta"] = out_plano
                    project_state["plano_id"] = plano_id + 1
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.rerun()
            with b3:
                if st.button("🚨 Apagar Tabela", key="btn_clear_plano", use_container_width=True):
                    project_state["plano_coleta"] = []
                    project_state["plano_id"] = plano_id + 1
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.rerun()

        project_state["plano_coleta"] = out_plano
        new_text = "Plano de Coleta de Dados:\n" + json.dumps(out_plano, ensure_ascii=False)

        c1, _ = st.columns([1, 5])
        with c1:
            if st.button("💾 Salvar Plano", disabled=read_only, use_container_width=True):
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                db.save_draft(pid, tool, {"text": new_text})
                st.success("Plano de Coleta salvo!")


    elif tool in ["D - Saving Projetado", "C - Saving Realizado"]:
        st.subheader(f"Cálculo de {tool}")
        st.info("Desdobre o impacto financeiro. O 'Saving Total' será calculado automaticamente ao salvar.")
        state_key = "saving_projetado" if tool == "D - Saving Projetado" else "saving_realizado"
        sav = project_state.get(state_key) or {}
        
        # Merge pre-render e bypass de State Session (Injeção via Coach)
        if "saving_coach_feedback" in st.session_state:
            ia_fb = st.session_state.pop("saving_coach_feedback")
            for k, v in ia_fb.items():
                if v: sav[k] = v
            # Injeta explícito nos componentes de texto antes de renderizarem na UI
            if sav.get("hard_racional"): st.session_state[f"hr_{state_key}"] = sav.get("hard_racional")
            if sav.get("soft_racional"): st.session_state[f"sr_{state_key}"] = sav.get("soft_racional")
            if sav.get("avoidance_racional"): st.session_state[f"ar_{state_key}"] = sav.get("avoidance_racional")
            if sav.get("faturamento_racional"): st.session_state[f"fr_{state_key}"] = sav.get("faturamento_racional")
            
            # Salva logo em seguida para perpetuar sem botão
            project_state[state_key] = sav
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                
        def safe_float(v):
            try:
                if isinstance(v, dict): return 0.0
                return float(v)
            except (ValueError, TypeError):
                return 0.0
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Hard Saving")
            st.markdown("<div style='height:40px; font-size:13px; color:gray;'>(Impacto Direto no DRE - Ex: Materiais, Faturado)</div>", unsafe_allow_html=True)
            h_val = st.number_input("Valor (R$)", value=safe_float(sav.get("hard", 0.0)), disabled=read_only, key=f"hard_{state_key}")
            h_rac = st.text_area("Memorial de Cálculo (Como chegou no valor)", value=sav.get("hard_racional", ""), height=150, disabled=read_only, key=f"hr_{state_key}")
        with c2:
            st.markdown("#### Soft Saving")
            st.markdown("<div style='height:40px; font-size:13px; color:gray;'>(Ganho Operacional / Liberação de Capacidade)</div>", unsafe_allow_html=True)
            s_val = st.number_input("Valor (R$)", value=safe_float(sav.get("soft", 0.0)), disabled=read_only, key=f"soft_{state_key}")
            s_rac = st.text_area("Memorial de Cálculo (Como chegou no valor)", value=sav.get("soft_racional", ""), height=150, disabled=read_only, key=f"sr_{state_key}")
        
        c3, c4 = st.columns(2)
        with c3:
            st.markdown("#### Cost Avoidance")
            st.markdown("<div style='height:40px; font-size:13px; color:gray;'>(Fuga de Custo - Ex: Evitou contratar, Multas)</div>", unsafe_allow_html=True)
            a_val = st.number_input("Valor (R$)", value=safe_float(sav.get("avoidance", 0.0)), disabled=read_only, key=f"avoid_{state_key}")
            a_rac = st.text_area("Memorial de Cálculo (Como chegou no valor)", value=sav.get("avoidance_racional", ""), height=150, disabled=read_only, key=f"ar_{state_key}")
        with c4:
            st.markdown("#### Ganho de Faturamento")
            st.markdown("<div style='height:40px; font-size:13px; color:gray;'>(Novas Receitas - Ex: Aumento de Capacidade e Venda)</div>", unsafe_allow_html=True)
            f_val = st.number_input("Valor (R$)", value=safe_float(sav.get("faturamento", 0.0)), disabled=read_only, key=f"fatu_{state_key}")
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

    elif tool == "D - Matriz RACI":
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
        
        # Salvamento automático silencioso (Auto-save real on interaction)
        if edited_raci != raci_data and not read_only:
            # Proteção contra state bug do Streamlit (onde retorna dict de edicoes em vez de rows durante unmounts)
            if isinstance(edited_raci, list):
                project_state["raci"] = edited_raci
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
        
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

    elif tool == "M - Fluxograma":
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

    elif tool == "M - Ishikawa":
        import ui_ishikawa_5pq
        ui_ishikawa_5pq.render_ishikawa_ui(project_state, pid, db, read_only)
        
    elif tool == "A - 5 Porquês":
        import ui_ishikawa_5pq
        ui_ishikawa_5pq.render_5pqs_ui(project_state, pid, db, read_only)

    elif tool == "A - Plano de Validação de Causas":
        import ui_plano_validacao
        ui_plano_validacao.render_plano_validacao_ui(project_state, pid, db, read_only)
        
    elif tool in ["D - Capabilidade (Baseline)", "I - Capabilidade (Melhoria)"]:
        import ui_capabilidade
        ui_capabilidade.render_capabilidade_ui(project_state, pid, db, read_only, tool)

    elif tool == "I - Plano de Soluções":
        import ui_plano_solucoes
        ui_plano_solucoes.render_plano_solucoes_ui(project_state, pid, db, read_only)

    elif tool == "I - Plano de Ação":
        import ui_plano_acao_5w2h
        ui_plano_acao_5w2h.render_plano_acao_ui(project_state, pid, db, read_only)

    elif tool == "M - Quick Wins":
        import ui_quick_wins
        ui_quick_wins.render_quick_wins_ui(project_state, pid, db, read_only)
        
    elif tool == "C - Plano de Controle":
        import ui_plano_controle
        ui_plano_controle.render_plano_controle_ui(project_state, pid, db, read_only)

    elif tool == "M - Repositório de Medições":
        import ui_repositorio_dados
        ui_repositorio_dados.render_repositorio_dados_ui(project_state, pid, db, read_only)

    else:
        st.info("Outras ferramentas estão na fila de atualização para a nuvem.")
        draft = db.load_draft(pid, tool) or {}
        draft_text = draft.get("text", "")
        new_text = st.text_area("Borrão da Ferramenta (Para Análise da IA):", value=draft_text, height=420, disabled=read_only)
        if st.button("💾 Salvar Rascunho", disabled=read_only):
            db.save_draft(pid, tool, {"text": new_text})
            st.success("Salvo!")

with coach_container:
    if tool in ["D - Matriz RACI", "M - Fluxograma"]:
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
        if tool == "D - VOC/VOB":
            st.info("💡 **Preenchimento Guiado VOC/VOB:** A IA vai gerar uma linha de referência para sua tabela baseada nas 3 respostas abaixo.")
            target_voc = st.radio("Gerar sugestão para:", ["Voz do Cliente (VOC)", "Voz do Negócio (VOB)"], disabled=read_only)
            q1 = st.text_input("Qual a necessidade do cliente (ou negócio)?", disabled=read_only)
            q2 = st.text_input("Qual é o valor atual / performance atual?", disabled=read_only)
            q3 = st.text_input("Qual é o valor limite entre a satisfação e a insatisfação?", disabled=read_only)
        elif tool == "D - Project Charter":
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
        elif tool == "D - SIPOC (por etapa)":
            st.info("💡 **Mapeamento Modular:** Diga qual parte do fluxo o Doutor Lean deve estruturar ativamente para você.")
            target_sipoc = st.radio("O que preencher automaticamente?", ["Etapas Mestre do Processo (P)", "Linhas de Entrada e Fornecedores (S/I)", "Linhas de Saídas e Clientes (O/C)"], disabled=read_only)

            if target_sipoc == "Etapas Mestre do Processo (P)":
                st.warning("⚠️ **Aviso de Sobrescrição:** A geração baseada em texto livre vai inicializar o tabuleiro do zero com novas Grandes Fases deduzidas, substituindo tudo atual.")
                q_desc = st.text_area("Descreva de forma simples como funciona o seu processo atual do início ao fim (Textão Livre):", disabled=read_only, height=100)
            elif target_sipoc == "Linhas de Entrada e Fornecedores (S/I)":
                st.info("💡 **Mapeamento de Esquerda:** A IA relerá as Etapas Centrais (P) que estão atualmente preenchidas e re-escreverá todos os Fornecedores e Entradas lógicas atreladas a elas.")
            else:
                st.info("💡 **Mapeamento de Direita:** A IA relerá as Etapas Centrais (P) que estão atualmente preenchidas e re-escreverá todas as Saídas e Clientes lógicas atreladas a elas.")
        elif tool in ["D - Saving Projetado", "C - Saving Realizado"]:
            st.info("💡 **Doutor Lean CFO:** Diga quais os ganhos imaginados neste projeto, e o Coach construirá um formato executivo guiando como precificar (e enquadrar em Hard/Soft) cada um deles.")
            
            # Garantir que a state session memorize as edições manuais
            if "coach_saving_desc" not in st.session_state:
                st.session_state["coach_saving_desc"] = project_state.get("charter", {}).get("benefits", "")
            
            def clear_saving_feedback():
                if "saving_coach_feedback" in st.session_state:
                    del st.session_state["saving_coach_feedback"]
                
            q_desc = st.text_area("Descreva os ganhos ou ideias (ou mantenha os importados do Project Charter da tela acima):", key="coach_saving_desc", height=250, disabled=read_only, on_change=clear_saving_feedback)
        elif tool == "M - Repositório de Medições":
            st.info("💡 **Cientista de Dados Black Belt:** Cole ou faça o upload de tabelas de dados. O Doutor Lean ajudará na interpretação e vai te pedir para orientar a análise para montar os gráficos.")
            st.warning("⚠️ Lembre-se: O robô não sabe como é o Gemba. A interpretação humana dos padrões matemáticos listados aqui é VITAL.")
        elif tool == "M - Causa & Efeito - Esforço Impacto":
            st.info("💡 **Análise de Causa & Efeito:** O Doutor Lean analisará cada X e gerará só o **Impacto** ou só o **Esforço**, dependendo do botão escolhido abaixo.")
            st.warning("⚠️ Preencha os X's na tabela ao lado e certifique-se que o Problema está salvo no Project Charter.")
        elif tool == "M - Plano de Coleta de Dados":
            st.info("💡 **Doutor Lean:** O robô analisará as causas prioritárias (Matriz C&E) ou indicadores mapeados para sugerir um plano de coleta robusto.")
            st.caption("Certifique-se de que a Matriz C&E possui itens marcados como 'Alta Prioridade' (Verde) para melhores sugestões.")
        elif tool == "I - Plano de Ação":
            st.info("💡 **Desdobramento de Ações:** O Coach analisará uma Solução específica e sugerirá as ações táticas (O que / Como) para alcançá-la.")
            st.caption("A IA preencherá apenas textos de ação; prazos e responsáveis continuam no seu controle.")
        else:
            st.info("💡 **Dica:** A IA lerá todo o contexto do seu projeto automaticamente. Se quiser, você pode direcioná-la adicionando um pedido específico abaixo.")
            ai_context_prompt = st.text_area(
                "Contexto ou Pedido Específico (Opcional):",
                placeholder="Ex: Foque apenas em redução de tempo na área de triagem...",
                height=80,
                disabled=read_only
            )
        st.warning("⚠️ **Atenção:** As informações geradas por Inteligência Artificial são exclusivas para direcionamento metodológico e devem obrigatoriamente ser revisadas e validadas na tabela ao lado antes do uso.")
        
    if tool == "M - Causa & Efeito - Esforço Impacto" and not read_only:
        # Tres botoes separados para a ferramenta C&E
        ce_b1, ce_b2, ce_b3 = st.columns([1, 1, 1])
        ce_mode = None
        if ce_b1.button("🎯 Avaliar Impacto", use_container_width=True):
            ce_mode = "impacto"
        if ce_b2.button("💪 Avaliar Esforço", use_container_width=True):
            ce_mode = "esforco"
        if ce_b3.button("💡 Avaliar Ambos", use_container_width=True):
            ce_mode = "ambos"

        if ce_mode:
            causas_atuais = project_state.get("causa_efeito", [])
            lista_causas = []
            for r in causas_atuais:
                # Monta texto a partir do campo unificado "indicador" (retrocompat: também aceita "etapa"+"causa")
                indicador = str(r.get("indicador", r.get("causa", ""))).strip()
                etapa_old = str(r.get("etapa", "")).strip()
                if etapa_old and indicador and etapa_old not in indicador:
                    texto = f"{etapa_old} — {indicador}"
                elif indicador:
                    texto = indicador
                else:
                    texto = etapa_old
                if texto:
                    lista_causas.append(texto)
            if not lista_causas:
                st.error("Preencha ao menos uma causa (X) na tabela antes de solicitar a análise.")
            else:
                spinner_msg = {
                    "impacto": "Doutor Lean estimando Impacto de cada causa...",
                    "esforco": "Doutor Lean estimando Esforço de cada causa...",
                    "ambos": "Doutor Lean avaliando Impacto e Esforço de cada causa...",
                }.get(ce_mode, "Processando...")
                with st.spinner(spinner_msg):
                    ai_rows = suggest_causa_efeito_impacto(project_state, lista_causas)
                    if not ai_rows:
                        st.error("A IA não retornou resultados. Tente novamente.")
                    else:
                        merged = []
                        for idx, orig in enumerate(causas_atuais):
                            match = ai_rows[idx] if idx < len(ai_rows) else None
                            if match:
                                novo = {
                                    "indicador": str(orig.get("indicador", orig.get("causa", orig.get("etapa", "")))),
                                    "impacto": orig.get("impacto", 0),
                                    "esforco": orig.get("esforco", 0),
                                    "justificativa": str(match.get("justificativa", orig.get("justificativa", "")))
                                }
                                if ce_mode in ("impacto", "ambos"):
                                    novo["impacto"] = int(match.get("impacto", orig.get("impacto", 0)))
                                if ce_mode in ("esforco", "ambos"):
                                    novo["esforco"] = int(match.get("esforco", orig.get("esforco", 0)))
                                merged.append(novo)
                            else:
                                merged.append(orig)
                        project_state["causa_efeito"] = merged
                        project_state["causa_efeito_id"] = project_state.get("causa_efeito_id", 0) + 1
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.session_state["ai_generated_warning"] = f"✨ ⚠️ {'Impacto' if ce_mode == 'impacto' else 'Esforço' if ce_mode == 'esforco' else 'Impacto e Esforço'} estimados! Revise os valores e veja o gráfico."
                        st.rerun()

        # --- Botão Dr. Lean (Consolidar X's) — aparece no Coach IA abaixo das avaliações IA ---
        if tool == "M - Causa & Efeito - Esforço Impacto" and not read_only:
            st.markdown("---")
            st.markdown("#### 🤖 Dr. Lean — Consolidação Inteligente de X's")
            st.caption("Analisa **todos** os indicadores da Planilha de Indicadores e gera uma lista enxuta de X's primários, agrupando indicadores redundantes e evitando misturar causas profundas com causas de primeiro nível.")
            if st.button("🧠 Gerar X's Consolidados (Dr. Lean)", use_container_width=True, key="btn_consolidar_xs_coach"):
                ind_data = project_state.get("matriz_indicadores", [])
                if not ind_data or all(not any(v for v in row.values()) for row in ind_data):
                    st.warning("⚠️ A Planilha de Indicadores está vazia. Preencha-a primeiro.")
                else:
                    with st.spinner("Dr. Lean analisando indicadores e consolidando X's..."):
                        ce_id_now = project_state.get("causa_efeito_id", 0)
                        xs_gerados = suggest_xs_consolidados(project_state, ind_data)
                    if not xs_gerados:
                        st.error("A IA não retornou X's. Verifique sua conexão com a API.")
                    else:
                        project_state["causa_efeito"] = xs_gerados
                        project_state["causa_efeito_id"] = ce_id_now + 1
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.session_state["ai_generated_warning"] = f"✅ {len(xs_gerados)} X's primários gerados pelo Dr. Lean! Revise, ajuste os pesos (Impacto/Esforço) e salve."
                        st.rerun()
    else:
        ce_mode = None
        mode_str = None  # default — only set to "review"/"generate" when button is clicked
        btn_label = "🔎 Iniciar Revisão" if ia_action == "Revisão do Coach IA" else "✨ Gerar Sugestão"
        
        if tool == "A - 5 Porquês" and ia_action != "Revisão do Coach IA":
            pop_5pq = st.popover("✨ Gerar Matriz Profunda", use_container_width=True)
            pop_5pq.warning("⚠️ **Alerta:** A Inteligência Artificial irá preencher todo o seu diagrama lendo o contexto já existente. Ela criará até 10 camadas principais preenchendo até o 4º nível! Tem certeza que deseja dar a ordem de geração macro?")
            if pop_5pq.button("🚀 Confirmar Arquitetura Profunda", disabled=read_only, use_container_width=True):
                mode_str = "generate"
        else:
            if st.button(btn_label, disabled=read_only, use_container_width=True):
                mode_str = "review" if ia_action == "Revisão do Coach IA" else "generate"

        # --- Só executa a IA quando o botão foi clicado (mode_str não é None) ---
        if mode_str is not None:

            # --- FLUXO ESPECIAL: Geração (Autocompletar) do VOC/VOB ---
            if tool == "D - VOC/VOB" and mode_str == "generate":
                with st.spinner(f"Doutor Lean gerando linha para {target_voc}..."):
                    new_row = suggest_vocvob_row(target_voc, q1, q2, q3, project_state)
                    t_key = "voc" if target_voc == "Voz do Cliente (VOC)" else "vob"
                    if "voc_vob" not in project_state:
                        project_state["voc_vob"] = {"voc": [], "vob": [], "notes": ""}
                    if t_key not in project_state["voc_vob"]:
                        project_state["voc_vob"][t_key] = []
                    project_state["voc_vob"][t_key].append(new_row)
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.session_state["ai_generated_warning"] = "✨ ⚠️ Linha inserida automaticamente pela Inteligência Artificial na tabela. Por favor, releia, valide os campos e salve!"
                    st.rerun()

            # --- FLUXO ESPECIAL: Geração do Charter via VOC/VOB (Problema) ---
            elif tool == "D - Project Charter" and mode_str == "generate" and target_charter == "Problema e Benefícios":
                if not q_impact:
                    st.warning("Por favor, preencha o impacto percebido antes de gerar sugestões.")
                else:
                    with st.spinner("Doutor Lean processando seu VOC/VOB e descrevendo o Problema..."):
                        new_data = generate_problem_benefits_from_vocvob(project_state, q_impact)
                        if "charter" not in project_state:
                            project_state["charter"] = {}
                        project_state["charter"]["problem"] = new_data.get("problem", "")
                        project_state["charter"]["benefits"] = new_data.get("benefits", "")
                        if not project_state["charter"].get("main_indicator"):
                            v_state = project_state.get("voc_vob", {})
                            indics = []
                            for row in v_state.get("voc", []) + v_state.get("vob", []):
                                y_v = str(row.get("Y (indicador)", row.get("Y (como medir)", ""))).strip()
                                if y_v: indics.append(y_v)
                            if indics:
                                project_state["charter"]["main_indicator"] = " / ".join(list(dict.fromkeys(indics)))
                        db.save_draft(pid, "D - Project Charter", {"charter": project_state["charter"], "text": "AI Generated Charter (Problem)"})
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.session_state["ai_generated_warning"] = "✨ ⚠️ Problema e Benefícios gerados automaticamente associando o impacto da necessidade original transcrita do VOC/VOB! Releia e verifique se as premissas estão corretas."
                        st.rerun()

            # --- FLUXO ESPECIAL: Geração do Charter via VOC/VOB (SMART Goal) ---
            elif tool == "D - Project Charter" and mode_str == "generate" and target_charter == "Objetivo SMART":
                if not q_tempo or not q_meta:
                    st.warning("Por favor, preencha o prazo e a meta numérica para construirmos o SMART!")
                else:
                    with st.spinner("Estruturando meta SMART e consolidando objetivo..."):
                        smart_goal = generate_smart_goal_from_charter_context(project_state, q_tempo, q_meta)
                        if "charter" not in project_state:
                            project_state["charter"] = {}
                        project_state["charter"]["goal"] = smart_goal
                        if not project_state["charter"].get("main_indicator"):
                            v_state = project_state.get("voc_vob", {})
                            indics = []
                            for row in v_state.get("voc", []) + v_state.get("vob", []):
                                y_v = str(row.get("Y (indicador)", row.get("Y (como medir)", ""))).strip()
                                if y_v: indics.append(y_v)
                            if indics:
                                project_state["charter"]["main_indicator"] = " / ".join(list(dict.fromkeys(indics)))
                        db.save_draft(pid, "D - Project Charter", {"charter": project_state["charter"], "text": "AI Generated Charter (SMART Goal)"})
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.session_state["ai_generated_warning"] = "✨ ⚠️ Objetivo construído segundo o padrão SMART! Releia e edite se necessário."
                        st.rerun()

            # --- FLUXO ESPECIAL: Geração (Autocompletar) do SIPOC ---
            elif tool == "D - SIPOC (por etapa)" and mode_str == "generate":
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
            elif tool in ["D - Saving Projetado", "C - Saving Realizado"] and mode_str == "generate":
                if not q_desc:
                    st.warning("Eita! Você precisa descrever algum benefício preliminar ou ideia na caixa de texto pro CFO conseguir criar o modelo financeiro de conversão.")
                else:
                    with st.spinner("O CFO Virtual está analisando as possibilidades de ganhos..."):
                        new_sav = suggest_saving_rationale(project_state, q_desc)
                        
                        st.session_state["saving_coach_feedback"] = new_sav # Encaminha via portal cross-rerun
                        st.session_state["ai_generated_warning"] = "✨ ⚠️ Análise Financeira Concluída. Veja a classificação das oportunidades logo abaixo!"
                        st.rerun()

            # --- FLUXO ESPECIAL: Geração (Autocompletar) de Matriz de Indicadores ---
            elif tool == "M - Matriz de Indicadores" and mode_str == "generate":
                with st.spinner("Doutor Lean processando etapas e criando árvore de indicadores..."):
                    new_matriz = suggest_matriz_indicadores(project_state)
                    if not new_matriz:
                        st.error("Falha ao gerar indicadores. Certifique-se de que a coluna de Processos não está vazia.")
                    else:
                        project_state["matriz_indicadores"] = new_matriz
                        project_state["matriz_id"] = project_state.get("matriz_id", 0) + 1
                        db.save_draft(pid, tool, {"text": json.dumps(new_matriz, ensure_ascii=False)})
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.session_state["ai_generated_warning"] = "✨ ⚠️ Matriz preenchida com as métricas geradas pela IA. Releia os tópicos!"
                        st.rerun()

            # --- FLUXO ESPECIAL: Geração do Ishikawa ---
            elif tool == "M - Ishikawa" and mode_str == "generate":
                with st.spinner("Doutor Lean estruturando a lista de causas (6Ms) a partir do seu Efeito..."):
                    ishikawas = project_state.get("ishikawas", [])
                    if not ishikawas:
                        st.error("Crie um painel do Ishikawa primeiro (no painel central) antes de pedir sugestões.")
                    else:
                        # Tenta pegar quem está na tela ativamente selecionado
                        active = ishikawas[-1]
                        if "active_ish_id" in st.session_state:
                            active = next((i for i in ishikawas if i["id"] == st.session_state["active_ish_id"]), ishikawas[-1])
                        
                        effect = str(active.get("effect", "")).strip()
                        if not effect:
                            st.error("Escreva o Problema primeiro na cabeça do peixe!")
                        else:
                            try:
                                import json
                                import coach
                                client = coach.client
                                prompt = f"""Atue como um Master Black Belt Lean Seis Sigma analítico. Contexto: {project_state.get('name')} - {project_state.get('charter', {}).get('problem', '')}. Problema Central (Cabeça do Peixe): {effect}.
Você deve conduzir um brainstorming profundo e sugerir Causas Primárias criativas para este problema. Divida suas sugestões obrigatoriamente nas 6 categorias (Máquina, Método, Material, Mão de Obra, Meio Ambiente, Medida).
Para CADA categoria, você deve apresentar no mínimo 3 a 5 hipóteses diferentes de causa! Não retorne apenas uma por categoria.
Retorne EXATAMENTE UM JSON em formato válido: {{"rows": [{{"categoria": "...", "causa": "..."}}, ...]}}"""
                                res = client.chat.completions.create(model=coach.get_model(), temperature=0.3, response_format={"type": "json_object"}, messages=[{"role": "system", "content": prompt}, {"role": "user", "content": "Gere a matriz"}])
                                data = json.loads(res.choices[0].message.content or "{}")
                                sugestoes = data.get("rows", [{"categoria": "ERRO", "causa": "JSON vazio"}])
                            except Exception as fail_e:
                                sugestoes = [{"categoria": "ERRO FATAL", "causa": str(fail_e)[:100]}]

                            if not sugestoes:
                                st.error("Falha ao gerar Ishikawa. Tente um problema mais descritivo.")
                            else:
                                dict_sug = {}
                                for s in sugestoes:
                                    dict_sug.setdefault(s.get("categoria", "Outros"), []).append(s.get("causa", ""))
                                
                                used_cats = set()
                                obj_spines = active.get("spines", [])
                                if isinstance(obj_spines, dict):
                                    obj_spines = list(obj_spines.values())
                                    active["spines"] = obj_spines

                                for spine in obj_spines:
                                    cat_name = spine.get("category", "")
                                    for ai_cat, ai_causes in dict_sug.items():
                                        import unicodedata, re
                                        def norm_str(s):
                                            n = unicodedata.normalize('NFKD', str(s)).encode('ASCII', 'ignore').decode('utf-8').lower()
                                            return re.sub(r'[^a-z0-9]', '', n)
                                        
                                        if norm_str(ai_cat) in norm_str(cat_name) or norm_str(cat_name) in norm_str(ai_cat):
                                            for c_idx, c_text in enumerate(ai_causes):
                                                # Procura uma caixa vazia na categoria para sobreescrever, senão adiciona
                                                empty_slot = next((c for c in spine.setdefault("causes", []) if not c.get("causa", "").strip()), None)
                                                if empty_slot:
                                                    empty_slot["causa"] = f"IA: {c_text}"
                                                else:
                                                    spine["causes"].append({"causa": f"IA: {c_text}"})
                                            used_cats.add(ai_cat)
                                            
                                    # STREAMLIT FIX: Limpa TODAS as caixas c_ e cb_ da memoria
                                    # para que o Streamlit não re-sobrescreva o preenchimento da IA!
                                    keys_to_delete = [k for k in st.session_state.keys() if k.startswith(f"c_{spine.get('id')}") or k.startswith(f"cb_{spine.get('id')}")]
                                    for k in keys_to_delete:
                                        try:
                                            del st.session_state[k]
                                        except KeyError:
                                            pass
                                
                                import uuid
                                def get_id(): return str(uuid.uuid4())[:8]
                                
                                for ai_cat, ai_causes in dict_sug.items():
                                    if ai_cat not in used_cats:
                                        causes_blocks = [{"causa": f"IA: {c}"} for c in ai_causes]
                                        active["spines"].append({
                                            "id": get_id(),
                                            "category": ai_cat,
                                            "causes": causes_blocks
                                        })

                                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                st.session_state["ai_generated_warning"] = "✨ ⚠️ Diagrama Ishikawa preenchido com subcausas! Revise e ajuste as tabelas."
                                st.rerun()

            # --- FLUXO ESPECIAL: Geração do Plano de Coleta de Dados ---
            elif tool == "M - Plano de Coleta de Dados" and mode_str == "generate":
                with st.spinner("Doutor Lean estruturando o plano de medição metrológica..."):
                    # Pega as causas verdes como base se existirem
                    ce_data = project_state.get("causa_efeito", [])
                    causas_v = [c for c in ce_data if int(c.get("esforco", 0) or 0) <= 50 and int(c.get("impacto", 0) or 0) > 50]
                    
                    sugestoes_raw = suggest_plano_coleta(project_state, causas_v)
                    if not sugestoes_raw:
                        st.error("Falha ao gerar o plano. Tente adicionar causas na Matriz C&E primeiro.")
                    else:
                        novas_linhas = []
                        for s in sugestoes_raw:
                            novas_linhas.append({
                                "Definição": s.get("definicao", ""),
                                "Indicador": s.get("indicador", ""),
                                "Fonte": s.get("fonte", ""),
                                "Amostra": s.get("amostra", ""),
                                "Responsável": s.get("responsavel", ""),
                                "Quando": s.get("quando", ""),
                                "Como": s.get("como", ""),
                                "Outros": s.get("outros", ""),
                                "Uso": s.get("uso", ""),
                                "Mostrar": s.get("mostrar", "")
                            })
                        project_state["plano_coleta"] = novas_linhas
                        project_state["plano_id"] = project_state.get("plano_id", 0) + 1
                        db.save_draft(pid, tool, {"text": json.dumps(novas_linhas, ensure_ascii=False)})
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.session_state["ai_generated_warning"] = "✨ ⚠️ Plano de Coleta sugerido pela IA baseado nas causas prioritárias detectadas. Por favor, valide a viabilidade técnica da coleta!"
                        st.rerun()

            # --- FLUXO ESPECIAL: Geração dos 5 Porquês ---
            # --- FLUXO ESPECIAL: Geração (Macro/Matrizes Arqueológicas) dos 5 Porquês ---
            elif tool == "A - 5 Porquês" and mode_str == "generate":
                with st.spinner("Doutor Lean atuando como Mestre Arquiteto de Árvores (Isso pode levar de 15 a 30 segundos)..."):
                    pqs = project_state.get("cinco_pqs", [])
                    if not pqs:
                        st.error("Crie um painel do 5 Porquês primeiro (no painel central) antes de pedir sugestões.")
                    else:
                        selected_id = st.session_state.get("cinco_pqs_selected_id")
                        active = next((p for p in pqs if p.get("id") == selected_id), pqs[-1])
                        effect = str(active.get("effect", "")).strip()
                        if not effect:
                            st.error("Escreva o Problema Central / Y desta análise primeiro!")
                        else:
                            from coach import suggest_deep_5pq_tree
                            new_branches = suggest_deep_5pq_tree(project_state, effect, active.get("branches", []))
                            if not new_branches:
                                st.error("Falha ao gerar Árvore Estruturada. Refine o problema.")
                            else:
                                active["branches"] = new_branches

                                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                # Incrementa contador de geração para forçar re-render dos text_areas
                                st.session_state["pq_gen_ver"] = st.session_state.get("pq_gen_ver", 0) + 1
                                st.session_state["ai_generated_warning"] = "✨ ⚠️ Árvore Estrutural Profunda gerada com sucesso pela arquitetura JSON do Doutor Lean!"
                                st.rerun()

            # --- FLUXO ESPECIAL: Geração do Plano de Ação (5W2H) ---
            elif tool == "I - Plano de Ação" and mode_str == "generate":
                with st.spinner("Doutor Lean desdobrando ações operacionais..."):
                    # Precisamos saber se o aluno importou algo
                    planos_acao = project_state.get("planos_acao", [])
                    if not planos_acao or not planos_acao[0].get("rows", []):
                        st.error("Nenhuma Solução disponível no Plano de Ação. Importe as soluções primeiro!")
                    else:
                        rows = planos_acao[0]["rows"]
                        import coach_extensions
                        # A IA vai ler a lista e pra cada `solucao` vazia (sem acoes vinculadas ou as que o usuario marcou como vazias), ela pode gerar.
                        # Para facilitar, a IA pode processar a 1ª linha vazia que achar!
                        # Vamos buscar a primeira linha que é is_parent e onde a "acao" tá vazia.
                        target_row_idx = next((i for i, r in enumerate(rows) if not str(r.get("acao", "")).strip()), -1)
                        if target_row_idx == -1:
                            st.error("Todas as linhas já possuem pelo menos uma ação descrita! Limpe a ação de alguma solução para eu descrevê-la novamente.")
                        else:
                            target_row = rows[target_row_idx]
                            causa = str(target_row.get("causa", ""))
                            solucao = str(target_row.get("solucao", ""))
                            acoes_sugeridas = coach_extensions.suggest_acao_5w2h(project_state, causa, solucao)
                            if not acoes_sugeridas:
                                st.error("Falha ao quebrar a solução em ações passo a passo.")
                            else:
                                # A primeira ação preenche a linha atual
                                target_row["acao"] = acoes_sugeridas[0]
                                # As próximas viram filhas
                                import uuid
                                for idx_adic, ax in enumerate(acoes_sugeridas[1:]):
                                    nova_filha = {
                                        "row_id": str(uuid.uuid4())[:12],
                                        "sol_id": target_row.get("sol_id"),
                                        "is_parent": False,
                                        "id_display": target_row.get("id_display", "-"),
                                        "causa": target_row.get("causa", ""),
                                        "solucao": target_row.get("solucao", ""),
                                        "acao": ax, "onde": "", "ini_prev": "", "fim_prev": "",
                                        "ini_real": "", "fim_real": "", "quem": "", "status": "Não Iniciado"
                                    }
                                    rows.insert(target_row_idx + 1 + idx_adic, nova_filha)
                                
                                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                st.session_state["ai_generated_warning"] = f"✨ ⚠️ A Solução `{solucao[:30]}...` foi desdobrada em {len(acoes_sugeridas)} ações passo a passo! Agora preencha os prazos/donos localmente."
                                st.rerun()

            # --- FLUXO ESPECIAL: Geração do Quick Wins ---
            elif tool == "M - Quick Wins" and mode_str == "generate":
                with st.spinner("Doutor Lean desdobrando Quick Wins..."):
                    qw_data = project_state.get("quick_wins", [])
                    if not qw_data or not qw_data[0].get("rows", []):
                        st.error("Nenhuma Oportunidade disponível no Quick Wins. Adicione uma linha primeiro!")
                    else:
                        rows = qw_data[0]["rows"]
                        import coach_extensions
                        target_row_idx = next((i for i, r in enumerate(rows) if not str(r.get("acao", "")).strip()), -1)
                        if target_row_idx == -1:
                            st.error("Todas as oportunidades já possuem ações! Limpe o campo para eu gerar novamente.")
                        else:
                            target_row = rows[target_row_idx]
                            causa = str(target_row.get("causa", ""))
                            solucao = str(target_row.get("solucao", ""))
                            acoes_sugeridas = coach_extensions.suggest_acao_5w2h(project_state, causa, solucao)
                            if not acoes_sugeridas:
                                st.error("Falha ao gerar o passo a passo.")
                            else:
                                target_row["acao"] = acoes_sugeridas[0]
                                target_row["version_ai"] = target_row.get("version_ai", 0) + 1
                                import uuid
                                for idx_adic, ax in enumerate(acoes_sugeridas[1:]):
                                    rows.insert(target_row_idx + 1 + idx_adic, {
                                        "row_id": str(uuid.uuid4())[:12], "sol_id": target_row.get("sol_id"), "is_parent": False,
                                        "id_display": target_row.get("id_display", "-"), "causa": target_row.get("causa", ""), "solucao": target_row.get("solucao", ""),
                                        "acao": ax, "onde": "", "ini_prev": "", "fim_prev": "", "ini_real": "", "fim_real": "", "quem": "", "status": "Não Iniciado", "version_ai": 0
                                    })
                                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                st.session_state["ai_generated_warning"] = "✨ Quick Wins táticos gerados com sucesso!"
                                st.rerun()

                contexto_medicoes = ""
                reps = project_state.get("measurement_reports", [])
                if reps:
                    contexto_medicoes = "\n\n[DADOS HISTÓRICOS DE REPORT]:\nO aluno também gerou análises de gráficos neste projeto, considere-os:\n"
                    for r in reps[-3:]: # max 3 pra nao estourar token
                        contexto_medicoes += f"--- {r['title']} ---\n"
                        for m in r.get("logs", []):
                            if m["role"] == "assistant":
                                contexto_medicoes += f"Análise: {m['content']}\n"
                
                text_for_ai = new_text + contexto_medicoes

                if mode_str == "generate" and ai_context_prompt.strip():
                    text_for_ai = f"PEDIDO ESPECÍFICO DO USUÁRIO PARA ESTA GERAÇÃO: {ai_context_prompt}\n\nDADOS ATUAIS DA FERRAMENTA:\n{new_text}{contexto_medicoes}"

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
                            st.error(f"**{pretty_gap_id(g.get('id', ''))}: {g.get('reason', '')}")
                    else:
                        st.write("- A análise não encontrou gaps ou gerou novas propriedades.")

