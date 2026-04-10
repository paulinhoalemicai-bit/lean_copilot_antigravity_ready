import streamlit as st
import uuid
import pandas as pd
import altair as alt
from datetime import datetime, date

def render_plano_acao_ui(project_state, pid, db, read_only):
    st.subheader("📋 Plano de Ação (5W2H)")
    st.markdown("Importe as soluções eleitas e as desdobre em pacotes de ações operacionais para acompanhamento contínuo.")
    
    planos_acao = project_state.get("planos_acao", [])
    if not planos_acao:
        if st.button("Iniciar Novo Plano em Branco", disabled=read_only):
            planos_acao.append({
                "id": str(uuid.uuid4())[:8],
                "effect": "Plano Principal",
                "rows": []
            })
            project_state["planos_acao"] = planos_acao
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()
        return

    active_plano = planos_acao[0]
    rows = active_plano.get("rows", [])
    
    colA, colB, colZ = st.columns([1.5, 1, 1])
    with colA:
        if st.button("📥 Importar Soluções Eleitas (do Plano de Soluções)", disabled=read_only, help="Puxa todas as soluções com a flag marcada como 'Eleita'"):
            planos_sol = project_state.get("planos_solucoes", [])
            importados = 0
            for ps in planos_sol:
                for c in ps.get("causas", []):
                    for s in c.get("solucoes", []):
                        if s.get("selecionada", False):
                            # Evitar duplicação da raiz da solução
                            exists = any(r.get("sol_id") == s.get("id") and r.get("is_parent", False) for r in rows)
                            if not exists:
                                parent_causa = c.get("causa_text", "Causa Desconhecida")
                                rows.append({
                                    "row_id": str(uuid.uuid4())[:12],
                                    "sol_id": s.get("id"),
                                    "is_parent": True, # A primeira linha de uma certa solução é o pai (onde Causa e Solução aparecem)
                                    "id_display": s.get("_display_id", "-"),
                                    "causa": parent_causa,
                                    "solucao": s.get("desc", ""),
                                    "acao": "",
                                    "onde": "",
                                    "ini_prev": "",
                                    "fim_prev": "",
                                    "ini_real": "",
                                    "fim_real": "",
                                    "quem": "",
                                    "status": "Não Iniciado",
                                    "version_ai": 0
                                })
                                importados += 1
            if importados > 0:
                active_plano["rows"] = rows
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.success(f"✅ {importados} soluções importadas com sucesso!")
                st.rerun()
            else:
                st.warning("⚠️ Nenhuma nova Solução Eleita foi encontrada para importação.")

    with colB:
        if not read_only and rows:
            with st.popover("🗑️ Apagar Todo o Plano", use_container_width=True):
                st.warning("Tem certeza? Esta ação removerá TODAS as linhas do plano 5W2H e não pode ser desfeita.")
                if st.button("Sim, apagar tudo!", type="primary"):
                    active_plano["rows"] = []
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.rerun()

    with colZ:
        z_c1, z_c2 = st.columns([1, 1.2])
        z_c1.markdown("<div style='margin-top: 5px; text-align: right; font-size: 0.9em; color: #555;'><b>🔍 Zoom:</b></div>", unsafe_allow_html=True)
        zoom_opt = z_c2.selectbox("Zoom", ["50%", "65%", "70%", "80%", "90%", "100%"], index=5, label_visibility="collapsed", help="Ajusta o tamanho visual temporário para enquadrar planos grandes na tela sem precisar usar as configurações do Chrome.")

    # Injeção de CSS para o Grid Dinâmico Gigante e Botões Inline
    z_val = zoom_opt.replace('%', '')
    st.markdown(
        f'<style>'
        f'.block-container {{ zoom: {z_val}% !important; }}'
        f'div[data-testid="stHorizontalBlock"]:has(> div:nth-child(12)) {{ min-width: 2200px !important; }}'
        f'[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(12)) {{ min-width: 0 !important; }}'
        f'/* Reduz padding dos botões de ação para caber lado a lado */'
        f'div[data-testid="stHorizontalBlock"]:has(> div:nth-child(12)) > div:nth-child(12) div[data-testid="stButton"] button {{ padding: 2px 8px !important; min-height: 0px !important; line-height: 1.5; }}'
        f'</style>'
        f'<div style="min-width:2200px; height:1px; visibility:hidden;"></div>',
        unsafe_allow_html=True
    )

    st.markdown("---")
    
    if not rows:
        st.info("Plano vazio. Clique no botão de importação acima ou adicione uma linha manualmente abaixo para construir sua base.")
        if st.button("➕ Adicionar Linha Manual", disabled=read_only):
            rows.append({
                "row_id": str(uuid.uuid4())[:12],
                "sol_id": str(uuid.uuid4())[:8],
                "is_parent": True,
                "id_display": "-",
                "causa": "Causa Manual",
                "solucao": "Solução Manual",
                "acao": "", "onde": "", "ini_prev": "", "fim_prev": "",
                "ini_real": "", "fim_real": "", "quem": "", "status": "Não Iniciado"
            })
            active_plano["rows"] = rows
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()
        return

    # Lógica de Cálculo de Status
    hoje = datetime.now().date()
    # Adicionamos um cálculo interno simulado antes de desenhar o grid para o KPI e Filtros
    total_acoes = 0
    atrasadas = 0
    concluidas = 0
    df_chart = []
    has_concluido_error = False
    
    # Atualiza status e cores em tempo real do loop pre-render
    for r in rows:
        st_val = r.get("status", "Não Iniciado")
        
        # Validação: Só pode estar concluído se houver data real de fim
        if st_val == "Concluído" and not r.get("fim_real", "").strip():
            st_val = "Em Andamento"
            r["status"] = st_val
            if f"paa_stat_{r['row_id']}" in st.session_state:
                st.session_state[f"paa_stat_{r['row_id']}"] = st_val
            has_concluido_error = True
        
        # Parse da data de forma limpa dd/mm/yyyy
        f_p = r.get("fim_prev", "").strip()
        diff_days = None
        if f_p:
            try:
                dt_obj = pd.to_datetime(f_p, format="%d/%m/%Y").date()
                diff_days = (dt_obj - hoje).days
            except:
                pass
        
        # Inteligência da cor (Traffic Light / e Atraso Automático virtual)
        cor = "" # neutro
        if st_val == "Concluído":
            cor = "#4CAF50" # Verde Escuro
            concluidas += 1
        else:
            if st_val == "Atrasado":
                cor = "#F44336" # Vermelho
                atrasadas += 1
            else:
                if diff_days is not None:
                    if diff_days < 0 and st_val not in ["Cancelado"]:
                        cor = "#F44336" # Vermelho auto
                        atrasadas += 1
                        # Forçar o status para atrasado (atualiza memória)
                        st_val = "Atrasado"
                        r["status"] = st_val
                        if f"paa_stat_{r['row_id']}" in st.session_state:
                            st.session_state[f"paa_stat_{r['row_id']}"] = st_val
                    elif 0 <= diff_days <= 3 and st_val not in ["Cancelado"]:
                        cor = "#FFC107" # Amarelo (Vence em 3 dias ou hoje)
        
        # Armazena estado visual temporário na row para o render mais abaixo
        r["_cor"] = cor
        total_acoes += 1
        df_chart.append({"Status": st_val if cor != "#F44336" else ("Atrasado" if st_val != "Concluído" else st_val)})
        
    # --- DASHBOARD KPI ---
    st.markdown("### Resumo Executivo do Plano")
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

    # --- FILTRO POR STATUS ---
    status_options = ["Não Iniciado", "Em Andamento", "Atrasado", "Concluído", "Cancelado"]
    filtro_status = st.multiselect("Filtrar ações exibidas:", options=status_options, default=[], help="Deixe em branco para exibir todas.")
    
    if has_concluido_error:
        st.warning("⚠️ Algumas ações não puderam ser marcadas como 'Concluídas'. Você precisa preencher a data no campo 'Fim (Real)' primeiro!")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Grid Setup Redimensionado para comportar os botões agrupados
    col_weights = [0.6, 1.8, 2.2, 3.2, 1.2, 1.0, 1.0, 1.0, 1.0, 1.2, 1.1, 0.8]
    headers = st.columns(col_weights)
    labels = ["ID", "Causa", "Solução", "Ação", "Onde", "Início (Prev)", "Fim (Prev)", "Início (Real)", "Fim (Real)", "Quem", "Status", "⚙️"]
    for hc, lab in zip(headers, labels):
         hc.markdown(f'<div style="background-color: #001C59; color: white; padding: 10px 5px; border-radius: 6px; text-align: center; font-size: 0.85em; display: flex; align-items: center; justify-content: center; height: 100%;"><b>{lab}</b></div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    dirty = False

    # Vamos agrupar as linhas por sol_id para renderizá-las em sequência
    # Assumimos que o estado foi montado em blocos, mas para segurança, vamos renderizar na ordem exata que estão na lista `rows`.
    # A ordem será gerenciada pelas manutenções de list (insert).

    # Um dicionário com os labels oficiais
    status_options = ["Não Iniciado", "Em Andamento", "Atrasado", "Concluído", "Cancelado"]

    for i, row in enumerate(rows):
        c_status = row.get("status", "Não Iniciado")
        if filtro_status and c_status not in filtro_status and row.get("_cor") != "#F44336":
            # Força exibição dos atrasados implícitos se "Atrasado" marcado, caso contrário pula
            if "Atrasado" in filtro_status and row.get("_cor") == "#F44336":
                pass
            else:
                continue

        cols = st.columns(col_weights)
        h = 82 # Aumentado em ~20% a partir dos 68 anteriores

        # Se não for parent (linhas "filhas"), não renderizamos fundo nem campo, apenas texto vazio
        is_parent = row.get("is_parent", False)

        # ID com Traffic Light dinâmico
        c_bg = row.get("_cor", "") # Pegar variável pré gerada acima
        c_font = "white" if c_bg else "inherit"
        bg_style = f"background-color: {c_bg}; color: {c_font};" if c_bg else ""
        cols[0].markdown(f"<div style='text-align:center; padding: 15px 5px; border-radius: 6px; margin-top: 5px; {bg_style}'><b>{row.get('id_display', '')}</b></div>", unsafe_allow_html=True)

        if is_parent:
            cols[1].text_area("causa", value=row.get("causa", ""), key=f"pa_causa_{i}", height=h, label_visibility="collapsed", disabled=read_only)
            cols[2].text_area("sol", value=row.get("solucao", ""), key=f"pa_sol_{i}", height=h, label_visibility="collapsed", disabled=read_only)
        else:
            cols[1].markdown("") # Em branco
            cols[2].markdown("") # Em branco

        # Campos editáveis que acionam sync implícito
        # Eles ficarão no final do script pelo sync_dynamic_tables ou on_change explícito?
        # É melhor ter todos registrados no sync_dynamic_tables. Para isso, os `key` devem seguir um padrão!
        # Usaremos: paa_{campo}_{row_id} para não ter risco de key changes ao inserir linhas.
        rid = row.get("row_id")
        v = row.get("version_ai", 0)

        acao_val = cols[3].text_area("acao", value=row.get("acao", ""), key=f"paa_acao_{rid}_{v}", height=h, label_visibility="collapsed", disabled=read_only)
        onde_val = cols[4].text_area("onde", value=row.get("onde", ""), key=f"paa_onde_{rid}", height=h, label_visibility="collapsed", disabled=read_only)
        inip_val = cols[5].text_input("inip", value=row.get("ini_prev", ""), key=f"paa_inip_{rid}", label_visibility="collapsed", disabled=read_only)
        fimp_val = cols[6].text_input("fimp", value=row.get("fim_prev", ""), key=f"paa_fimp_{rid}", label_visibility="collapsed", disabled=read_only)
        inir_val = cols[7].text_input("inir", value=row.get("ini_real", ""), key=f"paa_inir_{rid}", label_visibility="collapsed", disabled=read_only)
        fimr_val = cols[8].text_input("fimr", value=row.get("fim_real", ""), key=f"paa_fimr_{rid}", label_visibility="collapsed", disabled=read_only)
        quem_val = cols[9].text_area("quem", value=row.get("quem", ""), key=f"paa_quem_{rid}", height=h, label_visibility="collapsed", disabled=read_only)
        
        c_status = row.get("status", "Não Iniciado")
        if c_status not in status_options:
            c_status = "Não Iniciado"
        stat_val = cols[10].selectbox("stat", status_options, index=status_options.index(c_status), key=f"paa_stat_{rid}", label_visibility="collapsed", disabled=read_only)

        # Atualização imediata no estado (local sync sem rerun pra não arrastar a página, quem cuida é o st.session_state)
        # O ideal é usar o sync do app.py

        with cols[11]:
            if not read_only:
                b1, b2, b3 = st.columns(3)
                if b1.button("➕", key=f"pa_add_{rid}", help="Adicionar Ação desdobrada nesta mesma Solução"):
                    # Insert a new child row directly below this one
                    filha = {
                        "row_id": str(uuid.uuid4())[:12],
                        "sol_id": row.get("sol_id"),
                        "is_parent": False,
                        "id_display": row.get("id_display", "-"),
                        "causa": row.get("causa", ""),
                        "solucao": row.get("solucao", ""),
                        "acao": "", "onde": "", "ini_prev": "", "fim_prev": "",
                        "ini_real": "", "fim_real": "", "quem": "", "status": "Não Iniciado"
                    }
                    rows.insert(i + 1, filha)
                    dirty = True

                if b3.button("🗑️", key=f"pa_del_{rid}"):
                    # Deletar esta linha.
                    if is_parent and (i + 1 < len(rows)) and not rows[i+1].get("is_parent", True) and rows[i+1].get("sol_id") == row.get("sol_id"):
                        rows[i+1]["is_parent"] = True
                    
                    rows.pop(i)
                    dirty = True
                
                if b2.button("🤖", key=f"pa_ai_{rid}", help="A IA preencherá automaticamente campos de Ação (O que / Como) para esta solução!"):
                    import coach_extensions
                    c_txt = row.get("causa", "")
                    s_txt = row.get("solucao", "")
                    with st.spinner("Doutor Lean desdobrando ações..."):
                        acoes_sugeridas = coach_extensions.suggest_acao_5w2h(project_state, c_txt, s_txt)
                        if acoes_sugeridas:
                            row["acao"] = acoes_sugeridas[0]
                            row["version_ai"] = row.get("version_ai", 0) + 1
                            # As próximas viram filhas em sequencia logo abaixo desta que foi clicada
                            for idx_adic, ax in enumerate(acoes_sugeridas[1:]):
                                nv_id = str(uuid.uuid4())[:12]
                                nova_filha = {
                                    "row_id": nv_id,
                                    "sol_id": row.get("sol_id"),
                                    "is_parent": False,
                                    "id_display": row.get("id_display", "-"),
                                    "causa": row.get("causa", ""),
                                    "solucao": row.get("solucao", ""),
                                    "acao": ax, "onde": "", "ini_prev": "", "fim_prev": "",
                                    "ini_real": "", "fim_real": "", "quem": "", "status": "Não Iniciado",
                                    "version_ai": 0
                                }
                                rows.insert(i + 1 + idx_adic, nova_filha)
                        dirty = True
                        st.session_state["ai_generated_warning"] = "✨ ⚠️ Linhas criadas pela IA com sucesso!"

        st.markdown("<hr style='margin: 5px 0px; border-color: #e0e0e0;'>", unsafe_allow_html=True)

    if not read_only:
        if st.button("➕ Adicionar Nova Causa/Solução Manual"):
            rows.append({
                "row_id": str(uuid.uuid4())[:12],
                "sol_id": str(uuid.uuid4())[:8],
                "is_parent": True,
                "id_display": "-",
                "causa": "Causa Manual",
                "solucao": "Solução Manual",
                "acao": "", "onde": "", "ini_prev": "", "fim_prev": "",
                "ini_real": "", "fim_real": "", "quem": "", "status": "Não Iniciado"
            })
            dirty = True

    if dirty:
        active_plano["rows"] = rows
        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
        st.rerun()

