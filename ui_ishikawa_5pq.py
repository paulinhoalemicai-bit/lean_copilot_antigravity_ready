import streamlit as st
import uuid
import copy

def get_new_id():
    return str(uuid.uuid4())[:8]

def get_default_ishikawa_spines():
    return {
        "top1": {"category": "Meio ambiente", "causes": []},
        "top2": {"category": "Material", "causes": []},
        "top3": {"category": "Método", "causes": []},
        "bot1": {"category": "Medida", "causes": []},
        "bot2": {"category": "Mão de obra", "causes": []},
        "bot3": {"category": "Máquina", "causes": []}
    }

def render_ishikawa_ui(project_state, pid, db, read_only):
    st.subheader("🐟 Diagrama de Causa e Efeito (Ishikawa)")
    st.markdown("O diagrama de espinha de peixe clássico. Edite as categorias no topo/base de cada espinha e insira as sub-causas nas tabelas.")
    
    ishikawas = project_state.get("ishikawas", [])
    original_ishikawas = copy.deepcopy(ishikawas)
    
    if not ishikawas:
        if st.button("Criar Novo Diagrama de Ishikawa", disabled=read_only):
            ishikawas.append({
                "id": get_new_id(),
                "effect": "O Problema Principal Fica Aqui",
                "spines": get_default_ishikawa_spines()
            })
            project_state["ishikawas"] = ishikawas
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()
        return

    # Seletor
    ishi_options = {ix["id"]: ix["effect"] for ix in ishikawas}
    c_sel, c_btn = st.columns([3, 1])
    with c_sel:
        selected_id = st.selectbox("Selecione o Ishikawa:", options=list(ishi_options.keys()), format_func=lambda x: ishi_options[x], label_visibility="collapsed")
    with c_btn:
        if st.button("➕ Novo Diagrama", disabled=read_only, use_container_width=True):
            ishikawas.append({
                "id": get_new_id(), "effect": f"Análise Ishikawa {len(ishikawas)+1}", "spines": get_default_ishikawa_spines()
            })
            project_state["ishikawas"] = ishikawas
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()

    active_ish = next((ish for ish in ishikawas if ish["id"] == selected_id), None)
    if not active_ish: return
    
    if "spines" not in active_ish:
        active_ish["spines"] = get_default_ishikawa_spines()

    st.markdown("<br>", unsafe_allow_html=True)
    
    # =========================================================
    # ESPINHAS SUPERIORES
    # =========================================================
    st.markdown("<div style='text-align: center; color: #00AEEF; font-size: 20px; margin-bottom: -15px;'>M's Superiores</div>", unsafe_allow_html=True)
    cols_top = st.columns([1, 1, 1, 1])
    
    col_keys_top = ["top1", "top2", "top3"]
    for i, k in enumerate(col_keys_top):
        with cols_top[i]:
            spine = active_ish["spines"][k]
            new_cat = st.text_input(f"Categ {i+1}", value=spine["category"], key=f"cat_{active_ish['id']}_{k}", disabled=read_only, label_visibility="collapsed")
            spine["category"] = new_cat
            
            causas = spine.get("causes", [])
            df_causas = [{"Causas (Sub-causas com traço -)": c.get("causa", "")} for c in causas]
            if not df_causas: df_causas = [{"Causas (Sub-causas com traço -)": ""}] 
            
            edited_df = st.data_editor(
                df_causas, 
                num_rows="dynamic", 
                use_container_width=True, 
                key=f"ed_{active_ish['id']}_{k}",
                disabled=read_only
            )
            spine["causes"] = [{"causa": r["Causas (Sub-causas com traço -)"]} for r in edited_df if str(r.get("Causas (Sub-causas com traço -)", "")).strip()]
            
            st.markdown("<div style='text-align: center; font-size: 30px; line-height: 0.5;'>↘️</div>", unsafe_allow_html=True)

    # =========================================================
    # ESPINHA DORSAL CENTRAL
    # =========================================================
    c_line, c_head = st.columns([3, 1], vertical_alignment="center")
    with c_line:
        st.markdown("<div style='text-align: center; color: #001C59; font-size: 32px; font-weight: bold;'>──────────────────────────▶</div>", unsafe_allow_html=True)
    with c_head:
        new_eff = st.text_area("O PROBLEMA (Efeito)", value=active_ish["effect"], key=f"eff_{active_ish['id']}", disabled=read_only, height=100)
        active_ish["effect"] = new_eff

    # =========================================================
    # ESPINHAS INFERIORES
    # =========================================================
    cols_bot = st.columns([1, 1, 1, 1])
    col_keys_bot = ["bot1", "bot2", "bot3"]
    for i, k in enumerate(col_keys_bot):
        with cols_bot[i]:
            st.markdown("<div style='text-align: center; font-size: 30px; line-height: 0.5;'>↗️</div>", unsafe_allow_html=True)
            
            spine = active_ish["spines"][k]
            causas = spine.get("causes", [])
            df_causas = [{"Causas (Sub-causas com traço -)": c.get("causa", "")} for c in causas]
            if not df_causas: df_causas = [{"Causas (Sub-causas com traço -)": ""}] 
            
            edited_df = st.data_editor(
                df_causas, 
                num_rows="dynamic", 
                use_container_width=True, 
                key=f"ed_{active_ish['id']}_{k}",
                disabled=read_only
            )
            spine["causes"] = [{"causa": r["Causas (Sub-causas com traço -)"]} for r in edited_df if str(r.get("Causas (Sub-causas com traço -)", "")).strip()]

            new_cat = st.text_input(f"Categ {i+4}", value=spine["category"], key=f"cat_{active_ish['id']}_{k}", disabled=read_only, label_visibility="collapsed")
            spine["category"] = new_cat

    # Auto-save logic
    if ishikawas != original_ishikawas and not read_only:
        project_state["ishikawas"] = ishikawas
        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])



