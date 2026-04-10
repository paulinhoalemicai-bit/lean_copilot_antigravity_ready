import streamlit as st
import uuid

def render_plano_acao_ui(project_state, pid, db, read_only):
    st.subheader("📋 Plano de Ação (5W2H)")
    st.markdown("Importe as soluções eleitas e as desdobre em pacotes de ações operacionais para acompanhamento contínuo.")
    
    planos_acao = project_state.get("planos_acao", [])
    if not planos_acao:
        if st.button("Iniciar Novo Plano de Ação 5W2H", disabled=read_only):
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
    
    colA, colB = st.columns([2, 1])
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
                                parent_causa = c.get("descricao", "Causa Desconhecida")
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
                                    "status": "Não Iniciado"
                                })
                                importados += 1
            if importados > 0:
                active_plano["rows"] = rows
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.success(f"✅ {importados} soluções importadas com sucesso!")
                st.rerun()
            else:
                st.warning("⚠️ Nenhuma nova Solução Eleita foi encontrada para importação.")

    # Injeção de CSS para o Grid Dinâmico Gigante
    st.markdown(
        f'<style>'
        f'div[data-testid="stHorizontalBlock"]:has(> div:nth-child(12)) {{ min-width: 2200px !important; }}'
        f'[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(12)) {{ min-width: 0 !important; }}'
        f'</style>'
        f'<div style="min-width:2200px; height:1px; visibility:hidden;"></div>',
        unsafe_allow_html=True
    )

    st.markdown("---")
    
    if not rows:
        st.info("Nenhuma solução importada ainda. Clique no botão acima para construir sua base.")
        return

    # Header Row com 12 colunas (sendo a última para os botões)
    col_weights = [0.6, 2.0, 2.5, 3.0, 1.2, 1.0, 1.0, 1.0, 1.0, 1.2, 1.1, 0.4]
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
        cols = st.columns(col_weights)
        h = 100

        # Se não for parent (linhas "filhas"), não renderizamos fundo nem campo, apenas texto vazio
        is_parent = row.get("is_parent", False)

        # ID
        cols[0].markdown(f"<div style='text-align:center; padding-top: 30px;'><b>{row.get('id_display', '')}</b></div>", unsafe_allow_html=True)

        if is_parent:
            cols[1].text_area("causa", value=row.get("causa", ""), key=f"pa_causa_{i}", height=h, label_visibility="collapsed", disabled=True)
            cols[2].text_area("sol", value=row.get("solucao", ""), key=f"pa_sol_{i}", height=h, label_visibility="collapsed", disabled=True)
        else:
            cols[1].markdown("") # Em branco
            cols[2].markdown("") # Em branco

        # Campos editáveis que acionam sync implícito
        # Eles ficarão no final do script pelo sync_dynamic_tables ou on_change explícito?
        # É melhor ter todos registrados no sync_dynamic_tables. Para isso, os `key` devem seguir um padrão!
        # Usaremos: paa_{campo}_{row_id} para não ter risco de key changes ao inserir linhas.
        rid = row.get("row_id")

        acao_val = cols[3].text_area("acao", value=row.get("acao", ""), key=f"paa_acao_{rid}", height=h, label_visibility="collapsed", disabled=read_only)
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
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                if st.button("➕", key=f"pa_add_{rid}", help="Adicionar Ação desdobrada nesta mesma Solução"):
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

                if st.button("🗑️", key=f"pa_del_{rid}"):
                    # Deletar esta linha. Se for parent, e houver filhas embaixo, a próxima filha vira parent?
                    # Ou deita a árvore toda? Vamos simplificar: deleta a linha. Se deletar a parent e sobrar filha, paciência, o aluno conserta. Mas vamos adotar a lógica: se é parent e a de baixo é mesma sol e não-parent, herda.
                    if is_parent and (i + 1 < len(rows)) and not rows[i+1].get("is_parent", True) and rows[i+1].get("sol_id") == row.get("sol_id"):
                        rows[i+1]["is_parent"] = True
                    
                    rows.pop(i)
                    dirty = True

        st.markdown("---")

    if dirty:
        active_plano["rows"] = rows
        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
        st.rerun()

