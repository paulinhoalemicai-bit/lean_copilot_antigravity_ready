import streamlit as st
import uuid

def get_new_id():
    return str(uuid.uuid4())[:8]

def render_tree(node_list, level, is_ishikawa, read_only, parent_id=None):
    """
    Função recursiva para desenhar galhos.
    node_list: lista de dicionários de causas {id, name, (category em Ishikawa), subcauses}
    """
    for i, node in enumerate(node_list):
        # Indentação baseada no level
        cols = st.columns([0.1 * level, 3, 1, 1, 1]) if level > 0 else st.columns([3, 1, 1, 1])
        c_text = cols[-4]
        c_add = cols[-3]
        c_up = cols[-2]
        c_del = cols[-1]

        with c_text:
            cat_str = f" [{node.get('category', '')}]" if is_ishikawa and level == 0 else ""
            prefix = "└─ " if level > 0 else "📌 "
            new_name = st.text_input(f"hidden_{node['id']}", value=node['name'], key=f"ti_{node['id']}", label_visibility="collapsed", disabled=read_only)
            if new_name != node['name']:
                node['name'] = new_name
                st.session_state["needs_save"] = True
            
            if is_ishikawa and level == 0 and not read_only:
                new_cat = st.selectbox(
                    "Categoria", 
                    ["Método", "Máquina", "Mão de Obra", "Materiais", "Medição", "Meio Ambiente"], 
                    index=["Método", "Máquina", "Mão de Obra", "Materiais", "Medição", "Meio Ambiente"].index(node.get("category", "Método")) if node.get("category") in ["Método", "Máquina", "Mão de Obra", "Materiais", "Medição", "Meio Ambiente"] else 0,
                    key=f"cat_{node['id']}",
                    label_visibility="collapsed"
                )
                if new_cat != node.get("category"):
                    node["category"] = new_cat
                    st.session_state["needs_save"] = True

        with c_add:
            if not read_only:
                if st.button("➕ Porquê?", key=f"add_{node['id']}", use_container_width=True):
                    if "subcauses" not in node:
                        node["subcauses"] = []
                    node["subcauses"].append({"id": get_new_id(), "name": "", "subcauses": []})
                    st.session_state["needs_save"] = True
                    st.rerun()
        
        with c_up:
            if not read_only and level == 0 and len(node_list) > 1:
                # Simples reordenamento na raiz
                if st.button("⬆️ Subir", key=f"up_{node['id']}", use_container_width=True):
                    if i > 0:
                        node_list[i], node_list[i-1] = node_list[i-1], node_list[i]
                        st.session_state["needs_save"] = True
                        st.rerun()

        with c_del:
            if not read_only:
                if st.button("🗑️ Del", key=f"del_{node['id']}", use_container_width=True):
                    node_list.pop(i)
                    st.session_state["needs_save"] = True
                    st.rerun()

        # Render children
        if 'subcauses' in node and node['subcauses']:
            render_tree(node['subcauses'], level + 1, is_ishikawa, read_only, node['id'])

