import streamlit as st
import uuid
import copy
from db import upsert_project

def get_new_id():
    return f"pv_{uuid.uuid4().hex[:8]}"

def extract_5pq_tree(branches):
    """
    Given a list of branches from a 5PQs tree, extract all nodes with their WBS and hierarchy.
    """
    wbs_labels = [[""] * len(row) for row in branches]
    
    def get_parent_wbs(r, c):
        if c == 0: return ""
        for row_idx in range(r, -1, -1):
            if row_idx < len(branches) and c-1 < len(branches[row_idx]) and branches[row_idx][c-1] is not None:
                return wbs_labels[row_idx][c-1]
        return ""

    child_counts = {}
    c0_count = 0
    extracted_nodes = []

    for r in range(len(branches)):
        for c in range(len(branches[r])):
            if branches[r][c] is not None:
                if c == 0:
                    c0_count += 1
                    label = f"X{c0_count}"
                    parent_label = ""
                else:
                    parent_label = get_parent_wbs(r, c)
                    if parent_label not in child_counts:
                        child_counts[parent_label] = 1
                    else:
                        child_counts[parent_label] += 1
                    label = f"{parent_label}.{child_counts[parent_label]}"
                
                wbs_labels[r][c] = label
                pq_text = branches[r][c].get("pq", "").strip()
                if pq_text: # Só extrai nós que têm texto
                    extracted_nodes.append({
                        "id": str(uuid.uuid4()),
                        "wbs": label,
                        "parent_wbs": parent_label,
                        "causa": pq_text,
                        "status": "pendente",
                        "modelo_validacao": "",
                        "aux_modelo_validacao": "",
                        "como": "",
                        "quando": "",
                        "amostra": "",
                        "responsavel": "",
                        "dados_coletados": "",
                        "interpretacao_aluno": "",
                        "veredito_ia": ""
                    })

    # Ordena pelo WBS para garantir visualização hierárquica X1, X1.1, X1.2...
    def sort_wbs(x):
        parts = x["wbs"].replace("X", "").split(".")
        return [int(p) if p.isdigit() else 0 for p in parts]
    
    extracted_nodes.sort(key=sort_wbs)
    return extracted_nodes


@st.dialog("🔬 Análise de Dados da Causa", width="large")
def modal_analise_causa(project_state, pid, db_module, plano_idx, row_idx, read_only):
    plano_atual = project_state["planos_validacao"][plano_idx]
    row = plano_atual["rows"][row_idx]
    
    st.subheader(f"Validando: [{row['wbs']}] {row['causa']}")
    st.markdown("Insira os dados coletados e peça para o Doutor Lean analisar. Se for uma avaliação qualitativa, descreva as observações.")
    
    gen_key = st.session_state.get(f"pv_modal_gen_{plano_atual['id']}_{row_idx}", 0)
    
    # Text Area para os Dados
    novos_dados = st.text_area(
        "Dados Coletados / Observações Práticas",
        value=row.get("dados_coletados", ""),
        height=150,
        disabled=read_only,
        key=f"dados_{plano_atual['id']}_{row_idx}_v{gen_key}"
    )
    
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("🧠 Pedir Análise da IA", disabled=read_only or not novos_dados.strip(), use_container_width=True):
            with st.spinner("Analisando dados..."):
                from coach_extensions import analyze_validation_data
                row["dados_coletados"] = novos_dados
                ia_resp = analyze_validation_data(project_state, row["causa"], novos_dados)
                row["veredito_ia"] = ia_resp
                st.session_state[f"pv_modal_gen_{plano_atual['id']}_{row_idx}"] = gen_key + 1
                db_module.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.rerun()
                
    with c2:
        if st.button("🤔 Sugerir Interpretação (Aluno)", disabled=read_only or not row.get("veredito_ia"), use_container_width=True):
            st.warning("Feature: Sugerir interpretação (em construção)")
            # todo: implementar interação do aluno para interpretar a IA
            

    if row.get("veredito_ia"):
        st.markdown("### Retorno do Doutor Lean:")
        st.info(row["veredito_ia"])
        
    st.markdown("---")
    res_c1, res_c2, res_c3 = st.columns(3)
    row_status = row.get("status", "pendente")
    
    def update_status(new_status):
        row["dados_coletados"] = novos_dados
        row["status"] = new_status
        db_module.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
        st.rerun()

    with res_c1:
        if st.button("✅ Considerar Validada", type="primary" if row_status=="validada" else "secondary", disabled=read_only, use_container_width=True):
            update_status("validada")
    with res_c2:
        if st.button("❌ Considerar Recusada", type="primary" if row_status=="recusada" else "secondary", disabled=read_only, use_container_width=True):
            update_status("recusada")
    with res_c3:
        if st.button("⏳ Deixar Pendente", type="primary" if row_status=="pendente" else "secondary", disabled=read_only, use_container_width=True):
            update_status("pendente")


