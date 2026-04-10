import streamlit as st
import uuid
import copy
from db import upsert_project

def get_new_id():
    return f"ps_{uuid.uuid4().hex[:8]}"

def render_grafico_dispersao(solucoes_list):
    import altair as alt
    import pandas as pd
    
    if not solucoes_list:
        return None
        
    data = []
    for s in solucoes_list:
        desc = s.get("desc", "").strip()
        if not desc: continue
        # Inverted scores for X and Y plotting: we want 5=easy, 5=cheap. 
        # But wait! user said "para calculo do score, fazer com que a nota considerada seja a oposta... Do ponto de vista do grafico, no warnig, seguir a logica igual a matriz esforço imacto existente"
        # In Ishikawa, Impacto is Y, Esforço is X.
        c = int(s.get("c_score", 3))
        e  = int(s.get("e_score", 3))
        i  = int(s.get("i_score", 3))
        c_inv = 6 - c
        e_inv = 6 - e
        
        # Color based on Custo (1=Cheap, 5=Expensive)
        c_color = "🔴 Alto Custo" if c >= 4 else ("🟢 Baixo Custo" if c <= 2 else "🟡 Custo Médio")
        
        data.append({
            "ID_Vis": str(s.get("_num_only", "")),
            "Solução": desc[:40] + ("..." if len(desc)>40 else ""),
            "Impacto": i,
            "Esforço": e,
            "Custo Cor": c_color,
            "Score": s.get("final_score", 0),
            "Desc Full": desc
        })
        
    if not data: return None
        
    df = pd.DataFrame(data)
    
    # Domains 1 to 5
    base = alt.Chart(df).encode(
        x=alt.X('Esforço:Q', scale=alt.Scale(domain=[1, 5]), title="Esforço (1=Fácil, 5=Difícil)"),
        y=alt.Y('Impacto:Q', scale=alt.Scale(domain=[1, 5]), title="Impacto (1=Baixo, 5=Alto)")
    )
    
    scatter = base.mark_circle(size=400, opacity=0.8).encode(
        color=alt.Color('Custo Cor:N', scale=alt.Scale(domain=["🟢 Baixo Custo", "🟡 Custo Médio", "🔴 Alto Custo"], range=["green", "#d4af37", "red"])),
        tooltip=['ID_Vis', 'Solução', 'Impacto', 'Esforço', 'Custo Cor', 'Score', 'Desc Full']
    )
    
    text = base.mark_text(align='center', baseline='middle', color='white', fontSize=12, fontWeight='bold').encode(
        text='ID_Vis:N'
    )
    
    # Adding lines for quadrants
    line_x = alt.Chart(pd.DataFrame({'x': [3]})).mark_rule(strokeDash=[4, 4], color='gray').encode(x='x:Q')
    line_y = alt.Chart(pd.DataFrame({'y': [3]})).mark_rule(strokeDash=[4, 4], color='gray').encode(y='y:Q')
    
    layer = scatter + text
    return (layer + line_x + line_y).properties(width='container', height=400)

def extract_valid_causes(plano_validacao_rows):
    """
    Search for valid causes and format their ancestral path.
    A valid cause is one with status == 'validada'.
    Ancestral path looks up parent_wbs to build a string.
    """
    valid_causes = []
    
    # helper for finding full path
    def get_path(row):
        path = [row.get("causa", "")]
        curr_parent = row.get("parent_wbs")
        while curr_parent:
            p_row = next((r for r in plano_validacao_rows if r["wbs"] == curr_parent), None)
            if p_row:
                path.insert(0, p_row.get("causa", ""))
                curr_parent = p_row.get("parent_wbs")
            else:
                break
        return " ➞ ".join([p for p in path if p])

    for row in plano_validacao_rows:
        if row.get("status") == "validada":
            # Strip IA tag if it slipped through
            import re
            c_text = re.sub(r"^ia[\s\-:]+", "", row.get("causa", ""), flags=re.IGNORECASE).strip()
            path_text = get_path(row)
            path_text = re.sub(r"^ia[\s\-:]+", "", path_text, flags=re.IGNORECASE).strip()
            
            valid_causes.append({
                "causa_id": row.get("id"),
                "wbs": row.get("wbs"),
                "causa_text": c_text,
                "ancestrais": path_text,
                "solucoes": []
            })
            
    return valid_causes

