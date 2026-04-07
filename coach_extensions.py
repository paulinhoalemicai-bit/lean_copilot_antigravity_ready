import json
import os
from .coach import _chat_json

def suggest_ishikawa_eval(project_state, effect):
    prompt = f"""Atue como um Master Black Belt Lean Seis Sigma analítico.
Contexto: {project_state.get('name')} - {project_state.get('charter', {}).get('problem', '')}

Problema Central (Cabeça do Peixe): {effect}

Você deve conduzir um brainstorming e sugerir Causas Primárias (nível 1 apenas) para este problema.
Divida suas sugestões apenas nos 6M's clássicos.
NÃO sugira causas profundas (níveis 2, 3), apenas os grandes grupos direcionadores.
Retorne EXATAMENTE e APENAS UM JSON com a chave "rows" sendo uma lista de objetos, com as chaves 'categoria' e 'causa'. 
Exemplo: {{"rows": [ {{"categoria": "Máquina", "causa": "Falta de manutenção"}}] }}
"""
    try:
        out = _chat_json(prompt, "Gere as causas.")
        return out.get("rows", [])
    except Exception as e:
        print("Erro na IA Ishikawa:", e)
        return []

def suggest_valida_causa(client, model, project_context, causa_nome, dados_input, estatistico=False):
    perfil_validador = "estatístico rigoroso e analista de dados" if estatistico else "avaliador empírico e analítico de processos"
    prompt = f"""Atue como um {perfil_validador} em Lean Seis Sigma.
Contexto do Projeto: {project_context}
O aluno deseja validar a causa potencial: '{causa_nome}'.

Ele inseriu esta evidência/dados coletados:
'''
{dados_input}
'''

Sua Tarefa:
1. Avalie a QUALIDADE da evidência. É apenas uma opinião fraca, dados confusos, ou realmente prova a relação de causa/efeito?
2. Se a evidência não é suficiente, NEGE a validação duramente e informe que os dados são inconclusivos.
3. Se for suficiente (mesmo analiticamente para coisas simples), declare que a hipótese pode ser validada.
IMPORTANTE: Não invente conclusões se os dados forem lixo.
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{'role':'user', 'content': prompt}],
            temperature=0.2
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
