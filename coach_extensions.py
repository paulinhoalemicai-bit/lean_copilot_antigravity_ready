import json
import traceback
from coach import client, get_model

def suggest_ishikawa_eval(project_state, effect):
    prompt = f"""Atue como um Master Black Belt Lean Seis Sigma analítico.
Contexto: {project_state.get('name')} - {project_state.get('charter', {}).get('problem', '')}
Problema Central (Cabeça do Peixe): {effect}

Você deve conduzir um brainstorming e sugerir Causas Primárias (nível 1 apenas) para este problema.
Divida suas sugestões nos 6M's (Máquina, Método, Material, Mão de Obra, Meio Ambiente, Medida).
Retorne EXATAMENTE UM JSON em formato válido:
{{"rows": [{{"categoria": "...", "causa": "..."}}, ...]}}
"""
    try:
        response = client.chat.completions.create(
            model=get_model(),
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Gere a matriz 6Ms de causas."}
            ]
        )
        data = json.loads(response.choices[0].message.content or "{}")
        return data.get("rows", [{"categoria": "ERRO AI", "causa": "Respondeu vazio."}])
    except Exception as e:
        err = traceback.format_exc()
        return [{"categoria": "FALHA CÓDIGO", "causa": str(e)[:150]}]

def suggest_modelo_validacao(project_state, causa_nome, parent_causa_nome, effect_n0, focus):
    perfil = "analista de dados pragmático" if focus == "Simples" else "estatístico avançado"
    c_context = f"Causa Pai Imediata: {parent_causa_nome}\nEfeito Global (Y do 5 Porquês): {effect_n0}\n" if parent_causa_nome else f"Efeito Global (Y do 5 Porquês): {effect_n0}\n"
    prompt = f"""Atue como {perfil}.
Contexto do Projeto: {project_state.get('name', 'N/A')}
{c_context}Causa a Validar (Foco Principal): {causa_nome}

Sugira brevemente (em 1 ou 2 frases curtas) COMO validar se essa Causa a Validar é verdadeira. 
Para isso, sugira prioritariamente comparar os dados dessa causa com a Causa Pai Imediata. Caso seja uma causa de nível muito profundo e faça mais sentido/seja mais simples, sugira comparar a causa com o Efeito Global (Y).
Não use "eu recomendo" ou "eu sugiro", vá direto ao ponto com a ação que o usuário deve tomar.
"""
    try:
        response = client.chat.completions.create(
            model=get_model(),
            temperature=0.4,
            messages=[{"role":"user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erro na IA: {e}"

def analyze_validation_data(project_state, causa_nome, dados_input):
    prompt = f"""Atue como um Master Black Belt avaliador RIGOROSO.
Causa a validar: '{causa_nome}'.
O aluno coletou os seguintes dados/observações:
'''
{dados_input}
'''
Tarefa:
1. Avalie a qualidade da prova. É apenas "achismo", "testei aqui", ou há sustentação lógica/analítica?
2. Se a prova for ruim ou insuficiente, RECUSE validar imediatamente explicando o que faltou mostrar.
3. Se a prova for suficiente, concorde e conclua com o aluno.
Seja técnico e direto.
"""
    try:
        response = client.chat.completions.create(
            model=get_model(),
            temperature=0.2,
            messages=[{"role":"user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erro na IA: {e}"
def suggest_5_solucoes_basico(project_state, effect, ancestrais, causa_raiz):
    import json
    prompt = f"""Atue como Master Black Belt Lean.
Contexto do Projeto / Efeito Global: {effect}
Trilha do Problema (Ancestrais): {ancestrais}
Causa Raiz em Foco: {causa_raiz}

Pense em até 5 soluções totais para mitigar ou eliminar essa causa raiz.
Avalie cada solução atribuindo uma nota de 1 a 5 para Custo (1=muito barato, 5=muito caro), Esforço (1=muito fácil, 5=muito difícil), Impacto (1=pouco impacto, 5=muito impacto). Ou seja, 5 sempre representa ALTO custo, ALTO esforço, ALTO impacto.
Forneça um Comentário descrevendo Prós e Contras da solução.

Retorne EXATAMENTE UM JSON com formato:
[
  {{"solucao": "...", "custo": 4, "esforco": 3, "impacto": 5, "comentario": "Prós: ... Contras: ..."}},
  ...
]
Apenas o JSON array e nada mais.
"""
    try:
        response = client.chat.completions.create(
            model=get_model(),
            messages=[{'role':'user', 'content': prompt}],
            temperature=0.4
        )
        content = response.choices[0].message.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        data = json.loads(content)
        if isinstance(data, dict) and "solucoes" in data:
            return data["solucoes"]
        if isinstance(data, dict): # just in case it returns an object with a key array
            for k in data:
                if isinstance(data[k], list): return data[k]
        return data if isinstance(data, list) else []
    except Exception as e:
        return [{"solucao": "Erro ao gerar", "custo":1, "esforco":1, "impacto":1, "comentario": str(e)}]

def suggest_1_solucao_basico(project_state, effect, ancestrais, causa_raiz):
    import json
    prompt = f"""Atue como Master Black Belt Lean.
Contexto do Projeto / Efeito Global: {effect}
Trilha do Problema (Ancestrais): {ancestrais}
Causa Raiz em Foco: {causa_raiz}

Pense em 1 solução excelente para mitigar ou eliminar essa causa raiz.
Avalie a solução atribuindo uma nota de 1 a 5 para Custo (1=muito barato, 5=muito caro), Esforço (1=muito fácil, 5=muito difícil), Impacto (1=pouco impacto, 5=muito impacto). Ou seja, 5 sempre representa ALTO custo, ALTO esforço, ALTO impacto.
Forneça um Comentário descrevendo Prós e Contras da solução.

Retorne EXATAMENTE UM JSON com formato:
{{"solucao": "...", "custo": 4, "esforco": 3, "impacto": 5, "comentario": "Prós: ... Contras: ..."}}
Apenas o JSON object e nada mais.
"""
    try:
        response = client.chat.completions.create(
            model=get_model(),
            messages=[{'role':'user', 'content': prompt}],
            temperature=0.5
        )
        content = response.choices[0].message.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        data = json.loads(content)
        return data
    except Exception as e:
        return {"solucao": "Erro ao gerar", "custo":1, "esforco":1, "impacto":1, "comentario": str(e)}

def suggest_acao_5w2h(project_state, causa, solucao):
    import json
    prompt = f"""Atue como um gerente de projetos e Lean Master Black Belt.
Contexto: Este Plano de Ação é parte de um projeto DMAIC na Fase de MELHORIA (Improve). As atividades prévias de medição e validação lógica dessa causa raiz já foram realizadas.

Problema / Causa Raiz: {causa}
Solução Escolhida: {solucao}

Sua tarefa: Desdobre essa Solução em ações táticas sequenciais, descrevendo "O Que" deve ser feito e o "Como" focado ESTRITAMENTE NA IMPLANTAÇÃO DA MELHORIA.
Atenção: NÃO crie ações pertinentes à Fase de Controle (ex: criar dashboards de acompanhamento permanente, definir rotinas de auditoria, monitorar kpis a longo prazo), pois o "Plano de Controle" será uma ferramenta usada no futuro. Limite-se estritamente à execução da solução.

Pense em 2 a 5 etapas lógicas para implantar essa solução com eficiência. Não crie passos desnecessários.

Retorne EXATAMENTE UM JSON ARRAY de strings, onde cada string é uma ação. 
Exemplo de formato:
[
  "Ação 1: [O que] realizar xpto através de [Como] abc.",
  "Ação 2: [O que] testar abcd através de [Como] rty."
]
Apenas o JSON e nada mais.
"""
    try:
        response = client.chat.completions.create(
            model=get_model(),
            messages=[{'role':'user', 'content': prompt}],
            temperature=0.3
        )
        content = response.choices[0].message.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        data = json.loads(content)
        if isinstance(data, list) and len(data) > 0:
            return data
        return [content]
    except Exception as e:
        return [f"Ação sugerida 1: Iniciar planejamento da solução (Erro na IA: {str(e)})"]
def suggest_pratica_validacao(project_state, causa_nome, modelo_validacao):
    prompt = f"""Atue como um Master Black Belt.
Contexto: {project_state.get('name', 'N/A')}
Causa a validar: {causa_nome}
Modelo Macro de Validação: {modelo_validacao}

Seu objetivo é sugerir "Como" coletar os dados na prática e qual o "Tamanho da Amostra" recomendado em 2 seções separadas exatas.
Não faça introduções. Retorne a resposta EXATAMENTE no seguinte formato:
COMO: [sua sugestão prática e direta de como fazer a coleta/validação no genba]
AMOSTRA: [sua sugestão de tamanho do N ou período de tempo]"""
    try:
        from coach import client
        response = client.chat.completions.create(
            model=get_model(),
            temperature=0.3,
            messages=[{"role":"user", "content": prompt}]
        )
        content = response.choices[0].message.content
        como = ""
        amostra = ""
        for line in content.split("\n"):
            line = line.strip()
            if line.upper().startswith("COMO:"):
                como = line[5:].strip()
            elif line.upper().startswith("AMOSTRA:"):
                amostra = line[8:].strip()
        if not como and not amostra:
            como = content
            amostra = "Indefinida"
        return como, amostra
    except Exception as e:
        return "Erro na IA", str(e)


def analyze_measurement_data(project_state, data_sample, user_query, chat_history):
    import json
    from coach import client, get_model

    # Montar histórico em texto
    history_text = ""
    for msg in chat_history:
        role = "Usuário" if msg["role"] == "user" else "Dr. Lean"
        history_text += f"{role}: {msg['content']}\n"
    
    prompt = f"""Atue como um Cientista de Dados Black Belt e Estatístico.
Seu papel é ajudar o aluno na fase de MEDIÇÃO do DMAIC interpretando dados.

REGRAS CRÍTICAS:
1. SE O USUÁRIO FORNECER NÚMEROS/DADOS na pergunta (ex: "tempos: 2, 3, 5, 9..."), VOCÊ DEVE REALIZAR OS CÁLCULOS! Calcule a média, moda, mediana, mínimo, máximo, e desvio padrão. Sem teorias, apenas entregue as métricas reais. Além disso, se houver uma "meta" ou "referência" (ou meta implícita no texto), calcule as PORCENTAGENS de dados ACIMA e ABAIXO da referência.
2. NUNCA DEVOLVA CÓDIGO DE PROGRAMAÇÃO EM PYTHON. 
3. Para gerar gráficos (Histograma, Box Plot, Dispersão, etc), construa o JSON nativo do Vega-Lite v5. 
   - REQUISITOS DO VEGA-LITE: A chave "data: values" deve ser um ARRAY DE OBJETOS `{{"data": {{"values": [{{"valor": 2}}, {{"valor": 3}}]}}}}`. 
   - TEMPLATE BOX PLOT VEGA-LITE: `{{"$schema": "https://vega.github.io/schema/vega-lite/v5.json", "data": {{"values": [...]}}, "mark": "boxplot", "encoding": {{"x": {{"field": "valor", "type": "quantitative"}}}}}}`
   - O gráfico ficará invisível se você não preencher a chave `encoding` corretamente, apontando exatamento para a chave que está dentro de `values`!
4. Lembrete educacional: Deixe claro em 1 frase que a análise encontra padrões matemáticos, mas a validação no processo real (GEMBA) é função humana.

DADOS DA MESA DE TRABALHO:
{data_sample}

HISTÓRICO DA CONVERSA:
{history_text}

PERGUNTA ATUAL DO USUÁRIO:
{user_query}

Sua resposta deve ser EXATAMENTE um JSON válido atendendo ao schema abaixo. NÃO MISTURE MARKDOWN ANTES OU DEPOIS DO JSON.
{{
  "resposta": "Texto objetivo com seus cálculos reais, % acima/abaixo de metas, insights e conclusões úteis (markdown habilitado).",
  "vega_lite": {{
     // OPCIONAL: Especificação JSON do Vega-Lite v5. Siga o template estritamente para não quebrar o layout.
     // Retorne null se não precisar de gráfico.
  }}
}}
"""
    try:
        # Verifica se data_sample é uma imagem base64
        if isinstance(data_sample, tuple) and data_sample[0] == "IMAGE":
            # Remove a representação estranha da imagem do prompt de texto
            prompt = prompt.replace(str(data_sample), "[[DADOS FORNECIDOS COMO IMAGEM - VEJA O ANEXO]]")
            messages_payload = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_sample[1]}}
                    ]
                }
            ]
        else:
            messages_payload = [{'role': 'user', 'content': prompt}]

        response = client.chat.completions.create(
            model=get_model("analysis"),
            messages=messages_payload,
            temperature=0.2,
            response_format={ "type": "json_object" }
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return data
    except Exception as e:
        return {"resposta": f"Ops, enfrentei um problema ao analisar os dados: {str(e)}", "vega_lite": None}