# =====================================================================
# 5 PORQUÊS EM LINHA
# =====================================================================

def render_5pqs_ui(project_state, pid, db, read_only):
    st.subheader("🌳 Cascata dos 5 Porquês")
    st.markdown("Estratégia visual em blocos. Cada linha abaixo representa um caminho investigativo de ramificações até a raiz.")

    pqs = project_state.get("cinco_pqs", [])
    original_pqs = copy.deepcopy(pqs)

    if not pqs:
        if st.button("Criar Nova Análise 5 Porquês", disabled=read_only):
            pqs.append({
                "id": get_new_id(),
                "effect": "Problema Inicial / Y",
                "branches": [
                    [{"pq": ""}, {"pq": ""}, {"pq": ""}]
                ]
            })
            project_state["cinco_pqs"] = pqs
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()
        return

    pq_options = {ix["id"]: ix["effect"] for ix in pqs}
    c_sel, c_btn = st.columns([3, 1])
    with c_sel:
        selected_id = st.selectbox("Selecione o Fluxo 5 PQs:", options=list(pq_options.keys()), format_func=lambda x: pq_options[x], label_visibility="collapsed")
    with c_btn:
        if st.button("➕ Novo Escopo", disabled=read_only, use_container_width=True):
            pqs.append({
                "id": get_new_id(), "effect": f"Análise {len(pqs)+1}", "branches": [[{"pq": ""}]]
            })
            project_state["cinco_pqs"] = pqs
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()

    active_pq = next((ix for ix in pqs if ix["id"] == selected_id), None)
    if not active_pq: return
    
    if "branches" not in active_pq: active_pq["branches"] = [[{"pq": ""}]]

    st.markdown("---")
    
    new_eff = st.text_input("Qual o Problema Central / Y desta análise?", value=active_pq["effect"], disabled=read_only)
    active_pq["effect"] = new_eff

    st.markdown("<br>", unsafe_allow_html=True)
    
    # Edição por cada ramificação ("Cadeia")
    for b_idx, branch in enumerate(active_pq["branches"]):
        with st.container(border=True):
            # Formar a coluna. Se a branch tem N eltos, precisamos de N+1 colunas (a última pro botão avançar)
            # Mas vamos pegar o len(branch) descartando os Nones para saber? Não, len(branch) total dita as colunas
            num_cols = len(branch) + 1  
            bc = st.columns(num_cols)
            
            last_valid_idx = -1
            for p_idx, block in enumerate(branch):
                with bc[p_idx]:
                    if block is None:
                        st.markdown("<div style='text-align: right; color: gray; font-size: 24px; margin-top: 50px;'>↳</div>", unsafe_allow_html=True)
                    else:
                        last_valid_idx = p_idx
                        if p_idx == 0:
                            st.markdown("**1º Porquê**")
                        else:
                            st.markdown(f"**{p_idx+1}º Porquê** ➡️")
                            
                        new_txt = st.text_area(f"hidden_{b_idx}_{p_idx}", value=block["pq"], key=f"txt_{selected_id}_{b_idx}_{p_idx}", height=120, disabled=read_only, label_visibility="collapsed")
                        branch[p_idx]["pq"] = new_txt
                        
                        if not read_only:
                            if st.button("🔽 Bifurcar", key=f"bif_{selected_id}_{b_idx}_{p_idx}"):
                                # Criar uma nova branch que é preenchida com Nones até este ponto, e começa no próximo
                                new_branch = [None] * (p_idx + 1) + [{"pq": "Nova causa paralela..."}]
                                active_pq["branches"].insert(b_idx + 1, new_branch)
                                project_state["cinco_pqs"] = pqs
                                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                st.rerun()
                    
            with bc[-1]:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("➕ Avançar", key=f"add_{selected_id}_{b_idx}", disabled=read_only):
                    branch.append({"pq": ""})
                    project_state["cinco_pqs"] = pqs
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.rerun()

    # Auto-save logic
    if pqs != original_pqs and not read_only:
        project_state["cinco_pqs"] = pqs
        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
