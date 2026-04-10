import streamlit as st
import uuid
import pandas as pd
import altair as alt
from datetime import datetime, date

def render_quick_wins_ui(project_state, pid, db, read_only):
    st.subheader("🚀 Quick Wins (Ganhos Rápidos)")
    st.markdown("Mapeie e execute ações de baixa complexidade e alto impacto imediato que não exigem validações complexas.")
    
    quick_wins = project_state.get("quick_wins", [])
    if not quick_wins:
        if st.button("Iniciar Novo Quadro de Quick Wins", disabled=read_only):
            quick_wins.append({
                "id": str(uuid.uuid4())[:8],
                "effect": "Quick Wins",
                "rows": []
            })
            project_state["quick_wins"] = quick_wins
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()
        return

    active_plano = quick_wins[0]
    rows = active_plano.get("rows", [])
    
    # Colunas de topo simplificadas (sem importação)
    colB, colZ = st.columns([2, 1])

    with colB:
        if not read_only and rows:
            with st.popover("🗑️ Apagar Todo o Quadro", use_container_width=True):
                st.warning("Tem certeza? Esta ação removerá TODAS as linhas de Quick Wins e não pode ser desfeita.")
                if st.button("Sim, apagar tudo!", type="primary"):
                    active_plano["rows"] = []
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.rerun()

    with colZ:
        z_c1, z_c2 = st.columns([1, 1.2])
        z_c1.markdown("<div style='margin-top: 5px; text-align: right; font-size: 0.9em; color: #555;'><b>🔍 Zoom:</b></div>", unsafe_allow_html=True)
        zoom_opt = z_c2.selectbox("Zoom_QW", ["50%", "65%", "70%", "80%", "90%", "100%"], index=5, label_visibility="collapsed")

    # Injeção de CSS
    z_val = zoom_opt.replace('%', '')
    st.markdown(
        f'<style>'
        f'.block-container {{ zoom: {z_val}% !important; }}'
        f'div[data-testid="stHorizontalBlock"]:has(> div:nth-child(12)) {{ min-width: 2200px !important; }}'
        f'[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(12)) {{ min-width: 0 !important; }}'
        f'div[data-testid="stHorizontalBlock"]:has(> div:nth-child(12)) > div:nth-child(12) div[data-testid="stButton"] button {{ padding: 2px 8px !important; min-height: 0px !important; line-height: 1.5; }}'
        f'</style>'
        f'<div style="min-width:2200px; height:1px; visibility:hidden;"></div>',
        unsafe_allow_html=True
    )

    st.markdown("---")
    
    if not rows:
        st.info("Quadro vazio. Adicione uma linha manualmente abaixo para começar a registrar seus Quick Wins.")
        if st.button("➕ Adicionar Primeiro Quick Win", disabled=read_only):
            rows.append({
                "row_id": str(uuid.uuid4())[:12],
                "sol_id": str(uuid.uuid4())[:8],
                "is_parent": True,
                "id_display": "QW1",
                "causa": "Oportunidade Identificada",
                "solucao": "Ação de Ganho Rápido",
                "acao": "", "onde": "", "ini_prev": "", "fim_prev": "",
                "ini_real": "", "fim_real": "", "quem": "", "status": "Não Iniciado",
                "version_ai": 0
            })
            active_plano["rows"] = rows
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()
        return

    # Lógica de Cálculo de Status (Copiada do 5W2H)
    hoje = datetime.now().date()
    total_acoes = 0
    atrasadas = 0
    concluidas = 0
    df_chart = []
    has_concluido_error = False
    
    for r in rows:
        st_val = r.get("status", "Não Iniciado")
        if st_val == "Concluído" and not r.get("fim_real", "").strip():
            st_val = "Em Andamento"
            r["status"] = st_val
            if f"qwa_stat_{r['row_id']}" in st.session_state:
                st.session_state[f"qwa_stat_{r['row_id']}"] = st_val
            has_concluido_error = True
        
        f_p = r.get("fim_prev", "").strip()
        diff_days = None
        if f_p:
            try:
                dt_obj = pd.to_datetime(f_p, format="%d/%m/%Y").date()
                diff_days = (dt_obj - hoje).days
            except:
                pass
        
        cor = ""
        if st_val == "Concluído":
            cor = "#4CAF50"
            concluidas += 1
        else:
            if st_val == "Atrasado":
                cor = "#F44336"
                atrasadas += 1
            else:
                if diff_days is not None:
                    if diff_days < 0 and st_val not in ["Cancelado"]:
                        cor = "#F44336"
                        atrasadas += 1
                        st_val = "Atrasado"
                        r["status"] = st_val
                        if f"qwa_stat_{r['row_id']}" in st.session_state:
                            st.session_state[f"qwa_stat_{r['row_id']}"] = st_val
                    elif 0 <= diff_days <= 3 and st_val not in ["Cancelado"]:
                        cor = "#FFC107"
        
        r["_cor"] = cor
        total_acoes += 1
        df_chart.append({"Status": st_val if cor != "#F44336" else ("Atrasado" if st_val != "Concluído" else st_val)})
        
    # --- DASHBOARD KPI ---
    st.markdown("### Resumo Executivo - Quick Wins")
    kpi_d1, kpi_d2, kpi_d3, kpi_chart = st.columns([1, 1, 1, 2])
    kpi_d1.metric("Total de Ações", total_acoes)
    kpi_d2.metric("Ações Atrasadas", atrasadas)
    perc = round((concluidas / total_acoes) * 100) if total_acoes > 0 else 0
    kpi_d3.metric("Ações Concluídas", f"{perc}%")
    
    with kpi_chart:
        if df_chart:
            pdf = pd.DataFrame(df_chart)
            conta = pdf.groupby("Status").size().reset_index(name="Quantidade")
            color_scale = alt.Scale(domain=["Não Iniciado", "Em Andamento", "Atrasado", "Concluído", "Cancelado"], 
                                    range=["#9E9E9E", "#2196F3", "#F44336", "#4CAF50", "#607D8B"])
            donut = alt.Chart(conta).mark_arc(innerRadius=40).encode(
                theta=alt.Theta(field="Quantidade", type="quantitative"),
                color=alt.Color(field="Status", type="nominal", scale=color_scale),
                tooltip=["Status", "Quantidade"]
            ).properties(height=180, width=300)
            st.altair_chart(donut, use_container_width=True)

    status_options = ["Não Iniciado", "Em Andamento", "Atrasado", "Concluído", "Cancelado"]
    filtro_status = st.multiselect("Filtrar Quick Wins:", options=status_options, default=[], help="Deixe em branco para exibir todas.")
    
    if has_concluido_error:
        st.warning("⚠️ Algumas ações não puderam ser marcadas como 'Concluídas'. Você precisa preencher a data no campo 'Fim (Real)' primeiro!")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_weights = [0.6, 1.8, 2.2, 3.2, 1.2, 1.0, 1.0, 1.0, 1.0, 1.2, 1.1, 0.8]
    headers = st.columns(col_weights)
    labels = ["ID", "Oportunidade", "Solução Ganho Rápido", "Ação", "Onde", "Início (Prev)", "Fim (Prev)", "Início (Real)", "Fim (Real)", "Quem", "Status", "⚙️"]
    for hc, lab in zip(headers, labels):
         hc.markdown(f'<div style="background-color: #001C59; color: white; padding: 10px 5px; border-radius: 6px; text-align: center; font-size: 0.85em; display: flex; align-items: center; justify-content: center; height: 100%;"><b>{lab}</b></div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    dirty = False
    for i, row in enumerate(rows):
        c_status = row.get("status", "Não Iniciado")
        if filtro_status and c_status not in filtro_status and row.get("_cor") != "#F44336":
            if "Atrasado" in filtro_status and row.get("_cor") == "#F44336": pass
            else: continue

        cols = st.columns(col_weights)
        h = 82
        is_parent = row.get("is_parent", False)
        rid = row.get("row_id")
        v = row.get("version_ai", 0)

        c_bg = row.get("_cor", "")
        c_font = "white" if c_bg else "inherit"
        bg_style = f"background-color: {c_bg}; color: {c_font};" if c_bg else ""
        cols[0].markdown(f"<div style='text-align:center; padding: 15px 5px; border-radius: 6px; margin-top: 5px; {bg_style}'><b>{row.get('id_display', '')}</b></div>", unsafe_allow_html=True)

        if is_parent:
            cols[1].text_area("causa", value=row.get("causa", ""), key=f"qw_causa_{rid}", height=h, label_visibility="collapsed", disabled=read_only)
            cols[2].text_area("sol", value=row.get("solucao", ""), key=f"qw_sol_{rid}", height=h, label_visibility="collapsed", disabled=read_only)
        else:
            cols[1].markdown("")
            cols[2].markdown("")

        # Keys com qwa_ prefixo
        acao_val = cols[3].text_area("acao", value=row.get("acao", ""), key=f"qwa_acao_{rid}_{v}", height=h, label_visibility="collapsed", disabled=read_only)
        onde_val = cols[4].text_area("onde", value=row.get("onde", ""), key=f"qwa_onde_{rid}", height=h, label_visibility="collapsed", disabled=read_only)
        inip_val = cols[5].text_input("inip", value=row.get("ini_prev", ""), key=f"qwa_inip_{rid}", label_visibility="collapsed", disabled=read_only)
        fimp_val = cols[6].text_input("fimp", value=row.get("fim_prev", ""), key=f"qwa_fimp_{rid}", label_visibility="collapsed", disabled=read_only)
        inir_val = cols[7].text_input("inir", value=row.get("ini_real", ""), key=f"qwa_inir_{rid}", label_visibility="collapsed", disabled=read_only)
        fimr_val = cols[8].text_input("fimr", value=row.get("fim_real", ""), key=f"qwa_fimr_{rid}", label_visibility="collapsed", disabled=read_only)
        quem_val = cols[9].text_area("quem", value=row.get("quem", ""), key=f"qwa_quem_{rid}", height=h, label_visibility="collapsed", disabled=read_only)
        stat_val = cols[10].selectbox("stat", status_options, index=status_options.index(c_status), key=f"qwa_stat_{rid}", label_visibility="collapsed", disabled=read_only)

        with cols[11]:
            if not read_only:
                b1, b2, b3 = st.columns(3)
                if b1.button("➕", key=f"qw_add_{rid}"):
                    rows.insert(i + 1, {
                        "row_id": str(uuid.uuid4())[:12], "sol_id": row.get("sol_id"), "is_parent": False,
                        "id_display": row.get("id_display", "-"), "causa": row.get("causa", ""), "solucao": row.get("solucao", ""),
                        "acao": "", "onde": "", "ini_prev": "", "fim_prev": "", "ini_real": "", "fim_real": "", "quem": "", "status": "Não Iniciado", "version_ai": 0
                    })
                    dirty = True
                if b3.button("🗑️", key=f"qw_del_{rid}"):
                    if is_parent and (i + 1 < len(rows)) and not rows[i+1].get("is_parent", True): rows[i+1]["is_parent"] = True
                    rows.pop(i)
                    dirty = True
                if b2.button("🤖", key=f"qw_ai_{rid}"):
                    import coach_extensions
                    acoes = coach_extensions.suggest_acao_5w2h(project_state, row.get("causa", ""), row.get("solucao", ""))
                    if acoes:
                        row["acao"] = acoes[0]
                        row["version_ai"] = row.get("version_ai", 0) + 1
                        for idx_adic, ax in enumerate(acoes[1:]):
                            rows.insert(i + 1 + idx_adic, {
                                "row_id": str(uuid.uuid4())[:12], "sol_id": row.get("sol_id"), "is_parent": False,
                                "id_display": row.get("id_display", "-"), "causa": row.get("causa", ""), "solucao": row.get("solucao", ""),
                                "acao": ax, "onde": "", "ini_prev": "", "fim_prev": "", "ini_real": "", "fim_real": "", "quem": "", "status": "Não Iniciado", "version_ai": 0
                            })
                    dirty = True
                    st.session_state["ai_generated_warning"] = "✨ Quick Wins gerados pela IA!"

        st.markdown("<hr style='margin: 5px 0px; border-color: #e0e0e0;'>", unsafe_allow_html=True)

    if not read_only:
        if st.button("➕ Adicionar Nova Oportunidade"):
            rows.append({
                "row_id": str(uuid.uuid4())[:12], "sol_id": str(uuid.uuid4())[:8], "is_parent": True,
                "id_display": f"QW{len([r for r in rows if r.get('is_parent')]) + 1}",
                "causa": "Nova Oportunidade", "solucao": "Nova Solução",
                "acao": "", "onde": "", "ini_prev": "", "fim_prev": "", "ini_real": "", "fim_real": "", "quem": "", "status": "Não Iniciado", "version_ai": 0
            })
            dirty = True

    if dirty:
        active_plano["rows"] = rows
        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
        st.rerun()
