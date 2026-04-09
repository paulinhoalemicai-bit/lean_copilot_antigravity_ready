import json
import os
import traceback
from coach import client

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
            model="gpt-4o-mini",
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
            model="gpt-4o-mini",
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
            model="gpt-4o-mini",
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
Avalie cada solução atribuindo uma nota de 1 a 5 para Custo (1=muito caro, 5=muito barato/gratis), Esforço (1=muito dificil, 5=muito facil), Impacto (1=pouco impacto, 5=muito impacto na causa).
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
            model="gpt-4o-mini",
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
Avalie a solução atribuindo uma nota de 1 a 5 para Custo (1=muito caro, 5=muito barato/gratis), Esforço (1=muito dificil, 5=muito facil), Impacto (1=pouco impacto, 5=muito impacto na causa).
Forneça um Comentário descrevendo Prós e Contras da solução.

Retorne EXATAMENTE UM JSON com formato:
{{"solucao": "...", "custo": 4, "esforco": 3, "impacto": 5, "comentario": "Prós: ... Contras: ..."}}
Apenas o JSON object e nada mais.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
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

def suggest_acao_5w2h(client, model, solucao):
    prompt = f"""Para a solução: '{solucao}'
Sugira apenas o 'O que (What)' e o 'Como (How)' do plano de ação para implantar essa solução.
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{'role':'user', 'content': prompt}],
            temperature=0.4
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erro na IA: {e}"

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
            model="gpt-4o-mini",
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
