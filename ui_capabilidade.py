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
            return pd.read_csv(file)
        elif ext in ['xls', 'xlsx']:
            return pd.read_excel(file)
        else:
            return None
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
                else:
                    doc_text = parse_doc(uploaded_file)
                    st.text_area("Preview do Documento", doc_text[:1000] + "...", height=150, disabled=True)
                    
            st.markdown("---")
            coach_btn = st.button("✨ Orientar Cálculo de Capabilidade (IA)", disabled=read_only, use_container_width=True)
                    
        with colChat:
            state_log_key = f"cap_chat_logs_{tool}"
            if state_log_key not in st.session_state:
                st.session_state[state_log_key] = []
            
            if coach_btn:
                problem_stmt = project_state.get("charter", {}).get("problem", "Nenhum problema definido no Project Charter ainda.")
                initial_query = f"Avalie as informações disponíveis e me guie em como calcular a Capabilidade do Processo (Cpk, Ppk, Z.Score). Use shift de 1.5 caso converta para Sigma. O Problema Central do meu projeto é: '{problem_stmt}'. Analise também se os dados (se enviados) estão corretos para isso e crie o gráfico de distribuição (Histograma) pelo Vega-Lite."
                
                st.session_state[state_log_key].append({"role": "user", "content": "Me oriente e calcule a capabilidade."})
                
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
