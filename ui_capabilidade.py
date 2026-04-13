import streamlit as st
import pandas as pd
import numpy as np
import scipy.stats as stats
import docx
from pypdf import PdfReader
import io

def parse_doc(file) -> str:
    ext = file.name.split('.')[-1].lower()
    text = ""
    try:
        if ext == 'pdf':
            pdf = PdfReader(file)
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        elif ext == 'docx':
            doc = docx.Document(file)
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
        else:
            text = file.getvalue().decode("utf-8", errors="replace")
    except Exception as e:
        text = f"Erro na leitura do arquivo: {e}"
    return text

def parse_data(file) -> pd.DataFrame:
    ext = file.name.split('.')[-1].lower()
    try:
        if ext == 'csv':
            df = pd.read_csv(file, sep=None, engine='python')
        elif ext in ['xls', 'xlsx']:
            df = pd.read_excel(file)
        else:
            return None
            
        for col in df.columns:
            if df[col].dtype == 'object':
                # Remove pontos de milhar e converte virgula para ponto
                cleaned = df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                numeric_series = pd.to_numeric(cleaned, errors='coerce')
                # Se mais de 30% for numero valido, assume que a coluna eh toda numerica
                if numeric_series.notna().sum() >= (len(df) * 0.3):
                    df[col] = numeric_series
                    
        return df
    except:
        return None

