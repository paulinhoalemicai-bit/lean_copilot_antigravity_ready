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
        st.write("")  # Placeholder
    with c_btn:
        if st.button("➕ Novo Diagrama", disabled=read_only, use_container_width=True):
            ishikawas.append({
                "id": get_new_id(), "effect": f"Análise Ishikawa {len(ishikawas)+1}", "spines": get_default_ishikawa_spines()
            })
            project_state["ishikawas"] = ishikawas
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()

    if len(ishikawas) > 1:
        st.markdown("<h3 style='color:#001C59;'>Navegue pela coleção Ishikawa</h3>", unsafe_allow_html=True)
        def get_eff(i_id):
            return next((x["effect"] for x in ishikawas if x["id"] == i_id), i_id)
        active_ish_id = st.selectbox("Selecione o Diagrama Ishikawa", [ish['id'] for ish in ishikawas], format_func=lambda i: get_eff(i))
        active_ish = next(ish for ish in ishikawas if ish['id'] == active_ish_id)
        # BIND GLOBAL: Diz ao app.py quem é o cara que está na tela sendo renderizado
        st.session_state["active_ish_id"] = active_ish["id"]
    else:
        active_ish = ishikawas[0]
        st.session_state["active_ish_id"] = active_ish["id"]
    
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

    # BOTÕES DE CONTROLE GERAIS: Importar e Adicionar e Apagar
    c_imp, c_6m, c_add, c_clr = st.columns([2, 1.5, 1.5, 1])
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
    with c_6m:
        if st.button("🛠️ Estruturar 6M's Padrão", help="Gera as 6 categorias padrão da manufatura", disabled=read_only):
            ms = ["Máquina", "Método", "Material", "Mão de Obra", "Meio Ambiente", "Medida"]
            for m in ms:
                active_ish["spines"].append({"id": get_new_id(), "category": m, "causes": [{"causa": ""}, {"causa": ""}, {"causa": ""}]})
            project_state["ishikawas"] = ishikawas
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()
    with c_add:
        if st.button("➕ Adicionar Categoria Manual", disabled=read_only):
            active_ish["spines"].append({"id": get_new_id(), "category": "Nova Categoria", "causes": [{"causa": ""}, {"causa": ""}, {"causa": ""}]})
            project_state["ishikawas"] = ishikawas
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()
    with c_clr:
        pop = st.popover("🧨 Apagar Diagrama", help="Exclui este Ishikawa para sempre!")
        pop.error("Tem certeza absoluta? Isso apagará este diagrama (cabeça e causas) permanentemente!")
        if pop.button("Sim, apagar! 🧨", key=f"clr_all_ish_{active_ish['id']}", disabled=read_only):
            project_state["ishikawas"] = [i for i in project_state["ishikawas"] if i["id"] != active_ish["id"]]
            if "active_ish_id" in st.session_state: del st.session_state["active_ish_id"]
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
                        new_cat = st.text_input(f"Cat {spine['id']}", value=spine.get("category", "Categoria"), key=f"cat_{spine['id']}", disabled=read_only, label_visibility="collapsed")
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
                        new_cat = st.text_input(f"Cat {spine['id']}", value=spine.get("category", "Categoria"), key=f"cat_{spine['id']}", disabled=read_only, label_visibility="collapsed")
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
        if new_eff != active_ish["effect"]:
            active_ish["effect"] = new_eff
            project_state["ishikawas"] = ishikawas
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()

    # Auto-save logic para as demais mudanças
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
    # Contador de gerações de IA: incluso no key dos text_areas para forçar widget novo após cada geração
    gen_ver = st.session_state.get("pq_gen_ver", 0)

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
    pq_opts_list = list(pq_options.keys())
    default_idx = 0
    if "cinco_pqs_selected_id" in st.session_state and st.session_state["cinco_pqs_selected_id"] in pq_opts_list:
        default_idx = pq_opts_list.index(st.session_state["cinco_pqs_selected_id"])

    c_sel, c_btn = st.columns([3, 1])
    with c_sel:
        selected_id = st.selectbox("Selecione o Fluxo 5 PQs:", options=pq_opts_list, format_func=lambda x: pq_options[x], label_visibility="collapsed", index=default_idx)
        st.session_state["cinco_pqs_selected_id"] = selected_id
    with c_btn:
        if st.button("➕ Novo Escopo", disabled=read_only, use_container_width=True):
            new_id = get_new_id()
            pqs.append({
                "id": new_id, "effect": f"Análise {len(pqs)+1}", "branches": [[{"pq": ""}]]
            })
            st.session_state["cinco_pqs_selected_id"] = new_id
            project_state["cinco_pqs"] = pqs
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()

    active_pq = next((ix for ix in pqs if ix["id"] == selected_id), None)
    if not active_pq: return
    
    if "branches" not in active_pq: active_pq["branches"] = [[{"pq": ""}]]

    st.markdown("<br>", unsafe_allow_html=True)
        
    c_eff, c_ai_eff = st.columns([4, 1])
    with c_eff:
        new_eff = st.text_input("Qual o Problema Central / Y desta análise?", value=active_pq["effect"], disabled=read_only)
        active_pq["effect"] = new_eff
    with c_ai_eff:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✨ Sugerir Raízes Iniciais", disabled=read_only, help="Dr Lean: Cria a 1ª camada de Porquês"):
            with st.spinner("Dr Lean pesquisando raízes primárias..."):
                from coach import suggest_5pq_branches
                roots = suggest_5pq_branches(project_state, active_pq["effect"], [], active_pq["branches"])
                if roots:
                    # Remove todas as branches completamente vazias/None antes de inserir raizes
                    def branch_is_empty(b):
                        return not any(c and c.get("pq", "").strip() for c in b if c is not None)
                    active_pq["branches"] = [b for b in active_pq["branches"] if not branch_is_empty(b)]
                    for rt in roots:
                        active_pq["branches"].append([{"pq": f"IA: {rt}"}])
                    project_state["cinco_pqs"] = pqs
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    # Incrementa o contador de geração para forçar keys NOVAS nos text_areas
                    # Com keys novas, Streamlit não tem cache e OBRIGATORIAMENTE usa value=block["pq"]
                    st.session_state["pq_gen_ver"] = st.session_state.get("pq_gen_ver", 0) + 1
                    st.rerun()
                    
    branches = active_pq["branches"]
    
    # Linha mais larga define o total de colunas (todas as rows usam o mesmo max_cols para alinhar)
    max_cols = max((len(b) for b in branches if b), default=1) + 1  # +1 para coluna de botões
    total_width = max(max_cols * 250, 900)  # 250px por coluna, mínimo 900px

    # ── Estratégia de rolagem horizontal (2 regras CSS) ─────────────────────
    # Regra 1: Força min-width em TODOS os stHorizontalBlock (linhas de branch)
    # Regra 2: Reseta para 0 nos stHorizontalBlock que estão DENTRO de um stColumn
    #          (colunaas internas de botões); como regra 2 é mais específica, ela vence.
    # O <div> invisível abaixo força a largura da página e ativa a scrollbar do browser.
    st.markdown(
        f'<style>'
        f'div[data-testid="stHorizontalBlock"] {{ min-width: {total_width}px !important; }}'
        f'[data-testid="stColumn"] div[data-testid="stHorizontalBlock"] {{ min-width: 0 !important; }}'
        f'</style>'
        f'<div style="min-width:{total_width}px; height:1px; visibility:hidden;"></div>',
        unsafe_allow_html=True
    )

    
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
        with st.container(border=False):
            # TODAS as rows usam o mesmo número de colunas (max_cols)
            # para garantir alinhamento vertical perfeito entre níveis
            bc = st.columns(max_cols)
            
            for p_idx in range(max_cols - 1):  # -1 porque última col é sempre de botões
                with bc[p_idx]:
                    if p_idx >= len(branch):
                        # Coluna fora do alcance desta linha: espaço em branco para alinhar
                        st.markdown("<div style='height:168px'></div>", unsafe_allow_html=True)
                        continue
                    
                    block = branch[p_idx]
                    if block is None:
                        st.markdown("<div style='text-align:right; color:gray; font-size:26px; margin-top:60px; padding-right:4px;'>↳</div>", unsafe_allow_html=True)
                    else:
                        label = wbs_labels[b_idx][p_idx]
                        st.markdown(
                            f"<div style='margin-bottom:4px;'><b>[{label}] ➡️</b></div>",
                            unsafe_allow_html=True
                        )
                        # Botões ➕ e 🗑️ lado a lado.
                        # IMPORTANTE: o st.container() cria um stVerticalBlock intermediário
                        # que impede que o st.columns(2) interno seja afetado pelo
                        # CSS de min-width que só alcança filhos DIRETOS do stVerticalBlock externo.
                        if not read_only:
                            with st.container():
                                btn_c = st.columns(2)
                                with btn_c[0]:
                                    btn_ins = st.button("➕", key=f"ins_{selected_id}_{b_idx}_{p_idx}",
                                                       help="Inserir célula ANTES (Desloca para direita)",
                                                       use_container_width=True)
                                with btn_c[1]:
                                    btn_del = st.button("🗑️", key=f"del_{selected_id}_{b_idx}_{p_idx}",
                                                       help="Apagar SOMENTE esta célula (Desloca para esquerda)",
                                                       use_container_width=True)
                            if btn_ins:
                                branch.insert(p_idx, {"pq": ""})
                                project_state["cinco_pqs"] = pqs
                                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                st.rerun()
                            if btn_del:
                                branch.pop(p_idx)
                                def is_empty_branch(br):
                                    return len(br) == 0 or all(x is None for x in br)
                                active_pq["branches"] = [b for b in active_pq["branches"] if not is_empty_branch(b)]
                                if not active_pq["branches"]:
                                    active_pq["branches"] = [[{"pq": ""}]]
                                project_state["cinco_pqs"] = pqs
                                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                st.rerun()

                        new_txt = st.text_area(
                            f"hidden_{b_idx}_{p_idx}",
                            value=block["pq"],
                            key=f"txt_{selected_id}_{b_idx}_{p_idx}_v{gen_ver}",
                            height=120, disabled=read_only, label_visibility="collapsed"
                        )
                        block["pq"] = new_txt
                        
                        if not read_only:
                            if st.button("🔽 Avançar para Baixo", key=f"bif_{selected_id}_{b_idx}_{p_idx}"):
                                new_branch = [None] * p_idx + [{"pq": ""}]
                                active_pq["branches"].insert(b_idx + 1, new_branch)
                                project_state["cinco_pqs"] = pqs
                                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                st.rerun()
                
            with bc[-1]:
                st.markdown("<br>", unsafe_allow_html=True)
                if len(branch) > 0:
                    if st.button("➡️ Avançar para o Lado", key=f"add_{selected_id}_{b_idx}", disabled=read_only):
                        branch.append({"pq": ""})
                        project_state["cinco_pqs"] = pqs
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.rerun()
                    
                    if st.button("✨ Explorar Hipóteses", key=f"ai_{selected_id}_{b_idx}", disabled=read_only, help="Dr Lean: Sugere continuações lógicas partindo daqui!"):
                        with st.spinner("Dr Lean estruturando..."):
                            from coach import suggest_5pq_branches
                            ctx_path = [b["pq"] for b in branch if b and b.get("pq", "").strip()]
                            answs = suggest_5pq_branches(project_state, active_pq["effect"], ctx_path, active_pq["branches"])
                            if answs:
                                branch.append({"pq": f"IA: {answs[0]}"})
                                prefix_len = len(branch) - 1
                                for extra_ans in answs[1:]:
                                    clone_prefix = [None] * prefix_len + [{"pq": f"IA: {extra_ans}"}]
                                    active_pq["branches"].insert(b_idx + 1, clone_prefix)
                                project_state["cinco_pqs"] = pqs
                                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                                # Incrementa contador para forçar keys novas nos text_areas
                                st.session_state["pq_gen_ver"] = st.session_state.get("pq_gen_ver", 0) + 1
                                st.rerun()

    if not read_only:
        st.markdown("<br>", unsafe_allow_html=True)
        pop_clr = st.popover("🧨 Apagar Todo o Diagrama", use_container_width=True)
        pop_clr.error("Certeza que deseja esmagar esta árvore inteira?")
        if pop_clr.button("Mecha na lixeira! 🧨", disabled=read_only, use_container_width=True):
            project_state["cinco_pqs"] = [i for i in project_state["cinco_pqs"] if i["id"] != active_pq["id"]]
            if "active_pq_id" in st.session_state: del st.session_state["active_pq_id"]
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()

    # Auto-save logic
    if pqs != original_pqs and not read_only:
        project_state["cinco_pqs"] = pqs
        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