def render_plano_validacao_ui(project_state, pid, db, read_only):
    st.subheader("✅ Plano de Validação de Causas")
    st.markdown("Baseado nas hipóteses do 5 Porquês, valide quais causas raízes são verdadeiras com dados ou dedução analítica comprovada.")

    planos = project_state.get("planos_validacao", [])
    pqs = project_state.get("cinco_pqs", [])

    if not planos:
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Criar Plano Vazio", disabled=read_only):
                planos.append({
                    "id": get_new_id(),
                    "effect": "Plano Independente",
                    "rows": []
                })
                project_state["planos_validacao"] = planos
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.rerun()
        with c2:
            pq_opts = {p["id"]: p["effect"] for p in pqs if p.get("branches")}
            if pq_opts:
                with st.popover("Importar de um 5 Porquês", use_container_width=True):
                    sel_pq_id = st.selectbox("Selecione o 5PQs:", options=list(pq_opts.keys()), format_func=lambda x: pq_opts[x])
                    if st.button("Gerar Plano 📥"):
                        target_pq = next((p for p in pqs if p["id"] == sel_pq_id), None)
                        extracted = extract_5pq_tree(target_pq["branches"])
                        planos.append({
                            "id": get_new_id(),
                            "effect": target_pq["effect"],
                            "ref_5pq_id": sel_pq_id,
                            "rows": extracted
                        })
                        project_state["planos_validacao"] = planos
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.rerun()
            else:
                st.info("Nenhum 5 Porquês encontrado para importação.")
        return

    plano_opts = {p["id"]: p["effect"] for p in planos}
    plano_opts_ids = list(plano_opts.keys())
    default_idx = 0
    if "pv_selected_id" in st.session_state and st.session_state["pv_selected_id"] in plano_opts_ids:
        default_idx = plano_opts_ids.index(st.session_state["pv_selected_id"])

    c_sel, c_btn = st.columns([3, 1])
    with c_sel:
        selected_id = st.selectbox("Selecione o Plano de Validação:", options=plano_opts_ids, format_func=lambda x: f"[{x[:4]}] {plano_opts[x]}", index=default_idx)
        st.session_state["pv_selected_id"] = selected_id
    with c_btn:
        pq_opts = {p["id"]: p["effect"] for p in pqs if p.get("branches")}
        with st.popover("➕ Novo Plano", use_container_width=True):
            if st.button("Plano Vazio"):
                planos.append({"id": get_new_id(), "effect": f"Plano {len(planos)+1}", "rows": []})
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.rerun()
            if pq_opts:
                sel_pq_id_new = st.selectbox("Do 5PQs:", options=list(pq_opts.keys()), format_func=lambda x: pq_opts[x], key="novo_de_pq")
                if st.button("Gerar do 5PQs"):
                    target_pq = next((p for p in pqs if p["id"] == sel_pq_id_new), None)
                    extracted = extract_5pq_tree(target_pq["branches"])
                    planos.append({
                        "id": get_new_id(),
                        "effect": target_pq["effect"],
                        "ref_5pq_id": sel_pq_id_new,
                        "rows": extracted
                    })
                    db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                    st.rerun()

    active_plano_idx = next((i for i, p in enumerate(planos) if p["id"] == selected_id), None)
    if active_plano_idx is None: return
    active_plano = planos[active_plano_idx]

    rows = active_plano.get("rows", [])
    if not rows:
        st.info("Plano vazio. Adicione causas manualmente.")
        # Pode ter um botao pra inserir manual
        if st.button("➕ Adicionar Causa Manual"):
            rows.append({
                "id": str(uuid.uuid4()), "wbs": "", "parent_wbs": "", "causa": "", "status": "pendente",
                "modelo_validacao": "", "aux_modelo_validacao": "", "como": "", "quando": "", "amostra": "", "responsavel": "",
                "dados_coletados": "", "interpretacao_aluno": "", "veredito_ia": ""
            })
            active_plano["rows"] = rows
            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.rerun()

    # Monta um dicionário para ver facilmente o status dos pais
    status_map = {r["wbs"]: r.get("status", "pendente") for r in rows if r.get("wbs")}

    st.markdown(
        f'<style>'
        f'div[data-testid="stHorizontalBlock"] {{ min-width: 1400px !important; }}'
        f'[data-testid="stColumn"] div[data-testid="stHorizontalBlock"] {{ min-width: 0 !important; }}'
        f'</style>'
        f'<div style="min-width:1400px; height:1px; visibility:hidden;"></div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div style="background-color: #001C59; color: white; padding: 10px; border-radius: 6px;">'
        '<div style="display: flex; align-items: center;">'
        '<div style="flex: 0.1; padding: 0 5px; font-size: 0.85em;"><b>Status</b></div>'
        '<div style="flex: 0.1; padding: 0 5px; font-size: 0.85em;"><b>Nó</b></div>'
        '<div style="flex: 0.4; padding: 0 5px; font-size: 0.85em;"><b>Causa (Hipótese)</b></div>'
        '<div style="flex: 0.5; padding: 0 5px; font-size: 0.85em;"><b>Modelo de Validação</b></div>'
        '<div style="flex: 0.2; padding: 0 5px; font-size: 0.85em;"><b>Amostra</b></div>'
        '<div style="flex: 0.2; padding: 0 5px; font-size: 0.85em;"><b>Como</b></div>'
        '<div style="flex: 0.15; padding: 0 5px; font-size: 0.85em;"><b>Ação</b></div>'
        '</div></div><br>',
        unsafe_allow_html=True
    )

    gen_ver = st.session_state.get("pv_gen_ver", 0)
    
    for idx, r in enumerate(rows):
        is_locked_by_parent = False
        pt_wbs = r.get("parent_wbs")
        if pt_wbs and pt_wbs in status_map:
            if status_map[pt_wbs] != "validada":
                is_locked_by_parent = True
                
        row_disabled = read_only or is_locked_by_parent

        cols = st.columns([0.1, 0.1, 0.4, 0.5, 0.2, 0.2, 0.15])
        
        status_ico = "⏳"
        if r.get("status") == "validada": status_ico = "✅"
        elif r.get("status") == "recusada": status_ico = "❌"
        if is_locked_by_parent: status_ico = "🔒"

        cols[0].markdown(f"<div style='text-align:center; padding-top: 15px; font-size:24px;'>{status_ico}</div>", unsafe_allow_html=True)
        cols[1].markdown(f"<div style='text-align:center; padding-top: 20px;'><b>{r.get('wbs')}</b></div>", unsafe_allow_html=True)

        h = 100
        new_c = cols[2].text_area("causa", value=r.get("causa", ""), key=f"pv_c_{selected_id}_{idx}_v{gen_ver}", height=h, label_visibility="collapsed", disabled=row_disabled)
        new_m = cols[3].text_area("mod", value=r.get("modelo_validacao", ""), key=f"pv_m_{selected_id}_{idx}_v{gen_ver}", height=h, label_visibility="collapsed", disabled=row_disabled)
        new_a = cols[4].text_area("amo", value=r.get("amostra", ""), key=f"pv_a_{selected_id}_{idx}_v{gen_ver}", height=h, label_visibility="collapsed", disabled=row_disabled)
        new_k = cols[5].text_area("como", value=r.get("como", ""), key=f"pv_k_{selected_id}_{idx}_v{gen_ver}", height=h, label_visibility="collapsed", disabled=row_disabled)
        
        r["causa"] = new_c
        r["modelo_validacao"] = new_m
        r["amostra"] = new_a
        r["como"] = new_k

        with cols[6]:
            if not row_disabled:
                if st.button("✨ Gerar Validação", key=f"btn_ia_{selected_id}_{idx}", use_container_width=True):
                    from coach_extensions import suggest_modelo_validacao
                    with st.spinner("Dr Lean pensando..."):
                        sugestao = suggest_modelo_validacao(project_state, r["causa"], r.get("parent_wbs"), "Simples")
                        r["modelo_validacao"] = f"Sugestão IA: {sugestao}"
                        st.session_state["pv_gen_ver"] = gen_ver + 1
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.rerun()

                if st.button("🔬 Analisar / Validar", key=f"btn_mod_{selected_id}_{idx}", use_container_width=True):
                    modal_analise_causa(project_state, pid, db, active_plano_idx, idx, read_only)
            else:
                if is_locked_by_parent:
                    st.caption("🔒 Validar pai primeiro")

