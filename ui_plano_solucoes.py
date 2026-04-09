import streamlit as st
import uuid
import copy
from db import upsert_project

def get_new_id():
    return f"ps_{uuid.uuid4().hex[:8]}"

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
            c_text = re.sub(r"^(?i)ia[\s\-:]+", "", row.get("causa", "")).strip()
            path_text = get_path(row)
            path_text = re.sub(r"(?i)ia[\s\-:]+", "", path_text).strip()
            
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
    default_p_idx = 0
    if "ps_selected_macro_id" in st.session_state and st.session_state["ps_selected_macro_id"] in p_opts:
        default_p_idx = list(p_opts.keys()).index(st.session_state["ps_selected_macro_id"])

    c_sel, c_btn = st.columns([3, 1])
    with c_sel:
        selected_macro_id = st.selectbox("Selecione a Coleção de Soluções (Macro):", options=list(p_opts.keys()), format_func=lambda x: f"[{x[:4]}] {p_opts[x]}", index=default_p_idx)
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
                        solucoes.append({
                            "id": str(uuid.uuid4()),
                            "selecionada": False,
                            "desc": obj.get("solucao", ""),
                            "c_score": c,
                            "e_score": e,
                            "i_score": i,
                            "comentario": obj.get("comentario", ""),
                            "final_score": (c * active_macro.get("p_c_peso", 1)) + (e * active_macro.get("p_e_peso", 1)) + (i * active_macro.get("p_i_peso", 1))
                        })
                    active_causa["solucoes"] = solucoes
                    # Força nova geração
                    st.session_state["ps_gen_ver"] = st.session_state.get("ps_gen_ver", 0) + 1
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.rerun()
                else:
                    st.error("Erro na resposta da IA.")
    
    # CSS Custom Grid (1400px scrollable)
    st.markdown(
        f'<style>'
        f'div[data-testid="stHorizontalBlock"] {{ min-width: 1400px !important; }}'
        f'[data-testid="stColumn"] div[data-testid="stHorizontalBlock"] {{ min-width: 0 !important; }}'
        f'</style>'
        f'<div style="min-width:1400px; height:1px; visibility:hidden;"></div>',
        unsafe_allow_html=True
    )

    # Header Row
    st.markdown(
        '<div style="background-color: #001C59; color: white; padding: 10px; border-radius: 6px;">'
        '<div style="display: flex; gap: 1rem; align-items: center; padding: 0 4px;">'
        '<div style="flex: 0.5; font-size: 0.85em;"><b>Eleger</b></div>'
        '<div style="flex: 4; font-size: 0.85em;"><b>Solução</b></div>'
        '<div style="flex: 1.5; font-size: 0.85em;"><b>Custo (1-5)</b></div>'
        '<div style="flex: 1.5; font-size: 0.85em;"><b>Esforço (1-5)</b></div>'
        '<div style="flex: 1.5; font-size: 0.85em;"><b>Impacto (1-5)</b></div>'
        '<div style="flex: 1.5; font-size: 0.85em;"><b>Score Total</b></div>'
        '<div style="flex: 4; font-size: 0.85em;"><b>Análise / Prós e Contras</b></div>'
        '<div style="flex: 0.8; font-size: 0.85em;"><b>Ação</b></div>'
        '</div></div><br>',
        unsafe_allow_html=True
    )

    gen_ver = st.session_state.get("ps_gen_ver", 0)
    
    dirty = False

    for s_idx, sol in enumerate(solucoes):
        cols = st.columns([0.5, 4, 1.5, 1.5, 1.5, 1.5, 4, 0.8])
        
        # Checkbox
        h = 100
        new_sel = cols[0].checkbox("V", value=sol.get("selecionada", False), key=f"sel_{selected_macro_id}_{sel_causa_idx}_{s_idx}", disabled=read_only, label_visibility="collapsed")
        
        # Desc Text
        new_desc = cols[1].text_area("desc", value=sol.get("desc", ""), key=f"dsc_{selected_macro_id}_{sel_causa_idx}_{s_idx}_v{gen_ver}", height=h, label_visibility="collapsed", disabled=read_only)
        
        # Numeric Inputs
        new_c = cols[2].number_input("C", min_value=1, max_value=5, value=sol.get("c_score", 3), key=f"c_{selected_macro_id}_{sel_causa_idx}_{s_idx}_v{gen_ver}", label_visibility="collapsed", disabled=read_only)
        new_e = cols[3].number_input("E", min_value=1, max_value=5, value=sol.get("e_score", 3), key=f"e_{selected_macro_id}_{sel_causa_idx}_{s_idx}_v{gen_ver}", label_visibility="collapsed", disabled=read_only)
        new_i = cols[4].number_input("I", min_value=1, max_value=5, value=sol.get("i_score", 3), key=f"i_{selected_macro_id}_{sel_causa_idx}_{s_idx}_v{gen_ver}", label_visibility="collapsed", disabled=read_only)
        
        # Total Score
        old_score = sol.get("final_score", 0)
        calc_score = (new_c * active_macro.get("p_c_peso", 1)) + (new_e * active_macro.get("p_e_peso", 1)) + (new_i * active_macro.get("p_i_peso", 1))
        
        color_score = "green" if calc_score >= 30 else ("orange" if calc_score >= 15 else "red")
        cols[5].markdown(f"<div style='text-align:center; padding-top:20px; font-size:24px; color:{color_score}; font-weight:bold;'>{calc_score}</div>", unsafe_allow_html=True)
        
        # Comentario Text
        new_com = cols[6].text_area("com", value=sol.get("comentario", ""), key=f"com_{selected_macro_id}_{sel_causa_idx}_{s_idx}_v{gen_ver}", height=h, label_visibility="collapsed", disabled=read_only)
        
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
        with cols[7]:
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
