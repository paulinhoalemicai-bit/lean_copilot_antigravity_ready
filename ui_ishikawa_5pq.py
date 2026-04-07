import streamlit as st
import uuid
import copy

def get_new_id():
    return str(uuid.uuid4())[:8]

def get_default_ishikawa_spines():
    return [
        {"id": get_new_id(), "category": "Meio ambiente", "causes": []},
        {"id": get_new_id(), "category": "Material", "causes": []},
        {"id": get_new_id(), "category": "Método", "causes": []},
        {"id": get_new_id(), "category": "Medida", "causes": []},
        {"id": get_new_id(), "category": "Mão de obra", "causes": []},
        {"id": get_new_id(), "category": "Máquina", "causes": []}
    ]

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
    
    # Migração para a estrutura de Lista (se ainda for um dict estático)
    if isinstance(active_ish.get("spines"), dict):
        d_spines = active_ish["spines"]
        active_ish["spines"] = [
            d_spines.get("top1", {"category": "Meio ambiente", "causes": []}),
            d_spines.get("top2", {"category": "Material", "causes": []}),
            d_spines.get("top3", {"category": "Método", "causes": []}),
            d_spines.get("bot1", {"category": "Medida", "causes": []}),
            d_spines.get("bot2", {"category": "Mão de obra", "causes": []}),
            d_spines.get("bot3", {"category": "Máquina", "causes": []})
        ]
        for sp in active_ish["spines"]:
            if "id" not in sp: sp["id"] = get_new_id()
    
    if "spines" not in active_ish:
        active_ish["spines"] = get_default_ishikawa_spines()

    st.markdown("<br>", unsafe_allow_html=True)

    # Hack CSS para habilitar Barra de Rolagem (Scroll) Horizontal nas categorias
    st.markdown("""<style>
    div[data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
        padding-bottom: 20px !important;
        scrollbar-width: thin;
    }
    div[data-testid="column"] {
        min-width: 300px !important;
        flex: 0 0 auto !important;
    }
    input[aria-label^="Cat "] {
        background-color: #8ce1f0 !important;
        color: #001C59 !important;
        font-weight: bold !important;
    }
    /* Comprime o espaçamento das colunas verticais de causa suavemente sem cortar as caixas */
    div[data-testid="stVerticalBlock"] > div {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
        gap: 0.1rem !important;
    }
    </style>""", unsafe_allow_html=True)

    # BOTÕES DE CONTROLE GERAIS: Importar e Adicionar
    c_imp, c_add = st.columns(2)
    with c_imp:
        if st.button("📥 Preencher com Problema do Project Charter", disabled=read_only):
            val = project_state.get("charter", {}).get("problem", "")
            if val:
                active_ish["effect"] = val
                st.session_state[f"eff_{active_ish['id']}"] = val
                project_state["ishikawas"] = ishikawas
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.rerun()
            else:
                st.warning("O Project Charter ainda não tem um problema definido.")
    with c_add:
        if st.button("➕ Adicionar Nova Categoria na Espinha", disabled=read_only):
            active_ish["spines"].append({"id": get_new_id(), "category": "Nova Categoria", "causes": [{"causa": ""}, {"causa": ""}, {"causa": ""}]})
            project_state["ishikawas"] = ishikawas
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()

    st.markdown("---")
    
    spines = active_ish["spines"]
    half = len(spines) // 2 + (len(spines) % 2)
    top_spines = spines[:half]
    bot_spines = spines[half:]

    # =========================================================
    # RENDERIZAÇÃO DO DIAGRAMA (Fishbone + Head à direita)
    # =========================================================
    col_fish, col_head = st.columns([4, 1], vertical_alignment="center")

    with col_fish:
        # ESPINHAS SUPERIORES
        if top_spines:
            st.markdown("<div style='text-align: center; color: #00AEEF; font-size: 20px; margin-bottom: -15px;'>Categorias (Superior)</div>", unsafe_allow_html=True)
            cols_top = st.columns(len(top_spines))
            for i, spine in enumerate(top_spines):
                with cols_top[i]:
                    c_lbl, c_del = st.columns([5, 1])
                    with c_lbl:
                        new_cat = st.text_input(f"Cat {spine['id']}", value=spine["category"], key=f"cat_{spine['id']}", disabled=read_only, label_visibility="collapsed")
                        spine["category"] = new_cat
                    with c_del:
                        if st.button("🗑️", key=f"del_{spine['id']}", help="Remover categoria", disabled=read_only):
                            active_ish["spines"] = [s for s in active_ish["spines"] if s["id"] != spine["id"]]
                            project_state["ishikawas"] = ishikawas
                            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                            st.rerun()
                    
                    if not read_only:
                        if st.button("➕", key=f"add_c_{spine['id']}", help="Adicionar nova causa extra"):
                            spine["causes"].append({"causa": ""})
                            project_state["ishikawas"] = ishikawas
                            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                            st.rerun()
                        
                    if not spine.get("causes"):
                        spine["causes"] = [{"causa": ""}, {"causa": ""}, {"causa": ""}]
                    for c_idx, cause in enumerate(spine.setdefault("causes", [])):
                        c_in, c_del_c = st.columns([6, 1])
                        with c_in:
                            new_val = st.text_area(f"Causa {c_idx}", value=cause.get("causa", ""), key=f"c_{spine['id']}_{c_idx}", disabled=read_only, label_visibility="collapsed", placeholder="Causa...", height=68)
                            cause["causa"] = new_val
                        with c_del_c:
                            if st.button("🗑️", key=f"del_c_{spine['id']}_{c_idx}", disabled=read_only):
                                spine["causes"].pop(c_idx)
                                project_state["ishikawas"] = ishikawas
                                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                st.rerun()
                    st.markdown("<div style='border-right: 3px solid #001C59; height: 35px; width: 50%; margin-bottom: 5px;'></div>", unsafe_allow_html=True)

        # ESPINHA DORSAL CENTRAL
        st.markdown("<div style='text-align: right; color: #001C59; font-size: 32px; font-weight: bold;'>──────────────────────────────────▶</div>", unsafe_allow_html=True)

        # ESPINHAS INFERIORES
        if bot_spines:
            cols_bot = st.columns(len(bot_spines))
            for i, spine in enumerate(bot_spines):
                with cols_bot[i]:
                    st.markdown("<div style='border-right: 3px solid #001C59; height: 35px; width: 50%; margin-bottom: 5px;'></div>", unsafe_allow_html=True)
                    
                    if not spine.get("causes"):
                        spine["causes"] = [{"causa": ""}, {"causa": ""}, {"causa": ""}]
                    
                    for c_idx, cause in enumerate(spine.setdefault("causes", [])):
                        c_in, c_del_c = st.columns([6, 1])
                        with c_in:
                            new_val = st.text_area(f"Causa {c_idx}", value=cause.get("causa", ""), key=f"cb_{spine['id']}_{c_idx}", disabled=read_only, label_visibility="collapsed", placeholder="Causa...", height=68)
                            cause["causa"] = new_val
                        with c_del_c:
                            if st.button("🗑️", key=f"del_cb_{spine['id']}_{c_idx}", disabled=read_only):
                                spine["causes"].pop(c_idx)
                                project_state["ishikawas"] = ishikawas
                                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                st.rerun()
                    if not read_only:
                        if st.button("➕", key=f"add_cb_{spine['id']}", help="Adicionar nova causa extra"):
                            spine["causes"].append({"causa": ""})
                            project_state["ishikawas"] = ishikawas
                            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                            st.rerun()

                    c_lbl, c_del = st.columns([5, 1])
                    with c_lbl:
                        new_cat = st.text_input(f"Cat {spine['id']}", value=spine["category"], key=f"cat_{spine['id']}", disabled=read_only, label_visibility="collapsed")
                        spine["category"] = new_cat
                    with c_del:
                        if st.button("🗑️", key=f"del_{spine['id']}", help="Remover categoria", disabled=read_only):
                            active_ish["spines"] = [s for s in active_ish["spines"] if s["id"] != spine["id"]]
                            project_state["ishikawas"] = ishikawas
                            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                            st.rerun()

    with col_head:
        st.markdown("**O PROBLEMA (Efeito)**")
        new_eff = st.text_area("O PROBLEMA", value=active_ish["effect"], key=f"eff_{active_ish['id']}", disabled=read_only, height=180, label_visibility="collapsed")
        active_ish["effect"] = new_eff

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
    
    branches = active_pq["branches"]
    
    # -------------------------------------------------------------
    # Algoritmo para calcular numeração WBS (ex: X1, X1.1, X1.2.1)
    # -------------------------------------------------------------
    wbs_labels = [[""] * len(row) for row in branches]
    
    def get_parent_wbs(r, c):
        if c == 0: return ""
        for row_idx in range(r, -1, -1):
            if row_idx < len(branches) and c-1 < len(branches[row_idx]) and branches[row_idx][c-1] is not None:
                return wbs_labels[row_idx][c-1]
        return ""

    child_counts = {}
    c0_count = 0
    for r in range(len(branches)):
        for c in range(len(branches[r])):
            if branches[r][c] is not None:
                if c == 0:
                    c0_count += 1
                    wbs_labels[r][c] = f"X{c0_count}"
                else:
                    parent_wbs = get_parent_wbs(r, c)
                    child_counts[parent_wbs] = child_counts.get(parent_wbs, 0) + 1
                    wbs_labels[r][c] = f"{parent_wbs}.{child_counts[parent_wbs]}"

    # Edição por cada ramificação ("Cadeia")
    for b_idx, branch in enumerate(branches):
        st.markdown("<div style='margin-bottom: 20px;'>", unsafe_allow_html=True)
        with st.container(border=False):
            num_cols = len(branch) + 1  
            bc = st.columns(num_cols)
            
            for p_idx, block in enumerate(branch):
                with bc[p_idx]:
                    if block is None:
                        st.markdown("<div style='text-align: right; color: gray; font-size: 24px; margin-top: 50px;'>↳</div>", unsafe_allow_html=True)
                    else:
                        label = wbs_labels[b_idx][p_idx]
                        c1, c2 = st.columns([4, 1])
                        with c1:
                            st.markdown(f"**[{label}]** ➡️")
                        with c2:
                            if st.button("🗑️", key=f"del_{selected_id}_{b_idx}_{p_idx}", disabled=read_only, help="Apagar daqui para frente"):
                                branch[:] = branch[:p_idx]
                                def is_empty_branch(br):
                                    return len(br) == 0 or all(x is None for x in br)
                                active_pq["branches"] = [b for b in active_pq["branches"] if not is_empty_branch(b)]
                                # Garante sempre uma origem viva:
                                if not active_pq["branches"]:
                                    active_pq["branches"] = [[{"pq": ""}]]
                                project_state["cinco_pqs"] = pqs
                                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                st.rerun()
                                
                        new_txt = st.text_area(f"hidden_{b_idx}_{p_idx}", value=block["pq"], key=f"txt_{selected_id}_{b_idx}_{p_idx}", height=120, disabled=read_only, label_visibility="collapsed")
                        block["pq"] = new_txt
                        
                        if not read_only:
                            if st.button("🔽 Avançar para Baixo", key=f"bif_{selected_id}_{b_idx}_{p_idx}"):
                                new_branch = [None] * p_idx + [{"pq": "Nova ramificação..."}]
                                active_pq["branches"].insert(b_idx + 1, new_branch)
                                project_state["cinco_pqs"] = pqs
                                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                st.rerun()
                    
            with bc[-1]:
                st.markdown("<br>", unsafe_allow_html=True)
                # Avançar horizontal pega o tamanho total da row sem padding lateral.
                if len(branch) > 0 and st.button("➡️ Avançar para o Lado", key=f"add_{selected_id}_{b_idx}", disabled=read_only):
                    branch.append({"pq": "Nova causa..."})
                    project_state["cinco_pqs"] = pqs
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.rerun()

    if not read_only:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🧨 Apagar Todo o Diagrama", use_container_width=True, type="secondary"):
            active_pq["branches"] = [[{"pq": ""}]]
            project_state["cinco_pqs"] = pqs
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()

    # Auto-save logic
    if pqs != original_pqs and not read_only:
        project_state["cinco_pqs"] = pqs
        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
