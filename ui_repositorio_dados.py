import streamlit as st
import pandas as pd
import io
import json
import uuid
import datetime

def render_repositorio_dados_ui(project_state, pid, db, read_only):
    st.subheader("📊 Repositório de Medições (Laboratório de Dados)")
    st.markdown("""
        **Bem-vindo ao Laboratório!**  
        Aqui você centraliza as medições críticas do seu projeto. O **Doutor Lean** atuará como um Cientista de Dados para ajudá-lo a encontrar padrões, gerar gráficos (Histogramas, Paretos, Tendências) e realizar análises descritivas.
        
        > 💡 **Nota Importante:** A inteligência artificial mapeia padrões matemáticos, mas a **interpretação humana e o conhecimento do piso de fábrica (Gemba) são insubstituíveis** para atestar qualquer causa raiz.
    """)

    # 1. Carregamento de Dados
    st.markdown("### 1. Importar Base de Dados / Documentação")
    st.info("💡 Cole seus dados na caixa de texto abaixo OU faça upload de um arquivo (CSV, Excel, PDF, Word, JPG, PNG).")
    
    col_upload, col_paste = st.columns([1, 2])
    with col_upload:
        uploaded_file = st.file_uploader("Upload de Arquivo", type=["csv", "xlsx", "xls", "pdf", "docx", "png", "jpg", "jpeg"], disabled=read_only)
    with col_paste:
        pasted_data = st.text_area("Ou Cole os Dados Aqui (tab-separated)", height=80, disabled=read_only)

    df = None
    doc_text = ""
    vision_data = None
    
    # Processar o upload ou colagem
    try:
        import base64
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
            elif ext in ["png", "jpg", "jpeg"]:
                b64_str = base64.b64encode(uploaded_file.getvalue()).decode("utf-8")
                mime = f"image/{ext}" if ext != "jpg" else "image/jpeg"
                vision_data = ("IMAGE", f"data:{mime};base64,{b64_str}")
        elif pasted_data.strip():
            df = pd.read_csv(io.StringIO(pasted_data), sep="\t")
            
        # Tenta carregar o que já estava salvo se não houver um novo input agora
        if df is None and not doc_text and not vision_data and project_state.get("measurements_raw"):
            try:
                # Caso fosse tabela salva
                df = pd.read_json(io.StringIO(project_state["measurements_raw"]), orient="records")
            except:
                pass

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {str(e)}")

    if df is not None:
        if len(df) > 2000:
            st.error("⚠️ **Limite de Processamento Excedido!**")
            df = None
        else:
            st.success(f"✅ Tabela estruturada (CSV/Excel) carregada: {len(df)} linhas.")
            if not read_only:
                project_state["measurements_raw"] = df.to_json(orient="records")
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
    elif doc_text:
        st.success(f"✅ Documento Texto importado ({len(doc_text)} caracteres).")
    elif vision_data:
        st.success("✅ Imagem importada para análise via Visão Computacional.")
        st.image(uploaded_file, caption="Anexo da Mesa de Trabalho", width=300)

    st.markdown("---")
    
    # 2. Chat Analista
    st.markdown("### 2. Conversar com o Cientista de Dados (Doutor Lean)")
    
    if "data_chat_logs" not in st.session_state:
        st.session_state["data_chat_logs"] = []

    # Container de mensagens
    chat_container = st.container()
    
    for msg in st.session_state["data_chat_logs"]:
        is_user = msg["role"] == "user"
        with chat_container.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # Se a IA também retornou um gráfico vega_lite
            if not is_user and "vega_lite" in msg and msg["vega_lite"]:
                try:
                    import altair as alt
                    chart = alt.Chart.from_dict(msg["vega_lite"])
                    st.altair_chart(chart, use_container_width=True)
                except Exception as e:
                    st.caption(f"Não foi possível renderizar o gráfico gerado: {str(e)}")

    if not read_only:
        # Pega a pergunta
        query = st.chat_input("O que você deseja saber sobre os dados? (Ex: 'Gere um histograma da coluna Tempo')")
        if query:
            # Mostra e salva msg do user
            st.session_state["data_chat_logs"].append({"role": "user", "content": query})
            with chat_container.chat_message("user"):
                st.markdown(query)
            
            with chat_container.chat_message("assistant"):
                with st.spinner("Analisando matematicamente..."):
                    import coach_extensions
                    
                    data_str_context = "O aluno não forneceu uma tabela de dados válida ainda."
                    if vision_data:
                        data_str_context = vision_data
                    elif df is not None:
                        data_str_context = f"Resumo do DataFrame (shape {df.shape}):\n{df.head(10).to_csv(index=False)}"
                    elif doc_text:
                        data_str_context = f"Resumo do Documento PDF/Word fornecido:\n{doc_text[:3000]}..."

                    # Executa IA
                    resultado_json = coach_extensions.analyze_measurement_data(
                        project_state, 
                        data_str_context, 
                        query, 
                        st.session_state["data_chat_logs"][:-1] # manda histórico exceto a última que já ta no system context na funçao? Nao, manda tudo.
                    )
                    
                    # Checa resposta
                    ans_text = resultado_json.get("resposta", "Sem resposta analítica.")
                    v_lite = resultado_json.get("vega_lite", None)
                    
                    st.markdown(ans_text)
                    if v_lite:
                        try:
                            import altair as alt
                            chart = alt.Chart.from_dict(v_lite)
                            st.altair_chart(chart, use_container_width=True)
                        except Exception as e:
                            st.caption(f"Problema na renderização: {str(e)}")
                    
                    # Salva
                    st.session_state["data_chat_logs"].append({
                        "role": "assistant", 
                        "content": ans_text,
                        "vega_lite": v_lite
                    })

        # Botão de salvar relatório
        if st.session_state["data_chat_logs"]:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander("💾 Gravar Análises como Relatório Oficial", expanded=False):
                st.info("Isto irá compactar nossa conversa atual e torná-la parte da Memória Oficial do projeto (usada pelas IAs das outras ferramentas Ishikawa/5 PQs).")
                titulo_rel = st.text_input("Título deste Relatório (ex: Histograma do Processo B)")
                if st.button("Salvar Relatório na Memória do Projeto", type="primary"):
                    if not titulo_rel:
                        st.warning("Preencha um título para salvar!")
                    else:
                        reports = project_state.get("measurement_reports", [])
                        new_rep = {
                            "id": str(uuid.uuid4())[:8],
                            "title": titulo_rel,
                            "date": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "logs": st.session_state["data_chat_logs"]
                        }
                        reports.append(new_rep)
                        project_state["measurement_reports"] = reports
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                        st.success("Relatório Oficial Salvo!")
                        # Limpa o chat para começar outra coisa
                        st.session_state["data_chat_logs"] = []
                        st.rerun()

    st.markdown("---")
    
    # 3. Biblioteca de Relatórios Salvos
    st.markdown("### 3. Biblioteca de Relatórios Salvos")
    reports = project_state.get("measurement_reports", [])
    if not reports:
        st.info("Nenhum relatório salvo no repositório ainda.")
    else:
        # Coluna de seleção e botão de exclusão
        hc1, hc2 = st.columns([3, 1])
        report_options = {f"{r['title']} ({r['date']})": r for r in reports}
        selected_rep_title = hc1.selectbox("Selecione um Relatório Salvo para Visualização:", options=list(report_options.keys()))
        selected_rep = report_options[selected_rep_title]
        
        # Deletar Relatório
        if not read_only:
            if hc2.button("🗑️ Apagar Selecionado", use_container_width=True):
                project_state["measurement_reports"] = [r for r in reports if r["id"] != selected_rep["id"]]
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"])
                st.rerun()

        # Renderizar Relatório Selecionado
        with st.container(border=True):
            st.markdown(f"**Visualizando: {selected_rep['title']}**")
            for msg in selected_rep.get("logs", []):
                st.markdown(f"**{msg['role'].capitalize()}**: {msg['content']}")
                if "vega_lite" in msg and msg["vega_lite"]:
                    try:
                        import altair as alt
                        c = alt.Chart.from_dict(msg["vega_lite"])
                        st.altair_chart(c, use_container_width=True)
                    except:
                        st.caption("Gráfico salvo está inacessível ou corrompido.")
