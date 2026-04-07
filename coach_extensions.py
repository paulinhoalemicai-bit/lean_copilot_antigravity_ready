def suggest_ishikawa_eval(client, model, project_context, current_ishikawa):
    prompt = f"""Atue como um Master Black Belt Lean Seis Sigma analítico.
Contexto do Projeto: {project_context}

O aluno construiu a seguinte estrutura de Ishikawa para o Efeito/Problema ({current_ishikawa.get('effect', '')}):
{current_ishikawa.get('causes_tree', {})}

Sua Tarefa (Avaliação):
1. Avalie o mérito e clareza da decomposição das causas (não se preocupe de qual grupo 6M ela pertence).
2. Verifique se há repetições excessivas ou confusão óbvia entre causa raiz vs. sintoma.
3. Forneça um feedback construtivo curto. Responda em Markdown.
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{'role':'user', 'content': prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erro na IA: {e}"

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