def render_plano_solucoes_ui(project_state, pid, db, read_only):
    st.subheader("💡 Plano de Soluções")
    st.markdown("Para cada causa raiz validada, gere soluções contra a causa-raiz, avalie pontuações de Esforço, Custo e Impacto, e selecione as definições finais para o Plano de Ação.")

    planos_sol = project_state.get("planos_solucoes", [])
    planos_val = project_state.get("planos_validacao", [])

    if not planos_sol:
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Criar Plano de Soluções Vazio", disabled=read_only):
                planos_sol.append({
                    "id": get_new_id(),
                    "effect": "Plano Independente",
                    "p_c_peso": 1, "p_e_peso": 1, "p_i_peso": 1,
                    "causas": []
                })
                project_state["planos_solucoes"] = planos_sol
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.rerun()
        with c2:
            pv_opts = {p["id"]: p["effect"] for p in planos_val}
            if pv_opts:
                with st.popover("Importar Causas vinda da Validação", use_container_width=True):
                    sel_pv_id = st.selectbox("Selecione o Plano de Validação:", options=list(pv_opts.keys()), format_func=lambda x: pv_opts[x])
                    if st.button("Gerar Plano 📥"):
                        target_pv = next((p for p in planos_val if p["id"] == sel_pv_id), None)
                        extracted = extract_valid_causes(target_pv.get("rows", []))
                        if not extracted:
                            st.error("Este plano não possui NENHUMA causa com status de ✅ Validada. Valide-as primeiro.")
                        else:
                            planos_sol.append({
                                "id": get_new_id(),
                                "effect": target_pv["effect"],
                                "ref_pv_id": sel_pv_id,
                                "p_c_peso": 1, "p_e_peso": 1, "p_i_peso": 1,
                                "causas": extracted
                            })
                            project_state["planos_solucoes"] = planos_sol
                            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                            st.rerun()
            else:
                st.info("Nenhum Plano de Validação encontrado para importação.")
        return

    # Select Macro Plan
    p_opts = {p["id"]: p["effect"] for p in planos_sol}
    p_opts_with_global = {"GLOBAL": "🌎 Plano Global Consolidado (Read-only)"}
    p_opts_with_global.update(p_opts)
    
    default_p_idx = 0
    if "ps_selected_macro_id" in st.session_state and st.session_state["ps_selected_macro_id"] in p_opts_with_global:
        default_p_idx = list(p_opts_with_global.keys()).index(st.session_state["ps_selected_macro_id"])

    c_sel, c_btn = st.columns([3, 1])
    with c_sel:
        def fmt_macro(x):
            if x == "GLOBAL": return p_opts_with_global[x]
            return f"[{x[:4]}] {p_opts_with_global[x]}"
        selected_macro_id = st.selectbox("Selecione a Coleção de Soluções (Macro):", options=list(p_opts_with_global.keys()), format_func=fmt_macro, index=default_p_idx)
        st.session_state["ps_selected_macro_id"] = selected_macro_id
    with c_btn:
        with st.popover("➕ Novo Plano Macro", use_container_width=True):
            if st.button("Plano Vazio"):
                planos_sol.append({
                    "id": get_new_id(), "effect": f"Plano {len(planos_sol)+1}",
                    "p_c_peso": 1, "p_e_peso": 1, "p_i_peso": 1,
                    "causas": []
                })
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.rerun()
            pv_opts = {p["id"]: p["effect"] for p in planos_val}
            if pv_opts:
                sel_pv_id_n = st.selectbox("Do Plano Validado:", options=list(pv_opts.keys()), format_func=lambda x: pv_opts[x], key="novo_de_pv")
                if st.button("Gerar do Plano Validação"):
                    target_pv = next((p for p in planos_val if p["id"] == sel_pv_id_n), None)
                    extracted = extract_valid_causes(target_pv.get("rows", []))
                    if not extracted: st.error("Nenhuma causa validada.")
                    else:
                        planos_sol.append({"id": get_new_id(), "effect": target_pv["effect"], "ref_pv_id": sel_pv_id_n, "p_c_peso": 1, "p_e_peso": 1, "p_i_peso": 1, "causas": extracted})
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.rerun()

    if selected_macro_id == "GLOBAL":
        st.info("Visão global com TODAS as soluções geradas nos planos. Você pode desmarcar a caixa caso desista de uma solução prioritária.")
        todas_solucoes_eleitas = []
        global_seq = 1
        for p in planos_sol:
            for c in p.get("causas", []):
                for s in c.get("solucoes", []):
                    s["_display_id"] = f"{global_seq} - {c.get('wbs', 'X')}"
                    s["_num_only"] = global_seq
                    global_seq += 1
                    todas_solucoes_eleitas.append(s)
        
        grafico = render_grafico_dispersao(todas_solucoes_eleitas)
        if grafico:
            st.altair_chart(grafico, use_container_width=True)
            
            st.markdown("---")
            st.markdown("### Soluções Eleitas (Global)")
            
            # Header Row
            g_headers = st.columns([0.85, 1.2, 4, 1.5, 1.5, 1.5, 1.5])
            g_labels = ["Eleger", "ID", "Solução", "Custo (5=Caro)", "Esforço (5=Difícil)", "Impacto (5=Alto)", "Score Total"]
            for hc, lab in zip(g_headers, g_labels):
                hc.markdown(f'<div style="background-color: #001C59; color: white; padding: 15px 5px; border-radius: 6px; text-align: center; font-size: 0.85em; height: 100%; display: flex; align-items: center; justify-content: center;"><b>{lab}</b></div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            dirty_global = False
            for i, sol in enumerate(todas_solucoes_eleitas):
                cols = st.columns([0.85, 1.2, 4, 1.5, 1.5, 1.5, 1.5])
                
                # Checkbox interagível na primeira coluna
                new_sel = cols[0].checkbox("V", value=sol.get("selecionada", True), key=f"globsel_{sol.get('id', i)}", label_visibility="collapsed")
                if new_sel != sol.get("selecionada"):
                    sol["selecionada"] = new_sel
                    dirty_global = True
                
                cols[1].markdown(f"**{sol.get('_display_id', '')}**")
                cols[2].write(sol.get("desc", ""))
                cols[3].write(f"**Custo:** {sol.get('c_score', 0)}")
                cols[4].write(f"**Esforço:** {sol.get('e_score', 0)}")
                cols[5].write(f"**Impacto:** {sol.get('i_score', 0)}")
                cols[6].write(f"**Score:** {sol.get('final_score', 0)}")
                st.caption(sol.get("comentario", ""))
                st.markdown("---")
                
            if dirty_global:
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.rerun()
        else:
            st.warning("Nenhuma solução foi 'Eleita' (Flegada) em todo o projeto ainda.")
        return
    
    active_macro = next((p for p in planos_sol if p["id"] == selected_macro_id), None)
    if not active_macro: return

    # ConfigPesos Global para o Macro
    with st.expander("⚖ Configuração de Pesos para o Score (1 a 5)"):
        st.caption("Ajuste a importância de cada variável. O Score final = (Esforço x PesoE) + (Custo x PesoC) + (Impacto x PesoI). Ex: Se Custo não for tão importante financeiramente para a empresa agora, diminua seu peso.")
        wp_c1, wp_c2, wp_c3 = st.columns(3)
        p_c = wp_c1.number_input("Peso do Custo", min_value=1, max_value=5, value=active_macro.get("p_c_peso", 1), key=f"wp_c_{selected_macro_id}", disabled=read_only)
        p_e = wp_c2.number_input("Peso do Esforço", min_value=1, max_value=5, value=active_macro.get("p_e_peso", 1), key=f"wp_e_{selected_macro_id}", disabled=read_only)
        p_i = wp_c3.number_input("Peso do Impacto", min_value=1, max_value=5, value=active_macro.get("p_i_peso", 1), key=f"wp_i_{selected_macro_id}", disabled=read_only)
        if (p_c != active_macro.get("p_c_peso") or p_e != active_macro.get("p_e_peso") or p_i != active_macro.get("p_i_peso")) and not read_only:
            active_macro["p_c_peso"] = p_c
            active_macro["p_e_peso"] = p_e
            active_macro["p_i_peso"] = p_i
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])

    st.markdown("---")

    causas = active_macro.get("causas", [])
    
    # Gerar a numeração sequencial iterando em todas as causas do plano
    local_seq = 1
    for cx in causas:
        for sx in cx.get("solucoes", []):
            sx["_display_id"] = f"{local_seq} - {cx.get('wbs', 'X')}"
            sx["_num_only"] = local_seq
            local_seq += 1
            
    if not causas:
        st.info("Nenhuma causa mapeada neste plano.")
        if st.button("➕ Adicionar Causa Manual"):
            causas.append({
                "causa_id": str(uuid.uuid4()), "causa_text": "Nova Causa Manual", "ancestrais": "", "solucoes": []
            })
            active_macro["causas"] = causas
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()
        return

    # Select Active Causa (The Tabs substitute)
    def format_causa_opt(c_idx):
        c = causas[c_idx]
        has_sol = "✅" if len(c.get("solucoes", [])) > 0 else "⭕"
        return f"{has_sol} [{c.get('wbs', 'M')}] {c.get('causa_text')}"

    c_idx_opts = list(range(len(causas)))
    sel_causa_idx = st.selectbox("Focar nas Soluções da Causa:", options=c_idx_opts, format_func=format_causa_opt)
    
    if st.button("➕ Adicionar Causa Manual", disabled=read_only):
        causas.append({"causa_id": str(uuid.uuid4()), "causa_text": "Nova Causa Manual", "wbs": "M", "ancestrais": "", "solucoes": []})
        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
        st.rerun()

    active_causa = causas[sel_causa_idx]

    # Mostra a trilogia
    if active_causa.get("ancestrais"):
        st.caption(f"**Contexto/Trilha:** {active_causa['ancestrais']}")
    
    # Campo para ele editar o nome da causa caso digitado manualmente
    n_causa = st.text_input("Causa a resolver:", value=active_causa.get("causa_text", ""), disabled=read_only, key=f"t_c_{selected_macro_id}_{sel_causa_idx}")
    if n_causa != active_causa.get("causa_text", "") and not read_only:
        active_causa["causa_text"] = n_causa
        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])

    solucoes = active_causa.get("solucoes", [])
    st.markdown("<br>", unsafe_allow_html=True)
    c_btn1, c_btn2 = st.columns([1, 4])
    with c_btn1:
        if st.button("✨ Sugerir 5 Soluções", disabled=read_only or not active_causa.get("causa_text"), use_container_width=True):
            from coach_extensions import suggest_5_solucoes_basico
            with st.spinner("Gerando banco de soluções..."):
                resp_json = suggest_5_solucoes_basico(project_state, active_macro.get("effect"), active_causa.get("ancestrais"), active_causa.get("causa_text"))
                if resp_json and isinstance(resp_json, list):
                    for obj in resp_json:
                        c = int(obj.get("custo", 3))
                        e = int(obj.get("esforco", 3))
                        i = int(obj.get("impacto", 3))
                        c_inv = 6 - c
                        e_inv = 6 - e
                        solucoes.append({
                            "id": str(uuid.uuid4()),
                            "selecionada": False,
                            "desc": obj.get("solucao", ""),
                            "c_score": c,
                            "e_score": e,
                            "i_score": i,
                            "comentario": obj.get("comentario", ""),
                            "final_score": (c_inv * active_macro.get("p_c_peso", 1)) + (e_inv * active_macro.get("p_e_peso", 1)) + (i * active_macro.get("p_i_peso", 1))
                        })
                    active_causa["solucoes"] = solucoes
                    # Força nova geração
                    st.session_state["ps_gen_ver"] = st.session_state.get("ps_gen_ver", 0) + 1
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.rerun()
                else:
                    st.error("Erro na resposta da IA.")
    
    # CSS Custom Grid (1400px scrollable) targeting only the main matrix Grid (blocks with at least 8 columns) to prevent blowing up the Weights Header
    st.markdown(
        f'<style>'
        f'div[data-testid="stHorizontalBlock"]:has(> div:nth-child(8)) {{ min-width: 1400px !important; }}'
        f'[data-testid="stColumn"] div[data-testid="stHorizontalBlock"]:has(> div:nth-child(8)) {{ min-width: 0 !important; }}'
        f'</style>'
        f'<div style="min-width:1400px; height:1px; visibility:hidden;"></div>',
        unsafe_allow_html=True
    )

    # Header Row
    headers = st.columns([0.85, 1.2, 4, 1.5, 1.5, 1.5, 1.5, 4, 0.8])
    labels = ["Eleger", "ID", "Solução", "Custo (5=Caro)", "Esforço (5=Difícil)", "Impacto (5=Alto)", "Score Total", "Análise / Prós e Contras", "Ação"]
    for hc, lab in zip(headers, labels):
        hc.markdown(f'<div style="background-color: #001C59; color: white; padding: 15px 5px; border-radius: 6px; text-align: center; font-size: 0.85em; height: 100%; display: flex; align-items: center; justify-content: center;"><b>{lab}</b></div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    gen_ver = st.session_state.get("ps_gen_ver", 0)
    
    dirty = False

    for s_idx, sol in enumerate(solucoes):
        cols = st.columns([0.85, 1.2, 4, 1.5, 1.5, 1.5, 1.5, 4, 0.8])
        
        h = 100
        # Checkbox
        new_sel = cols[0].checkbox("V", value=sol.get("selecionada", False), key=f"sel_{selected_macro_id}_{sel_causa_idx}_{s_idx}", disabled=read_only, label_visibility="collapsed")
        
        # ID Visual
        cols[1].markdown(f"**{sol.get('_display_id', '')}**")
        
        # Desc Text
        new_desc = cols[2].text_area("desc", value=sol.get("desc", ""), key=f"dsc_{selected_macro_id}_{sel_causa_idx}_{s_idx}_v{gen_ver}", height=h, label_visibility="collapsed", disabled=read_only)
        
        # Numeric Inputs
        new_c = cols[3].number_input("C", min_value=1, max_value=5, value=sol.get("c_score", 3), key=f"c_{selected_macro_id}_{sel_causa_idx}_{s_idx}_v{gen_ver}", label_visibility="collapsed", disabled=read_only)
        new_e = cols[4].number_input("E", min_value=1, max_value=5, value=sol.get("e_score", 3), key=f"e_{selected_macro_id}_{sel_causa_idx}_{s_idx}_v{gen_ver}", label_visibility="collapsed", disabled=read_only)
        new_i = cols[5].number_input("I", min_value=1, max_value=5, value=sol.get("i_score", 3), key=f"i_{selected_macro_id}_{sel_causa_idx}_{s_idx}_v{gen_ver}", label_visibility="collapsed", disabled=read_only)
        
        # Total Score logic: Invert Cost and Effort for the Score.
        old_score = sol.get("final_score", 0)
        c_inv = 6 - new_c
        e_inv = 6 - new_e
        calc_score = (c_inv * active_macro.get("p_c_peso", 1)) + (e_inv * active_macro.get("p_e_peso", 1)) + (new_i * active_macro.get("p_i_peso", 1))
        
        # Adjusting color logic
        max_possible = 5 * (active_macro.get("p_c_peso",1) + active_macro.get("p_e_peso",1) + active_macro.get("p_i_peso",1))
        color_score = "green" if calc_score >= (max_possible * 0.7) else ("orange" if calc_score >= (max_possible * 0.4) else "red")
        cols[6].markdown(f"<div style='text-align:center; padding-top:20px; font-size:24px; color:{color_score}; font-weight:bold;' title='Esforço Invertido + Custo Invertido + Impacto'>{calc_score}</div>", unsafe_allow_html=True)
        
        # Comentario Text
        new_com = cols[7].text_area("com", value=sol.get("comentario", ""), key=f"com_{selected_macro_id}_{sel_causa_idx}_{s_idx}_v{gen_ver}", height=h, label_visibility="collapsed", disabled=read_only)
        
        if (new_sel != sol.get("selecionada") or 
            new_desc != sol.get("desc") or 
            new_c != sol.get("c_score") or 
            new_e != sol.get("e_score") or 
            new_i != sol.get("i_score") or 
            calc_score != old_score or 
            new_com != sol.get("comentario")):
            
            sol["selecionada"] = new_sel
            sol["desc"] = new_desc
            sol["c_score"] = new_c
            sol["e_score"] = new_e
            sol["i_score"] = new_i
            sol["final_score"] = calc_score
            sol["comentario"] = new_com
            dirty = True

        # Botão de Ação / Lixeira
        with cols[8]:
            if not read_only:
                if st.button("🧠", key=f"bin1_{selected_macro_id}_{sel_causa_idx}_{s_idx}", help="Autocompletar Linha"):
                    from coach_extensions import suggest_1_solucao_basico
                    with st.spinner(".."):
                        resp_json = suggest_1_solucao_basico(project_state, active_macro.get("effect"), active_causa.get("ancestrais"), active_causa.get("causa_text"))
                        if resp_json:
                            sol["desc"] = resp_json.get("solucao", "")
                            sol["c_score"] = int(resp_json.get("custo", 3))
                            sol["e_score"] = int(resp_json.get("esforco", 3))
                            sol["i_score"] = int(resp_json.get("impacto", 3))
                            sol["comentario"] = resp_json.get("comentario", "")
                            st.session_state["ps_gen_ver"] = gen_ver + 1
                            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                            st.rerun()
                if st.button("🗑️", key=f"bd_{selected_macro_id}_{sel_causa_idx}_{s_idx}", help="Excluir Causa"):
                    solucoes.pop(s_idx)
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.rerun()

    if dirty:
        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
        st.rerun()

    if not read_only:
        if st.button("➕ Adicionar Nova Linha"):
            solucoes.append({
                "id": str(uuid.uuid4()), "selecionada": False, "desc": "", "c_score": 3, "e_score": 3, "i_score": 3, "final_score": 0, "comentario": ""
            })
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()

    # Chart block
    all_sols_this_causa = []
    for s in active_causa.get("solucoes", []):
        if s.get("desc", "").strip():
            all_sols_this_causa.append(s)
    
    if all_sols_this_causa:
        st.markdown("---")
        st.markdown(f"### Matriz Esforço x Impacto (Soluções da Causa: {active_causa.get('causa_text', '')})")
        graf_local = render_grafico_dispersao(all_sols_this_causa)
        if graf_local:
            st.altair_chart(graf_local, use_container_width=True)