def render_ishikawa_ui(project_state, pid, db, read_only):
    st.subheader("🐟 Diagrama de Causa e Efeito (Ishikawa)")
    
    ishikawas = project_state.get("ishikawas", [])
    
    if not ishikawas:
        st.info("Nenhum diagrama criado. Crie o seu primeiro!")
        new_effect = st.text_input("Qual o Efeito (Y) ou Problema que será analisado?", key="new_ishi_effect")
        if st.button("Criar Novo Ishikawa", disabled=read_only):
            if new_effect.strip():
                ishikawas.append({
                    "id": get_new_id(),
                    "effect": new_effect.strip(),
                    "causes": []
                })
                project_state["ishikawas"] = ishikawas
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.rerun()
        return

    # Seletor
    ishi_options = {ix["id"]: ix["effect"] for ix in ishikawas}
    cols = st.columns([3, 1])
    with cols[0]:
        selected_id = st.selectbox("Selecione o Ishikawa para visualizar/editar:", options=list(ishi_options.keys()), format_func=lambda x: ishi_options[x])
    with cols[1]:
        if st.button("➕ Criar Novo") and not read_only:
            ishikawas.append({
                "id": get_new_id(), "effect": f"Novo Efeito {len(ishikawas)+1}", "causes": []
            })
            project_state["ishikawas"] = ishikawas
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()
    
    # Encontrar o ativo
    active_ish = next((ish for ish in ishikawas if ish["id"] == selected_id), None)
    
    if active_ish:
        # Renomear Y
        new_eff = st.text_input("Efeito (Cabeça do Peixe)", value=active_ish["effect"], disabled=read_only)
        if new_eff != active_ish["effect"]:
            active_ish["effect"] = new_eff
            st.session_state["needs_save"] = True
            
        st.markdown("---")
        
        # Botões M's
        if not read_only:
            colA, colB = st.columns(2)
            with colA:
                if st.button("➕ Adicionar Causa Primária", use_container_width=True):
                    active_ish["causes"].append({"id": get_new_id(), "name": "", "category": "Método", "subcauses": []})
                    st.session_state["needs_save"] = True
                    st.rerun()
            with colB:
                if st.button("🛠️ Injetar Estrutura 6 M's Inicial", use_container_width=True):
                    ms = ["Método", "Máquina", "Mão de Obra", "Materiais", "Medição", "Meio Ambiente"]
                    for m in ms:
                        active_ish["causes"].append({"id": get_new_id(), "name": f"Exemplo em {m}", "category": m, "subcauses": []})
                    st.session_state["needs_save"] = True
                    st.rerun()

        with st.container(border=True):
            st.markdown("### Causas e Sub-Causas")
            st.session_state["needs_save"] = False
            render_tree(active_ish["causes"], 0, is_ishikawa=True, read_only=read_only)
            
            if st.session_state.get("needs_save") and not read_only:
                project_state["ishikawas"] = ishikawas
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.session_state["needs_save"] = False

        # Integração IA
        if st.button("🤖 Pedir Análise do Dr. Lean (Verificar Método)", disabled=read_only):
            from coach_extensions import suggest_ishikawa_eval
            from app import _filled_or_marker # if needed, but we can pass db global
            # just mock call or basic
            pass

def render_5pqs_ui(project_state, pid, db, read_only):
    st.subheader("🌳 Diagrama dos 5 Porquês")
    
    pqs = project_state.get("cinco_pqs", [])
    
    if not pqs:
        st.info("Nenhum 5 PQs criado. Comece analisando um Efeito ou Causa Primária!")
        new_effect = st.text_input("Qual o Problema (Topo da Árvore)?", key="new_pq_effect")
        if st.button("Criar Novos 5 Porquês", disabled=read_only):
            if new_effect.strip():
                pqs.append({
                    "id": get_new_id(),
                    "effect": new_effect.strip(),
                    "causes": []
                })
                project_state["cinco_pqs"] = pqs
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.rerun()
        return

    # Seletor
    pq_options = {ix["id"]: ix["effect"] for ix in pqs}
    cols = st.columns([3, 1])
    with cols[0]:
        selected_id = st.selectbox("Selecione o 5 PQs para visualizar:", options=list(pq_options.keys()), format_func=lambda x: pq_options[x])
    with cols[1]:
        if st.button("➕ Criar Novo") and not read_only:
            pqs.append({
                "id": get_new_id(), "effect": f"Nova Análise {len(pqs)+1}", "causes": []
            })
            project_state["cinco_pqs"] = pqs
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()
    
    active_pq = next((ix for ix in pqs if ix["id"] == selected_id), None)
    
    if active_pq:
        # Renomear Topo
        new_eff = st.text_input("Problema Central", value=active_pq["effect"], disabled=read_only)
        if new_eff != active_pq["effect"]:
            active_pq["effect"] = new_eff
            st.session_state["needs_save"] = True
            
        if not read_only:
            if st.button("➕ Adicionar 1º Porquê", use_container_width=True):
                active_pq["causes"].append({"id": get_new_id(), "name": "Por que...", "subcauses": []})
                st.session_state["needs_save"] = True
                st.rerun()

        with st.container(border=True):
            st.session_state["needs_save"] = False
            render_tree(active_pq["causes"], 0, is_ishikawa=False, read_only=read_only)
            
            if st.session_state.get("needs_save") and not read_only:
                project_state["cinco_pqs"] = pqs
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.session_state["needs_save"] = False