def render_capabilidade_ui(project_state: dict, pid: str, db, read_only: bool, tool: str):
    st.subheader(tool)
    st.info("💡 **Capabilidade (Nível Sigma):** Avalie o quanto o seu processo é capaz de atender às especificações do cliente.")
    
    st_key_tipo = f"cap_tipo_{tool}"
    default_tipo = project_state.get(st_key_tipo, "Discretos (Contagem / Defeitos)")
    
    tipo = st.radio(
        "Tipo de Dados do Indicador Principal", 
        ["Discretos (Contagem / Defeitos)", "Contínuos (Medição Variável)"],
        index=0 if default_tipo == "Discretos (Contagem / Defeitos)" else 1,
        disabled=read_only
    )
    
    if tipo != default_tipo and not read_only:
        project_state[st_key_tipo] = tipo
        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"], project_state.get("allow_teacher_view", True))

    if tipo == "Discretos (Contagem / Defeitos)":
        st.markdown("### Capabilidade de Dados Discretos")
        
        st_key = f"cap_discrete_{tool}"
        default_data = [
            {"Variável": "Antes de Melhoria" if "Baseline" in tool else "Depois da Melhoria", "D (Defeitos)": 0, "U (Unidades)": 0, "OP (Oportunidades)": 1, "Shift": 1.5}
        ]
        data = project_state.get(st_key, default_data)
        
        st.markdown("#### 1. Campos de Entrada")
        edited_data = st.data_editor(
            data,
            num_rows="dynamic",
            column_config={
                "Variável": st.column_config.TextColumn("Variável"),
                "D (Defeitos)": st.column_config.NumberColumn("D (Nº Defeitos)", min_value=0),
                "U (Unidades)": st.column_config.NumberColumn("U (Nº Unidades)", min_value=0),
                "OP (Oportunidades)": st.column_config.NumberColumn("OP (Oportunidades do erro ocorrer)", min_value=1),
                "Shift": st.column_config.NumberColumn("Sigma Shift", default=1.5)
            },
            disabled=read_only,
            use_container_width=True
        )
        
        if edited_data != data and not read_only:
            if isinstance(edited_data, list):
                project_state[st_key] = edited_data
                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"], project_state.get("allow_teacher_view", True))

        st.markdown("#### 2. Campos Calculados")
        calc_rows = []
        for row in edited_data:
            d = max(0, float(row.get("D (Defeitos)", 0) or 0))
            u = max(0, float(row.get("U (Unidades)", 0) or 0))
            op = max(1, float(row.get("OP (Oportunidades)", 1) or 1))
            shift = float(row.get("Shift", 1.5) or 1.5)
            
            top = u * op
            dpu = d / u if u > 0 else 0
            dpo = d / top if top > 0 else 0
            dpmo = dpo * 1000000
            
            # Sigma L from norm.ppf(1 - DPO). Cap at 0.999999 and 0.000001
            safe_dpo = min(max(dpo, 0.000001), 0.999999) if dpo > 0 else 0.000001
            sigma_l = stats.norm.ppf(1 - safe_dpo)
            if dpo == 0: sigma_l = 6.0 # Arbitrary high capability when 0 defects
            zb = sigma_l + shift
            
            calc_rows.append({
                "Variável": row.get("Variável", ""),
                "TOP": top,
                "DPU": round(dpu, 4),
                "DPO": round(dpo, 4),
                "DPMO": round(dpmo, 1),
                "Sigma-L": round(sigma_l, 2),
                "Z.B (Curto Prazo)": round(zb, 2)
            })
            
        st.dataframe(pd.DataFrame(calc_rows), use_container_width=True)

    else:
        st.markdown("### Capabilidade de Dados Contínuos")
        st.markdown("Para dados contínuos, suba seu arquivo ou cole os dados brutos e deixe o Doutor Lean ajudar a interpretar se os dados são adequados e gerar o estudo de normalidade/capabilidade.")
        
        colChat, colData = st.columns([1, 1])
        
        with colData:
            uploaded_file = st.file_uploader("Subir Tabela de Dados (CSV, Excel) ou Documentos (PDF, DOCX, TXT)", type=["csv", "xlsx", "xls", "pdf", "docx", "txt"])
            
            df = None
            doc_text = ""
            if uploaded_file is not None:
                ext = uploaded_file.name.split('.')[-1].lower()
                if ext in ['csv', 'xlsx', 'xls']:
                    df = parse_data(uploaded_file)
                    if df is not None:
                        st.dataframe(df.head(), use_container_width=True)
                        st.caption(f"Tabela carregada: {df.shape[0]} linhas e {df.shape[1]} colunas.")
                        
                        # Mantém a listagem para QUALQUER coluna selecionada (sem ocultar a UI se a conversão falhar)
                        cols = df.columns.tolist()
                        
                        st.markdown("#### Gerador Gráfico Nativo Seguro")
                        
                        c_col, c_chart = st.columns(2)
                        with c_col:
                            selected_col = st.selectbox("Selecione a Métrica/Variável Y", cols)
                        with c_chart:
                            chart_type = st.selectbox("Escolha o Tipo de Gráfico", ["Histograma (Distribuição)", "Boxplot (Variação)", "Ordem / Linha do Tempo"])
                        
                        if st.button("📈 Gerar e Salvar Gráfico na Galeria", type="secondary"):
                            import altair as alt
                            try:
                                # Tentamos forçar numérico para o gráfico (Altair auto-detecta, mas forçamos pra garantir bins em str numéricos que escaparam do parser)
                                plot_df = df.copy()
                                if plot_df[selected_col].dtype == object:
                                    plot_df[selected_col] = pd.to_numeric(plot_df[selected_col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False), errors='coerce')
                                    
                                if chart_type == "Histograma (Distribuição)":
                                    chart = alt.Chart(plot_df).mark_bar(color='#0083B8').encode(
                                        alt.X(f"{selected_col}:Q", bin=alt.Bin(maxbins=30), title=selected_col),
                                        alt.Y('count()', title='Frequência'),
                                        tooltip=[alt.Tooltip(f"{selected_col}:Q", bin=True), 'count()']
                                    ).properties(height=300)
                                elif chart_type == "Boxplot (Variação)":
                                    chart = alt.Chart(plot_df).mark_boxplot(extent='min-max', color='#0083B8').encode(
                                        y=alt.Y(f"{selected_col}:Q", title=selected_col)
                                    ).properties(height=300)
                                else:
                                    chart = alt.Chart(plot_df.reset_index()).mark_line(point=True, color='#0083B8').encode(
                                        x=alt.X('index:Q', title='Amostra (Ordem Cronológica)'),
                                        y=alt.Y(f"{selected_col}:Q", title=selected_col),
                                        tooltip=['index', selected_col]
                                    ).properties(height=300)
                                
                                chart_dict = chart.to_dict()
                                state_charts_key = f"cap_saved_charts_{tool}"
                                if state_charts_key not in st.session_state:
                                    st.session_state[state_charts_key] = []
                                    
                                st.session_state[state_charts_key].append({
                                    "title": f"{chart_type} - {selected_col}",
                                    "spec": chart_dict
                                })
                                st.success(f"Gráfico '{chart_type}' gerado e anexado à Galeria abaixo!")
                            except Exception as e:
                                st.warning(f"Erro ao renderizar gráfico nativo para os dados fornecidos. Eles podem ser puramente em texto. O erro interno foi: {e}")
                                    
                        # --- Espaço para Galeria ---
                        st.markdown("---")
                        st.markdown("### 🖼️ Painel de Gráficos Gerados")
                        state_charts_key = f"cap_saved_charts_{tool}"
                        
                        if state_charts_key in st.session_state and st.session_state[state_charts_key]:
                            for idx, c_data in enumerate(st.session_state[state_charts_key]):
                                st.markdown(f"**{c_data['title']}**")
                                import altair as alt
                                try:
                                    st.altair_chart(alt.Chart.from_dict(c_data['spec']), use_container_width=True)
                                except: pass
                                
                                if st.button(f"🗑️ Remover Gráfico", key=f"btn_remove_chart_{idx}"):
                                    st.session_state[state_charts_key].pop(idx)
                                    st.rerun()
                        else:
                            st.info("Nenhum gráfico gerado ainda. Selecione e clique em Gerar acima.")
                else:
                    doc_text = parse_doc(uploaded_file)
                    st.text_area("Preview do Documento", doc_text[:1000] + "...", height=150, disabled=True)
                    
            st.markdown("---")
            b_chat_1 = st.button("✨ 1. Orientar Quais Dados Coletar e Definir Limites (IA)", disabled=read_only, use_container_width=True)
            b_chat_2 = st.button("📊 2. Calcular Distribuição / Nível Sigma (Requer Dados)", disabled=read_only or df is None, use_container_width=True)
            
            st.markdown("---")
            st.markdown("### 💾 Salvar Módulo de Capabilidade Oficial")
            if not read_only:
                if st.button("Resumir a Análise e Salvar Todo o Estudo Científico", type="primary", use_container_width=True):
                    with st.spinner("Compilando e salvando relatório consolidado (Conclusão + Gráficos)..."):
                        import coach_extensions
                        resume_payload = "Aja como o Diretor Master Black Belt. Faça um laudo de fechamento conclusivo sobre nossa análise de capabilidade e nível de sigma da nossa conversa com base nos meus dados. Diga que agora ele será registrado oficialmente."
                        ans = coach_extensions.analyze_measurement_data(
                            project_state, "Gerar Conclusão Definitiva", resume_payload, st.session_state.get(f"cap_chat_logs_{tool}", [])
                        )
                        final_msg = ans.get("resposta", "Análise salva com sucesso e sem ressalvas.")
                        
                        # Pack graphs if present
                        saved_charts = st.session_state.get(f"cap_saved_charts_{tool}", [])
                        
                        rel = {
                            "id": f"cap_oficial_{tool.split(' - ')[0]}_{pd.Timestamp.now().strftime('%H%M%S')}",
                            "title": f"Laudo de Capabilidade Oficial - {tool.split(' - ')[0]}",
                            "date": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"),
                            "summary": final_msg,
                            "charts": saved_charts
                        }
                        
                        reports_key = f"capabilidade_oficial_relatorios_{tool}"
                        my_reports = project_state.get(reports_key, [])
                        my_reports.append(rel)
                        project_state[reports_key] = my_reports
                        
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"], project_state.get("allow_teacher_view", True))
                        
                        # Limpa sessão prosximos projetos
                        st.session_state[f"cap_chat_logs_{tool}"] = []
                        st.session_state[f"cap_saved_charts_{tool}"] = []
                        
                        st.success("Relatório Definitivo Gerado e Salvo com Sucesso! Leia abaixo.")
                        st.rerun()

            st.markdown("---")
            st.markdown("### 📋 Seus Laudos de Capabilidade Salvos")
            reports_key = f"capabilidade_oficial_relatorios_{tool}"
            laudos = project_state.get(reports_key, [])
            
            if not laudos:
                st.caption("Ainda não há laudos de capabilidade gravados neste projeto.")
            else:
                for idx_laudo, laudo in enumerate(reversed(laudos)):
                    with st.expander(f"{laudo['title']} - Criado em {laudo['date']}", expanded=(idx_laudo == 0)):
                        st.markdown(laudo['summary'])
                        if laudo.get('charts'):
                            st.markdown("#### 🖼️ Gráficos Anexados ao Relatório")
                            for c_data in laudo['charts']:
                                import altair as alt
                                try:
                                    st.markdown(f"_{c_data['title']}_")
                                    st.altair_chart(alt.Chart.from_dict(c_data['spec']), use_container_width=True)
                                except: pass
                        if not read_only:
                            if st.button("Sinalizar Limpeza / Deletar", key=f"del_laudo_{laudo['id']}"):
                                proj_reports = project_state.get(reports_key, [])
                                proj_reports = [r for r in proj_reports if r['id'] != laudo['id']]
                                project_state[reports_key] = proj_reports
                                db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"], project_state.get("allow_teacher_view", True))
                                st.rerun()
                    
        with colChat:
            state_log_key = f"cap_chat_logs_{tool}"
            if state_log_key not in st.session_state:
                st.session_state[state_log_key] = []
            
            trigger_coach = False
            initial_query = ""
            
            if b_chat_1:
                problem_stmt = project_state.get("charter", {}).get("problem", "Nenhum problema foi definido ainda.")
                initial_query = f"Sou o aluno Lean Seis Sigma. Baseando-se APENAS neste problema do Project Charter ['{problem_stmt}'], me oriente: Quais dados exatos eu deveria coletar para medir a capabilidade atual da minha operação contínua? Me explique de forma muito simples como eu posso determinar sozinho qual meu Limite Inferior (LSE) ou Limite Superior (LIE) (Limite entre o bom e o ruim), e diga por que essa linguagem é importante. Não calcule nada ainda."
                st.session_state[state_log_key].append({"role": "user", "content": "Quais dados eu preciso coletar e como defino os limites do meu problema?"})
                trigger_coach = True
                
            elif b_chat_2:
                initial_query = f"Tenho dados inseridos. Analise-os para gerar a Capabilidade Contínua. IDENTIFIQUE qual é o meu Limite Superior ou Inferior baseado na nossa conversa prévia ou meta empírica e calcule o Cpk, Ppk e encontre o Nível Sigma nativo destes dados de acordo. Se tiver DPMO, explicite. Também crie um Histograma representativo (Distribuição dos Dados) pelo Vega-Lite."
                st.session_state[state_log_key].append({"role": "user", "content": "Gere a Análise de Capabilidade Estatística e o Histograma."})
                trigger_coach = True
                
            if trigger_coach:
                with st.spinner("Analisando matematicamente os dados e o problema..."):
                    import coach_extensions
                    data_str_context = "Nenhuma tabela enviada."
                    if df is not None:
                        data_str_context = f"Amostra dos Dados (DataFrame - Shape {df.shape}):\n{df.head(20).to_csv(index=False)}"
                    elif doc_text:
                        data_str_context = f"Resumo do Documento:\n{doc_text[:3000]}"
                    
                    resultado_json = coach_extensions.analyze_measurement_data(
                        project_state, 
                        data_str_context, 
                        initial_query, 
                        st.session_state[state_log_key][:-1] # Manda histórico
                    )
                    
                    if resultado_json and "resposta" in resultado_json:
                        msg_ass = {"role": "assistant", "content": resultado_json["resposta"]}
                        if "vega_lite" in resultado_json and isinstance(resultado_json["vega_lite"], dict) and resultado_json["vega_lite"].get("data"):
                            msg_ass["vega_lite"] = resultado_json["vega_lite"]
                        st.session_state[state_log_key].append(msg_ass)
                        
                        # Auto-save no backend para o chat na tela de Capabilidade continuar na aba
                        st_key_db = f"cap_chat_historico_{tool}"
                        project_state[st_key_db] = st.session_state[state_log_key]
                        db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"], project_state.get("allow_teacher_view", True))

            chat_container = st.container(height=500)
            
            # Se houver histórico salvo carrega do projeto 
            # (isso é feito aqui para sincronia, mas pra nao bagunçar o estado vivo da tab)
            st_key_db = f"cap_chat_historico_{tool}"
            if len(st.session_state[state_log_key]) == 0 and project_state.get(st_key_db):
                st.session_state[state_log_key] = project_state[st_key_db]
                
            for msg in st.session_state[state_log_key]:
                is_user = msg["role"] == "user"
                with chat_container.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if not is_user and "vega_lite" in msg and msg["vega_lite"]:
                        try:
                            import altair as alt
                            chart = alt.Chart.from_dict(msg["vega_lite"])
                            st.altair_chart(chart, use_container_width=True)
                        except Exception as e:
                            st.caption(f"Não foi possível renderizar o gráfico gerado: {str(e)}")
                            
            if not read_only:
                user_msg = st.chat_input("Dúvidas extras ou refinar valores das especificações...")
                if user_msg:
                    st.session_state[state_log_key].append({"role": "user", "content": user_msg})
                    st.rerun()
                    
            # Acionador do backend se a última msg for do user e n for o botão
            if len(st.session_state[state_log_key]) > 0 and st.session_state[state_log_key][-1]["role"] == "user":
                with chat_container.chat_message("assistant"):
                    with st.spinner("Analisando matematicamente..."):
                        import coach_extensions
                        data_str_context = "Nenhuma tabela enviada."
                        if df is not None:
                            data_str_context = f"Amostra dos Dados (DataFrame - Shape {df.shape}):\n{df.head(20).to_csv(index=False)}"
                        elif doc_text:
                            data_str_context = f"Resumo do Documento:\n{doc_text[:3000]}"
                        
                        resultado_json = coach_extensions.analyze_measurement_data(
                            project_state, 
                            data_str_context, 
                            st.session_state[state_log_key][-1]["content"], 
                            st.session_state[state_log_key][:-1]
                        )
                        
                        if resultado_json and "resposta" in resultado_json:
                            msg_ass = {"role": "assistant", "content": resultado_json["resposta"]}
                            if "vega_lite" in resultado_json and isinstance(resultado_json["vega_lite"], dict) and resultado_json["vega_lite"].get("data"):
                                msg_ass["vega_lite"] = resultado_json["vega_lite"]
                            st.session_state[state_log_key].append(msg_ass)
                            
                            project_state[st_key_db] = st.session_state[state_log_key]
                            db.upsert_project(pid, project_state["name"], project_state, project_state["user_id"], project_state["allow_teacher_edit"], project_state.get("allow_teacher_view", True))
                            st.rerun()
