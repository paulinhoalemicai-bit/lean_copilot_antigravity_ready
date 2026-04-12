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
    st.markdown("Insira os dados coletados e converse com o Doutor Lean para obter análises estátisticas e gráficos para atestar esta causa.")
    
    # 1. Carregamento de Dados (Mini)
    col_upload, col_paste = st.columns([1, 2])
    with col_upload:
        uploaded_file = st.file_uploader("Upload de Documentos / Imagens", type=["csv", "xlsx", "xls", "pdf", "docx", "png", "jpg", "jpeg"], disabled=read_only)
    with col_paste:
        novos_dados = st.text_area("Ou Cole Dados/Observações", value="", height=100, disabled=read_only)

    df = None
    arquivo_resumo = ""
    vision_data = None
    doc_text = ""
    try:
        import base64
        import pandas as pd
        import io
        if uploaded_file is not None:
            ext = uploaded_file.name.split(".")[-1].lower()
            if ext == "csv":
                df = pd.read_csv(uploaded_file)
            elif ext in ["xlsx", "xls"]:
                df = pd.read_excel(uploaded_file)
            elif ext == "pdf":
                import pypdf
                pdf_reader = pypdf.PdfReader(uploaded_file)
                doc_text = "\n".join([page.extract_text() for page in pdf_reader.pages if page.extract_text()])
                arquivo_resumo = f"Documento PDF Fornecido:\n{doc_text[:3000]}..."
                st.success(f"PDF carregado e texto extraído ({len(doc_text)} caracteres).")
            elif ext == "docx":
                import docx
                doc = docx.Document(uploaded_file)
                doc_text = "\n".join([para.text for para in doc.paragraphs])
                arquivo_resumo = f"Documento Word Fornecido:\n{doc_text[:3000]}..."
                st.success(f"Word carregado e texto extraído ({len(doc_text)} caracteres).")
            elif ext in ["png", "jpg", "jpeg"]:
                b64_str = base64.b64encode(uploaded_file.getvalue()).decode("utf-8")
                mime = f"image/{ext}" if ext != "jpg" else "image/jpeg"
                vision_data = ("IMAGE", f"data:{mime};base64,{b64_str}")
                arquivo_resumo = vision_data
                st.success("Imagem anexada para Visão Computacional.")
                st.image(uploaded_file, width=300)
        elif novos_dados.strip():
            df = pd.read_csv(io.StringIO(novos_dados), sep="\t")
            
        # Carregamentos salvos no banco local da linha
        if df is None and not doc_text and not vision_data and not novos_dados.strip():
            m_type = row.get("arquivos_salvos_tipo", "texto_plano")
            saved_data = row.get("arquivos_salvos_dados", "")
            if saved_data:
                if m_type == "csv":
                    try: df = pd.read_json(io.StringIO(saved_data), orient="records")
                    except: pass
                elif m_type == "doc":
                    doc_text = saved_data
                    arquivo_resumo = f"Documento Salvo:\n{doc_text[:3000]}..."
                elif m_type == "vision":
                    vision_data = ("IMAGE", saved_data)
                    arquivo_resumo = vision_data
                elif m_type == "texto_plano":
                    arquivo_resumo = f"Observações Práticas Salvas: {saved_data}"
        
        if df is not None:
            if len(df) > 2000:
                st.error("⚠️ Base com mais de 2.000 linhas. Use uma IA externa para resumir os dados.")
                df = None
            else:
                arquivo_resumo = f"Resumo do DataFrame:\n{df.head(10).to_csv(index=False)}"
                st.success(f"Tabela carregada: {len(df)} linhas.")
                
    except Exception:
        if novos_dados.strip(): 
            arquivo_resumo = f"Observações Práticas: {novos_dados}"

    # Botão de Salvamento (Específico da linha/causa)
    if not read_only and (df is not None or doc_text or vision_data or novos_dados.strip()):
        if st.button("💾 Salvar Anexo na Causa", use_container_width=True):
            if df is not None:
                row["arquivos_salvos_tipo"] = "csv"
                row["arquivos_salvos_dados"] = df.to_json(orient="records")
            elif doc_text:
                row["arquivos_salvos_tipo"] = "doc"
                row["arquivos_salvos_dados"] = doc_text
            elif vision_data:
                row["arquivos_salvos_tipo"] = "vision"
                row["arquivos_salvos_dados"] = vision_data[1]
            elif novos_dados.strip():
                row["arquivos_salvos_tipo"] = "texto_plano"
                row["arquivos_salvos_dados"] = novos_dados.strip()
            
            row["dados_coletados"] = "Possui anexo multimodal" # Feedback visual
            db_module.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.success("Anexo salvo no banco de dados para esta causa!")

    st.markdown("---")
    
    # 2. Chat Analista Específico da Hipótese
    chat_key = f"chat_pv_{plano_atual['id']}_{row_idx}"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []
        
    chat_container = st.container()
    
    for msg in st.session_state[chat_key]:
        with chat_container.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("vega_lite"):
                try:
                    import altair as alt
                    st.altair_chart(alt.Chart.from_dict(msg["vega_lite"]), use_container_width=True)
                except Exception as e:
                    st.caption(f"Falha ao desenhar o gráfico: {str(e)}")

    if not read_only:
        query = st.chat_input(f"Peça uma análise específica sobre [{row['wbs']}]...")
        if query:
            st.session_state[chat_key].append({"role": "user", "content": query})
            with chat_container.chat_message("user"): st.markdown(query)
            
            with chat_container.chat_message("assistant"):
                with st.spinner("Analisando estatiscamente..."):
                    from coach_extensions import analyze_measurement_data
                    ctx = arquivo_resumo if arquivo_resumo else "O aluno não postou dados. Apenas converse e tente induzi-lo."
                    resultado_json = analyze_measurement_data(project_state, ctx, query, st.session_state[chat_key][:-1])
                    
                    ans_text = resultado_json.get("resposta", "")
                    v_lite = resultado_json.get("vega_lite", None)
                    
                    st.markdown(ans_text)
                    if v_lite:
                        try:
                            import altair as alt
                            st.altair_chart(alt.Chart.from_dict(v_lite), use_container_width=True)
                        except Exception as e:
                            pass
                    
                    st.session_state[chat_key].append({
                        "role": "assistant",
                        "content": ans_text,
                        "vega_lite": v_lite
                    })

    # 3. Gravar Evidência
    if not read_only and st.session_state[chat_key]:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 Gravar Chat como Evidência de Validação", type="primary", use_container_width=True):
            row["evidencia_chat"] = st.session_state[chat_key].copy()
            row["veredito_ia"] = "Evidência Registrada no Laboratório."
            db_module.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
            st.success("Análise Gravada! Ela atestará ou refutará sua matriz principal.")

    st.markdown("---")
    res_c1, res_c2, res_c3 = st.columns(3)
    row_status = row.get("status", "pendente")
    
    def update_status(new_status):
        row["status"] = new_status
        db_module.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
        st.rerun()

    with res_c1:
        if st.button("✅ Considerar Validada", type="primary" if row_status=="validada" else "secondary", disabled=read_only): update_status("validada")
    with res_c2:
        if st.button("❌ Considerar Recusada", type="primary" if row_status=="recusada" else "secondary", disabled=read_only): update_status("recusada")
    with res_c3:
        if st.button("⏳ Deixar Pendente", type="primary" if row_status=="pendente" else "secondary", disabled=read_only): update_status("pendente")

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
        '<div style="display: flex; gap: 1rem; align-items: center; padding: 0 4px;">'
        '<div style="flex: 1; font-size: 0.85em;"><b>Status</b></div>'
        '<div style="flex: 1; font-size: 0.85em;"><b>Nó</b></div>'
        '<div style="flex: 4; font-size: 0.85em;"><b>Causa (Hipótese)</b></div>'
        '<div style="flex: 5; font-size: 0.85em;"><b>Modelo de Validação</b></div>'
        '<div style="flex: 1.5; font-size: 0.85em;"><b>Ação</b></div>'
        '<div style="flex: 2; font-size: 0.85em;"><b>Como</b></div>'
        '<div style="flex: 2; font-size: 0.85em;"><b>Amostra</b></div>'
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

        cols = st.columns([1, 1, 4, 4.5, 2.5, 2, 1.5])
        
        status_ico = "⏳"
        if r.get("status") == "validada": status_ico = "✅"
        elif r.get("status") == "recusada": status_ico = "❌"
        if is_locked_by_parent: status_ico = "🔒"

        cols[0].markdown(f"<div style='text-align:center; padding-top: 15px; font-size:24px;'>{status_ico}</div>", unsafe_allow_html=True)
        cols[1].markdown(f"<div style='text-align:center; padding-top: 20px;'><b>{r.get('wbs')}</b></div>", unsafe_allow_html=True)

        h = 100
        new_c = cols[2].text_area("causa", value=r.get("causa", ""), key=f"pv_c_{selected_id}_{idx}_v{gen_ver}", height=h, label_visibility="collapsed", disabled=row_disabled)
        new_m = cols[3].text_area("mod", value=r.get("modelo_validacao", ""), key=f"pv_m_{selected_id}_{idx}_v{gen_ver}", height=h, label_visibility="collapsed", disabled=row_disabled)
        
        with cols[4]:
            if not row_disabled:
                if st.button("✨ Sugerir", key=f"btn_ia_{selected_id}_{idx}"):
                    from coach_extensions import suggest_modelo_validacao
                    import re
                    with st.spinner("IA..."):
                        parent_text = ""
                        if r.get("parent_wbs"):
                            pt_row = next((pr for pr in rows if pr["wbs"] == r["parent_wbs"]), None)
                            if pt_row:
                                parent_text = pt_row.get("causa", "")
                                parent_text = re.sub(r"^ia[\s\-:]+", "", parent_text, flags=re.IGNORECASE).strip()
                                
                        clean_causa = re.sub(r"^ia[\s\-:]+", "", r["causa"], flags=re.IGNORECASE).strip()
                        sugestao = suggest_modelo_validacao(project_state, clean_causa, parent_text, active_plano.get("effect", ""), "Simples")
                        r["modelo_validacao"] = f"Sugestão IA: {sugestao}"
                        st.session_state["pv_gen_ver"] = gen_ver + 1
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.rerun()

                if r.get("modelo_validacao") and st.button("📝 Detalhar", key=f"btn_det_{selected_id}_{idx}", help="Como coletar e tamanho de amostra"):
                    from coach_extensions import suggest_pratica_validacao
                    with st.spinner("Prática..."):
                        como, amostra = suggest_pratica_validacao(project_state, r["causa"], r["modelo_validacao"])
                        r["como"] = como
                        r["amostra"] = amostra
                        st.session_state["pv_gen_ver"] = gen_ver + 1
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.rerun()

                btn_label = "📊 Analisar (Evidência Salva)" if r.get("evidencia_chat") else "🔬 Analisar Dados"
                if st.button(btn_label, key=f"btn_mod_{selected_id}_{idx}"):
                    modal_analise_causa(project_state, pid, db, active_plano_idx, idx, read_only)
            else:
                if is_locked_by_parent:
                    st.caption("🔒 Pais pendentes")

        new_k = cols[5].text_area("como", value=r.get("como", ""), key=f"pv_k_{selected_id}_{idx}_v{gen_ver}", height=h, label_visibility="collapsed", disabled=row_disabled)
        new_a = cols[6].text_area("amo", value=r.get("amostra", ""), key=f"pv_a_{selected_id}_{idx}_v{gen_ver}", height=h, label_visibility="collapsed", disabled=row_disabled)
        
        r["causa"] = new_c
        r["modelo_validacao"] = new_m
        r["amostra"] = new_a
        r["como"] = new_k

