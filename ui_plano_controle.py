import streamlit as st
import uuid

def render_plano_controle_ui(project_state, pid, db_module, read_only):
    st.header("📋 Plano de Controle")
    st.markdown("O Plano de Controle consolida os métodos e responsáveis por sustentar os resultados das causas e indicadores do projeto a longo prazo.")
    
    t_ctrl, t_coach = st.tabs(["📝 Plano de Controle", "🧑‍🏫 Coach (Doutor Lean)"])
    
    with t_ctrl:
        # Initialization
        if "plano_controle" not in project_state:
            project_state["plano_controle"] = []
        
        planos = project_state["plano_controle"]
        
        # Container for Actions
        action_cols = st.columns([2, 2, 2, 6])
        
        with action_cols[0]:
            if st.button("➕ Adicionar Linha Manual", disabled=read_only, use_container_width=True):
                nova_linha = {
                    "id": str(uuid.uuid4())[:8],
                    "oq_checar": "",
                    "proc_chave": "",
                    "resp_proc": "",
                    "metodo": "Auditoria",
                    "formula": "",
                    "lim_min": "",
                    "meta": "",
                    "lim_max": "",
                    "fonte": "",
                    "tam_amostra": "",
                    "freq": "",
                    "resp_controle": "",
                    "local_armaz": "",
                    "acao_corr": "",
                    "acao_prev": "",
                    "obs": ""
                }
                planos.append(nova_linha)
                db_module.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.rerun()

        with action_cols[1]:
            if st.button("♻️ Importar Escopo", disabled=read_only, use_container_width=True, help="Importar o Y do Charter e as Causas Validadas."):
                y_charter = project_state.get("project_charter", {}).get("y", "")
                if y_charter:
                    planos.append({
                        "id": str(uuid.uuid4())[:8],
                        "oq_checar": f"[Y (Indicador Final)] {y_charter}",
                        "proc_chave": "", "resp_proc": "", "metodo": "Auditoria", "formula": "", "lim_min": "", "meta": "", "lim_max": "", "fonte": "", "tam_amostra": "", "freq": "", "resp_controle": "", "local_armaz": "", "acao_corr": "", "acao_prev": "", "obs": ""
                    })
                
                planos_sol = project_state.get("planos_solucoes", [])
                for p_sol in planos_sol:
                    for row in p_sol.get("rows", []):
                        if row.get("solucao_aprovada") and row.get("solucao", "").strip():
                            planos.append({
                                "id": str(uuid.uuid4())[:8],
                                "oq_checar": f"[X ({row.get('wbs')})] {row.get('solucao')}",
                                "proc_chave": "", "resp_proc": "", "metodo": "Auditoria", "formula": "", "lim_min": "", "meta": "", "lim_max": "", "fonte": "", "tam_amostra": "", "freq": "", "resp_controle": "", "local_armaz": "", "acao_corr": "", "acao_prev": "", "obs": ""
                            })
                            
                db_module.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.rerun()
                
        with action_cols[2]:
            if st.button("🚨 Apagar Tabela", disabled=read_only, use_container_width=True, type="primary"):
                project_state["plano_controle"] = []
                db_module.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.rerun()
                
        with action_cols[3]:
            if st.button("🪄 IA: Sugerir Ferramenta Completa", disabled=read_only, use_container_width=True):
                if not planos:
                    st.error("Por favor, importe o escopo ou crie uma linha antes para a IA saber o que controlar.")
                else:
                    import coach
                    with st.spinner("O Doutor Lean está preenchendo todos os Planos de Controle... (aguarde)"):
                        for i, row in enumerate(planos):
                            # so para linhas quase vazias (vamos julgar se ela tem menos de 3 campos)
                            campos_nulos = sum(1 for k in ["proc_chave", "formula", "meta", "tam_amostra", "acao_corr", "acao_prev"] if not row.get(k))
                            if campos_nulos >= 3:
                                resp = coach.suggest_plano_controle_row(project_state, row.get("oq_checar", ""))
                                for k, v in resp.items():
                                    if k in row and not row[k]:
                                        row[k] = v
                    db_module.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.rerun()
                    
        st.divider()
        
        if not planos:
            st.info("Nenhuma linha no Plano de Controle. Adicione uma nova ou importe do Escopo.")
            
        else:
            for idx, row in enumerate(planos):
                with st.expander(f"📁 {row.get('oq_checar', 'Item Vazio')} - {row.get('metodo', 'Auditoria')}", expanded=True):
                    c1, c2, c3, c4 = st.columns(4)
                    row["oq_checar"] = c1.text_input("O que deve ser checado", row.get("oq_checar", ""), key=f"pc_1_{idx}", disabled=read_only)
                    row["proc_chave"] = c2.text_input("Processo Chave", row.get("proc_chave", ""), key=f"pc_2_{idx}", disabled=read_only)
                    row["resp_proc"] = c3.text_input("Responsável pelo processo", row.get("resp_proc", ""), key=f"pc_3_{idx}", disabled=read_only)
                    row["metodo"] = c4.selectbox("Método de Controle", ["Auditoria", "Gráfico", "Visual", "Outros"], index=["Auditoria", "Gráfico", "Visual", "Outros"].index(row.get("metodo", "Auditoria")) if row.get("metodo", "Auditoria") in ["Auditoria", "Gráfico", "Visual", "Outros"] else 0, key=f"pc_4_{idx}", disabled=read_only)
                    
                    c5, c6, c7, c8 = st.columns(4)
                    row["formula"] = c5.text_input("Fórmula do Indicador", row.get("formula", ""), key=f"pc_5_{idx}", disabled=read_only)
                    row["lim_min"] = c6.text_input("Limite Mínimo", row.get("lim_min", ""), key=f"pc_6_{idx}", disabled=read_only)
                    row["meta"] = c7.text_input("Meta do indicador", row.get("meta", ""), key=f"pc_7_{idx}", disabled=read_only)
                    row["lim_max"] = c8.text_input("Limite Máximo", row.get("lim_max", ""), key=f"pc_8_{idx}", disabled=read_only)
                    
                    c9, c10, c11, c12 = st.columns(4)
                    row["fonte"] = c9.text_input("Fonte da informação", row.get("fonte", ""), key=f"pc_9_{idx}", disabled=read_only)
                    row["tam_amostra"] = c10.text_input("Tamanho da amostra", row.get("tam_amostra", ""), key=f"pc_10_{idx}", disabled=read_only)
                    row["freq"] = c11.text_input("Frequência de Medição", row.get("freq", ""), key=f"pc_11_{idx}", disabled=read_only)
                    row["resp_controle"] = c12.text_input("Responsável pelo controle", row.get("resp_controle", ""), key=f"pc_12_{idx}", disabled=read_only)
                    
                    c13, c14, c15, c16 = st.columns(4)
                    row["local_armaz"] = c13.text_input("Local armazenamento", row.get("local_armaz", ""), key=f"pc_13_{idx}", disabled=read_only)
                    row["acao_corr"] = c14.text_input("Ação corretiva", row.get("acao_corr", ""), key=f"pc_14_{idx}", disabled=read_only)
                    row["acao_prev"] = c15.text_input("Ação Preventiva", row.get("acao_prev", ""), key=f"pc_15_{idx}", disabled=read_only)
                    row["obs"] = c16.text_input("Observações", row.get("obs", ""), key=f"pc_16_{idx}", disabled=read_only)
                    
                    bcc1, bcc2 = st.columns([8, 2])
                    with bcc2:
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.button("🪄 Completar Linha", key=f"ai_{idx}", disabled=read_only, use_container_width=True, help="Gerar os 15 campos usando IA baseado no 'A Checar'."):
                                import coach
                                with st.spinner("Gerando dados para linha..."):
                                    resp = coach.suggest_plano_controle_row(project_state, row.get("oq_checar", ""))
                                    # Update fields
                                    for k, v in resp.items():
                                        if k in row and not row[k]: # Only fill empty fields
                                            row[k] = v
                                db_module.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                st.rerun()

                        with col_btn2:
                            if st.button("🗑️ Apagar", key=f"del_{idx}", disabled=read_only, use_container_width=True):
                                planos.pop(idx)
                                db_module.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                st.rerun()

            # Autosave for text inputs
            if not read_only:
                db_module.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])

            
    with t_coach:
        st.subheader("Análise do Coach")
        st.info("Aqui a inteligência analisará a consistência de todas as metas, amostras e métodos que você preencheu na tabela.")
        import coach_extensions
        coach_extensions.suggest_plano_controle_eval(project_state, pid, db_module, read_only)
