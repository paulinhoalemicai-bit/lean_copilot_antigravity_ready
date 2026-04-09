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
def suggest_solucoes_basico(client, model, root_causes):
    prompt = f"""Atue como Master Black Belt Lean.
Para as seguintes Causas Raízes Validadas: {root_causes}
Pense em até 5 soluções totais para eliminá-las.
Descreva os prós e contras textualmente usando a matriz B.A.S.I.C.O na explicação qualitativa, SEM atribuir pontuação numérica.
Responda em formato markdown estruturado.
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
