from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from openai import OpenAI

from config import TOOL_GUIDANCE
import db

ENV_PATH = Path(__file__).with_name(".env")
load_dotenv(dotenv_path=ENV_PATH)

api_key = os.getenv("OPENAI_API_KEY", "").strip()
if not api_key:
    raise RuntimeError(
        "OPENAI_API_KEY não encontrado.\n"
        "Crie o arquivo .env na mesma pasta e coloque:\n"
        "OPENAI_API_KEY=sua_chave_aqui\n"
    )

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
client = OpenAI(api_key=api_key)


def new_session_id() -> str:
    return str(uuid.uuid4())


def _clean_text(s: str) -> str:
    if not s:
        return ""
    out = s
    replacements = {
        "baseline": "valor atual",
        "target": "valor desejado",
        "timestamp": "data/hora de registro",
        "<TARGET_%_ONTIME>": "<VALOR_DESEJADO>",
        "<BASELINE_PICO>": "<VALOR_ATUAL>",
    }
    for old, new in replacements.items():
        out = re.sub(re.escape(old), new, out, flags=re.IGNORECASE)
    return out


def _clean_json_payload(obj: Any) -> Any:
    if isinstance(obj, str):
        return _clean_text(obj)
    if isinstance(obj, list):
        return [_clean_json_payload(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _clean_json_payload(v) for k, v in obj.items()}
    return obj


def _parse_json_from_text(text: str) -> Dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])
    raise ValueError("Não foi possível interpretar JSON.")


def _chat_json(system: str, user: str) -> Dict[str, Any]:
    response = client.chat.completions.create(
        model=db.get_global_model(),
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    raw = response.choices[0].message.content or "{}"
    obj = _parse_json_from_text(raw)
    return _clean_json_payload(obj)


def _base_system(tool: str) -> str:
    guidance = TOOL_GUIDANCE.get(tool, "")
    return f"""
Você é um copiloto Lean Seis Sigma com foco em coaching metodológico.
Responda em português claro, didático e direto.
Não use termos em inglês se houver equivalente simples em português.
Evite jargões desnecessários.

Regras:
- Não confunda "preenchido" com "bem definido"
- Se estiver vago, trate como lacuna
- Faça perguntas curtas e úteis
- No Project Charter, não entre em causa raiz
- No SIPOC por etapa, analise por etapa e não o processo inteiro
- No VOC/VOB, preserve foco em necessidade, problema, requisito crítico e Y

Contexto da ferramenta:
{guidance}

Sua resposta deve ser JSON com estas chaves:
- ok: lista de strings
- gaps: lista de objetos com chaves id, severity, reason
- questions: lista de strings
- next_action: string
- allow_generate: boolean
- candidates: lista de objetos com chaves title, draft, why, how_to_test
""".strip()


def coach_run(
    tool: str,
    project_state: Dict[str, Any],
    draft_text: str,
    mode: str = "review",
    user_id: str = "local_user",
) -> Tuple[Dict[str, Any], Dict[str, int], List[Dict[str, Any]]]:
    system = _base_system(tool)
    user = f"""
Instrução CRÍTICA: Você deve avaliar ÚNICA E EXCLUSIVAMENTE o "Conteúdo Desta Ferramenta".
Use o "Estado Todo" apenas para contexto de leitura, mas NÃO aponte erros que o aluno cometeu em outras partes ou ferramentas passadas. Foque o seu feedback somente no que está construído para a ferramenta atual que ele está acessando.

Ferramenta atual sendo trabalhada: {tool}

Conteúdo Desta Ferramenta (FOCO TOTAL DO FEEDBACK):
{draft_text}

Estado Todo do Projeto (Apenas Consulta para ler contexto, ignorar defeitos deste JSON em sua avaliação):
{json.dumps(project_state, ensure_ascii=False, indent=2)}

Tarefa:
1. Liste pontualmente coisas que estão boas (apenas no conteúdo da ferramenta atual) em "ok"
2. Liste lacunas lógicas, metodológicas ou defeitos da ferramenta atual sendo preenchida em "gaps"
3. Faça 1 a 3 perguntas essenciais para provocar a reflexão
4. Dê 1 próximo passo sugerido em "next_action"
5. Defina "allow_generate" (bool)
6. Se mode="generate", inclua até 4 sugestões de complemento em "candidates"

Formatação dos gaps:
- id: algo curto e claro, de preferência no padrão RUBRIC.<Ferramenta>.<Campo>
- severity: high, medium ou low
- reason: em português, começando por "Atenção: ..." ou "Problema: ..."
""".strip()

    try:
        coach_json = _chat_json(system, user)
    except Exception as e:
        coach_json = {
            "ok": [],
            "gaps": [
                {
                    "id": "SYSTEM.FAIL",
                    "severity": "high",
                    "reason": f"Gap Sistema: falha ao chamar a IA ({str(e)})",
                }
            ],
            "questions": ["Tente novamente após revisar sua chave e conexão."],
            "next_action": "Revisar a configuração da API e tentar de novo.",
            "allow_generate": False,
            "candidates": [],
        }

    rubric_scores: Dict[str, int] = {}
    gaps_hint: List[Dict[str, Any]] = []
    return coach_json, rubric_scores, gaps_hint


def suggest_serpentes_steps(project_state: dict, hint: str = "") -> dict:
    system = """
Você é especialista em mapeamento de processos.
Sugira macro etapas (diagrama de serpentes) em sequência.
Use português simples.
Responda JSON com:
- macro_etapas: lista de strings
""".strip()

    user = f"""
Contexto do projeto:
{json.dumps(project_state, ensure_ascii=False, indent=2)}

Dica opcional:
{hint}

Gere de 5 a 10 macro etapas em nível macro, do início ao fim do processo.
""".strip()

    try:
        out = _chat_json(system, user)
        steps = out.get("macro_etapas", []) or []
        steps = [str(x).strip() for x in steps if str(x).strip()]
        return {"macro_etapas": steps}
    except Exception:
        return {"macro_etapas": []}


def suggest_sipoc_by_step(project_state: dict, serp_steps: List[str]) -> dict:
    system = """
Você é especialista em SIPOC por etapa.
Para cada etapa P, sugira:
- fornecedores (S)
- entradas (I)
- saídas (O)
- clientes (C)

Regras:
- Trabalhe por etapa, não pelo processo inteiro
- Mantenha coerência: S fornece I; C recebe O
- Use listas curtas
- Português simples

Responda JSON com:
- observacoes: string
- rows: lista de objetos com chaves p, s, i, o, c
""".strip()

    user = f"""
Contexto do projeto:
{json.dumps(project_state, ensure_ascii=False, indent=2)}

Etapas P:
{json.dumps(serp_steps, ensure_ascii=False, indent=2)}

Gere sugestões por etapa.
""".strip()

    try:
        out = _chat_json(system, user)
        rows = out.get("rows", []) or []
        clean_rows = []
        for r in rows:
            p = str(r.get("p", "")).strip()
            if not p:
                continue
            clean_rows.append(
                {
                    "p": p,
                    "s": [str(x).strip() for x in (r.get("s") or []) if str(x).strip()],
                    "i": [str(x).strip() for x in (r.get("i") or []) if str(x).strip()],
                    "o": [str(x).strip() for x in (r.get("o") or []) if str(x).strip()],
                    "c": [str(x).strip() for x in (r.get("c") or []) if str(x).strip()],
                }
            )
        return {
            "observacoes": str(out.get("observacoes", "") or ""),
            "rows": clean_rows,
        }
    except Exception as e:
        return {"observacoes": f"Falha ao gerar sugestões: {str(e)}", "rows": []}


def suggest_charter_from_vocvob(project_state: dict, voc_text: str) -> Dict[str, Any]:
    system = """
Você é especialista em Lean Seis Sigma.
A partir do VOC/VOB, gere sugestões editáveis para Project Charter.

Regras:
- Gere 3 opções
- Cada opção deve ter:
  - title
  - draft (com 2 linhas: 'Problema: ...' e 'Objetivo: ...')
  - why
  - how_to_test
- Problema: 1 frase clara, sem causa raiz
- Objetivo: SMART, em português simples

Responda JSON com:
- candidates: lista de objetos
""".strip()

    user = f"""
Contexto do projeto:
{json.dumps(project_state, ensure_ascii=False, indent=2)}

VOC/VOB:
{voc_text}

Gere as sugestões.
""".strip()

    try:
        out = _chat_json(system, user)
        cands = out.get("candidates", []) or []
        clean = []
        for c in cands:
            clean.append(
                {
                    "title": str(c.get("title", "")).strip(),
                    "draft": str(c.get("draft", "")).strip(),
                    "why": str(c.get("why", "")).strip(),
                    "how_to_test": str(c.get("how_to_test", "")).strip(),
                }
            )
        return {"candidates": clean}
    except Exception as e:
        return {
            "candidates": [
                {
                    "title": "Falha ao gerar sugestão",
                    "draft": "",
                    "why": str(e),
                    "how_to_test": "",
                }
            ]
        }

def generate_problem_benefits_from_vocvob(project_state: dict, impact_answer: str) -> Dict[str, str]:
    vocvob_data = project_state.get("voc_vob", {})
    
    system = """
Você é um Master Black Belt orientando a escrita de um Project Charter corporativo.
Sua missão é gerar duas coisas baseadas nas necessidades estruturadas (VOC/VOB) preenchidas pelo usuário e no "Impacto" relatado por ele.

1. "problem": Escreva um texto narrativo e coeso definindo o Problema/Justificativa. O padrão metodológico EXIGE:
- Introdução sobre o cenário atual.
- O valor atual de performance do processo.
- Como o cliente está sendo afetado por isso (consequências).

2. "benefits": Descreva os benefícios esperados, focando em declarar o oposto direto das consequências do problema citadas (ganhos financeiros, operacionais ou satisfação).

Retorne EXATAMENTE um objeto JSON:
{
  "problem": "texto do problema",
  "benefits": "texto dos benefícios"
}
""".strip()

    user = f"""
DADOS DA TABELA VOC/VOB DO PROJETO:
{json.dumps(vocvob_data, ensure_ascii=False, indent=2)}

PERGUNTA DE DIRECIONAMENTO:
Qual o impacto sofrido pelo cliente de não ter a sua necessidade atendida?
Resposta do Aluno: {impact_answer}

Gere o Problema e os Benefícios.
""".strip()

    try:
        out = _chat_json(system, user)
        return {
            "problem": str(out.get("problem", "N/A")).strip(),
            "benefits": str(out.get("benefits", "N/A")).strip()
        }
    except Exception as e:
        return {
            "problem": f"Erro IA: {str(e)}",
            "benefits": f"Erro IA"
        }

def generate_smart_goal_from_charter_context(project_state: dict, tempo: str, meta: str) -> str:
    charter_data = project_state.get("charter", {})
    
    system = """
Você é um Master Black Belt de Lean Seis Sigma construindo Projetos de Melhoria.
Sua missão é gerar APENAS UMA ÚNICA FRASE unificada formatada perfeitamente como uma Meta SMART (Specific, Measurable, Achievable, Relevant, Time-bound).

Regras da Meta SMART para Seis Sigma:
- Iniciar sempre com um verbo de ação (Reduzir, Aumentar, Eliminar, Maximizar).
- Declarar o objeto/indicador focado (O que está sendo medido).
- Declarar o valor/baseline atual se for dedutível do contexto, e a Meta numérica providenciada pelo usuário.
- Finalizar taxativamente com o Prazo limite providenciado pelo usuário.
Exemplo Perfeito: "Reduzir a taxa de refugo no setor de embalagem de 15% para 5% até o final de dezembro de 2024".

Retorne APENAS o texto livre (string pura) da frase final gerada, sem formatações markdown, sem aspas, e sem explicações e conversas adicionais.
""".strip()

    user = f"""
CONTEXTO DO PROJECT CHARTER (Use para entender o que está sendo resolvido):
- Justificativa/Problema: {charter_data.get('problem', '')}
- Indicador Principal (Y): {charter_data.get('main_indicator', '')}
- Rascunho/Escopo prévio do objetivo: {charter_data.get('goal', '')}

DADOS MANDATÓRIOS DO USUÁRIO (Use-os taxativamente para o 'M' e 'T' do SMART):
- Meta de Resultado (M): {meta}
- Prazo Estipulado (T): {tempo}

Gere EXATAMENTE a frase final da Meta SMART.
""".strip()

    try:
        response = client.chat.completions.create(
            model=db.get_global_model(),
            temperature=0.2,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return str(response.choices[0].message.content or "A IA não retornou um texto válido.").strip()
    except Exception as e:
        return f"Erro IA ao gerar SMART: {str(e)}"

def suggest_sipoc_macro(project_state: dict, desc: str) -> List[str]:
    system = """
Você é um especialista Master Black Belt focado em mapeamento SIPOC.
O aluno relatará uma descrição textual de um processo. Extraia de 4 a 8 MACRO ETAPAS (P - Process) dessa descrição.
Regras:
1. Comece cada etapa com um verbo no infinitivo ou substantivo de ação forte (ex: "Receber Paciente").
2. Nível macro (não inclua micro-tarefas da mesma estação).
3. Responda APENAS em JSON estrito.
- "macro_etapas": lista de strings curtas em ordem cronológica.
""".strip()
    
    user_str = f"Contexto do Projeto:\n{json.dumps(project_state.get('name', ''), ensure_ascii=False)}\n\nDescrição Livre:\n{desc}"
    try:
        out = _chat_json(system, user_str)
        return [str(x).strip() for x in out.get("macro_etapas", []) if str(x).strip()]
    except Exception:
        return []

def suggest_sipoc_io(project_state: dict, target: str) -> list:
    current_sipoc = project_state.get("sipoc", [])
    if not current_sipoc: 
        return []
    
    steps_txt = [s.get("P", f"Etapa {i+1}") for i, s in enumerate(current_sipoc)]
    
    if target == "inputs":
        system = """
Você é um Master Black Belt. O aluno lhe passará uma lista de Etapas de um Processo (P).
Para CADA etapa sequencial da array, defina 1 a 3 Entradas vitais (I) e seus Fornecedores (S).
- Sja muito curto, no máximo 4 palavras por S e I.
- Responda JSON com a chave "rows".
- "rows": array de arrays de objetos {"S": "Fornecedor", "I": "Entrada"}.
Importante: O tamanho do array "rows" MUST BE EXATAMENTE IGUAL ao tamanho do array de Etapas enviado.
"""
    else:
        system = """
Você é um Master Black Belt. O aluno lhe passará uma lista de Etapas de um Processo (P).
Para CADA etapa sequencial da array, defina 1 a 3 Saídas resultantes (O) e o Cliente recebedor (C).
- Seja muito curto, no máximo 4 palavras por O e C.
- Responda JSON com a chave "rows".
- "rows": array de arrays de objetos {"O": "Saída", "C": "Cliente"}.
Importante: O tamanho do array "rows" MUST BE EXATAMENTE IGUAL ao tamanho do array de Etapas enviado.
"""

    user_str = f"Lista Estrita de ETAPAS (tamanho {len(steps_txt)}):\n{json.dumps(steps_txt, ensure_ascii=False)}"
    
    try:
        out = _chat_json(system, user_str)
        rows_ai = out.get("rows", [])
        
        # Sincroniza e sobrescreve
        for idx, step in enumerate(current_sipoc):
            if idx < len(rows_ai) and isinstance(rows_ai[idx], list):
                if target == "inputs":
                    step["inputs"] = rows_ai[idx]
                else:
                    step["outputs"] = rows_ai[idx]
        
        return current_sipoc
    except Exception as e:
        return current_sipoc

def suggest_saving_rationale(project_state: dict, expected_gains: str) -> dict:
    system = """
Você é um CFO (Diretor Financeiro) de uma super corporação enxuta, especialista em finanças de projetos Lean Seis Sigma.
O aluno descreveu os ganhos que espera obter no projeto no texto "expected_gains".
Você deve estruturá-los em um Racional base (Memorial de Cálculo textual) para orientar a precificação exata.

Regras Estritas para os 4 baldes financeiros (Responda estritamente em JSON com as chaves exatas informadas abaixo):
- "hard_racional": Dinheiro que a empresa GASTAVA e não vai gastar mais. Redução comprovada no custo da operação que reduz despesas (DRE).
- "faturamento_racional": Dinheiro NOVO entrando no caixa da empresa. Todo Aumento de Faturamento, Vendas extra, ticket médio.
- "soft_racional": Impactos indiretos. Ex: Ganho operacional, liberação de horas-homem transferida (horas pagas que agora cobrem novas tarefas), evitar desperdício de tempo.
- "avoidance_racional": Fuga de custo, evitar contratação futura que seria necessária se o processo continuasse ineficiente.

Retorne no máximo 3 ou 4 linhas detalhadas por campo. Comece provocando as contas matemáticas vazias que o aluno deve ir atrás de descobrir para fechar o número da tela.
Caso algum balde não faça sentido pro relato, preencha com: "Nenhum fator mapeado pelo seu relato."
""".strip()

    user_str = f"Benefícios/Ganhos prováveis citados pelo aluno:\n{expected_gains}"
    try:
        out = _chat_json(system, user_str)
        
        def _fmt(val):
            if isinstance(val, list):
                return "\n".join("- " + str(v) for v in val)
            return str(val).strip()

        return {
            "hard": _fmt(out.get("hard_racional", "")),
            "soft": _fmt(out.get("soft_racional", "")),
            "avoidance": _fmt(out.get("avoidance_racional", "")),
            "faturamento": _fmt(out.get("faturamento_racional", ""))
        }
    except Exception as e:
        return {"hard": f"Erro IA: {e}", "soft": "", "avoidance": "", "faturamento": ""}

def suggest_vocvob_row(target_type: str, q1: str, q2: str, q3: str, project_state: dict) -> Dict[str, str]:
    system = f"""
Você é especialista em Lean Seis Sigma, focando em {target_type}.
O usuário forneceu respostas cruciais para mapear a Voz.
Sua tarefa é preencher EXATAMENTE 1 linha de uma tabela (JSON) com as 4 colunas abaixo:
1. "Voz (necessidade)": Resuma a necessidade em linguagem do {target_type}.
2. "Problema": Aponte o que está falhando com base no valor/performance atual.
3. "Requisito crítico": Descreva o limite exato de satisfação vs insatisfação (CTQ/CTB).
4. "Y (indicador)": O indicador mensurável atrelado ao requisito crítico.

Retorne EXATAMENTE um objeto JSON com as chaves:
- "Voz (necessidade)": string
- "Problema": string
- "Requisito crítico": string
- "Y (indicador)": string
- "observacoes": (Opcional) uma string explicando a sugestão se necessário.
""".strip()

    user = f"""
Contexto do Projeto:
{json.dumps(project_state, ensure_ascii=False, indent=2)}

Respostas fornecidas pelo aluno:
1. Qual a necessidade do cliente/negócio? -> {q1}
2. Qual o valor/performance atual? -> {q2}
3. Qual o valor limite entre satisfação e insatisfação? -> {q3}

Preencha a linha.
""".strip()

    try:
        out = _chat_json(system, user)
        # Extrair com chaves exatas exigidas pela interface
        return {
            "Voz (necessidade)": str(out.get("Voz (necessidade)", "N/A")).strip(),
            "Problema": str(out.get("Problema", "N/A")).strip(),
            "Requisito crítico": str(out.get("Requisito crítico", "N/A")).strip(),
            "Y (indicador)": str(out.get("Y (indicador)", "N/A")).strip()
        }
    except Exception as e:
        return {
            "Voz (necessidade)": "Erro IA",
            "Problema": str(e),
            "Requisito crítico": "",
            "Y (indicador)": ""
        }

def suggest_matriz_indicadores(project_state: dict) -> list:
    system = """
Você é um Coach Master Black Belt especialista em mapeamento e identificação de Indicadores de Processos Lean Seis Sigma.
O aluno relatará as Etapas do Processo (identificadas no SIPOC) bem como o Problema (Charter) que o projeto dele busca resolver.
Sua missão é gerar os indicadores para medir essas etapas em sete categorias diferentes, criando assim métricas precisas.

Regras Estritas para a tabela de retorno:
1. Responda em JSON EXATAMENTE no formato com a chave "rows".
2. "rows" será uma array de objetos com as seguintes chaves idênticas para cada linha:
   "Processo": a descrição da etapa original que o aluno mandou.
   "Quantidade/Volume": bullet points (prefixados por "•" ou "-") com as métricas contáveis da etapa. Ex: "- Qtd de inscrições analisadas".
   "Quantidade/Recursos": bullet points focados em capacidade de atendimento. Ex: "- Qtd de salas", "- Qtd de profissionais", "- Qtd de equipamentos alocados".
   "Quantidade em processamento (WIP)": bullet points focados em estoque em processamento/fila daquela etapa. Ex: "- Qtd inscrições aguardando resposta".
   "Tempo (Lead/Cycle Time)": bullet points do tempo entre tarefas atreladas à etapa.
   "Percentual (%)": dimensões proporcionais de controle. IMPORTANTE: Obrigatoriamente inclua neste campo uma métrica relativa que compare a Demanda atrelada à etapa vs a Capacidade Instalada para medir restrições e identificar gargalos (Ex: "% de Utilização", "% Ocupação"), baseada na Teoria das Restrições.
   "Qualidade (Erro/NPS)": proporção de defeitos, devoluções, retrabalho e satisfação relativos à etapa.
   "Financeiro (R$)": representação financeira caso aplicável (se não houver, tracejar com "-").
3. Todos os campos gerados (exceto a coluna "Processo") devem conter os indicadores em lista de tópicos em uma mesma célula/string longa com quebras de linha (\\n), se houver mais de um.
   Exemplo: "- Qtd formulários preenchidos\\n- Qtd retidos"
"""
    
    charter_data = project_state.get("charter", {})
    prob = charter_data.get("problem", "Problema não reportado no charter.")
    ind_data = project_state.get("matriz_indicadores", [])
    
    # Extrair apenas os nomes dos processos já listados
    etapas = [row.get("Processo", "") for row in ind_data if isinstance(row, dict) and row.get("Processo")]
    
    if not etapas:
        # Tenta pegar do SIPOC
        sipoc_data = project_state.get("sipoc", [])
        etapas = [s.get("P", "") for s in sipoc_data if s.get("P", "").strip()]
        
    user_str = f"Problema relatado no Charter:\n{prob}\n\nAnalise as seguintes etapas e elabore as métricas em tópicos para cada uma delas:\n{json.dumps(etapas, ensure_ascii=False)}"
    
    try:
        out = _chat_json(system, user_str)
        rows_ai = out.get("rows", [])
        return rows_ai
    except Exception as e:
        return []


def suggest_causa_efeito_impacto(project_state: dict, causas: list) -> list:
    """
    Recebe uma lista de causas (X's) e retorna uma avaliação de Impacto [1-100]
    e Esforço [1-10] para cada uma, baseado no problema do Charter.
    """
    system = """
Você é um Coach Master Black Belt especialista em Análise de Causa Raiz e priorização por Causa & Efeito (Matriz de Priorização Lean Seis Sigma).
Sua missão é analisar cada causa (X) informada e estimar:
  - "impacto": número inteiro de 0 a 100 — o quanto essa causa X contribui diretamente para o Problema relatado no Charter.
    0 = não influencia; 100 = causa principal direta.
  - "esforco": número inteiro de 0 a 100 — o quanto é difícil/custoso endereçar essa causa.
    0 = muito fácil (Baixo Esforço); 100 = extremamente complexo/caro.
  - "justificativa": 1 frase curta explicando o raciocínio do impacto.

Regras Estritas:
1. Responda APENAS em JSON com chave "rows".
2. "rows" é uma lista com um objeto por causa recebida, EXATAMENTE na mesma ordem, com as chaves: "causa", "impacto", "esforco", "justificativa".
3. Impacto e Esforço DEVEM ser números inteiros válidos (0-100), nunca strings.
4. Justificativa máximo 15 palavras.
"""
    charter_data = project_state.get("charter", {})
    prob = charter_data.get("problem", "Problema não informado no Charter.")
    causas_str = json.dumps(causas, ensure_ascii=False)
    user_str = (
        f"Problema do projeto (Charter):\n{prob}\n\n"
        f"Avalie cada uma das causas abaixo com Impacto [0-100] e Esforço [0-100]:\n{causas_str}"
    )
    try:
        out = _chat_json(system, user_str)
        return out.get("rows", [])
    except Exception:
        return []


def suggest_xs_consolidados(project_state: dict, indicadores_data: list) -> list:
    """
    Dr. Lean: Analisa TODOS os indicadores da Planilha de Indicadores e gera
    uma lista enxuta de X's primários (causas de primeiro nível abaixo do Y).

    Regras metodológicas aplicadas pela IA:
    - Agrupa indicadores redundantes ou dependentes entre si
    - Evita misturar causas profundas (por que do por quê) com causas maiores (X direto do Y)
    - Trabalha apenas no nível X1, X2... (não X1.1.1 nem causa raiz)
    - Remove indicadores meramente descritivos ou de controle que não são causas reais
    - Retorna entre 5 e 12 X's primários consolidados
    """
    system = """
Você é o Dr. Lean, um Master Black Belt com 20+ anos de experiência em projetos Lean Seis Sigma hospitalares e industriais.

Sua missão CRÍTICA é analisar a planilha completa de indicadores de um projeto e gerar uma lista de X's PRIMÁRIOS (causas de primeiro nível) para a Matriz Causa & Efeito.

CONCEITO FUNDAMENTAL — O que é um X primário:
- O Y é o PROBLEMA do projeto (o grande indicador que queremos melhorar).
- Os X's primários são as CAUSAS DIRETAS do Y — o primeiro nível de decomposição.
- Exemplo: Y = "Alto tempo de espera do paciente"
  → X primário CORRETO: "Fluxo de triagem ineficiente" (causa direta)
  → X profundo ERRADO: "Funcionário não seguiu o protocolo" (causa do X, não do Y diretamente)

REGRAS ESTRITAS DE CLASSIFICAÇÃO:
1. AGRUPE indicadores que medem o mesmo fenômeno. Ex: "Qtd de triagens/hora" + "% de triagens fora do padrão" → agrupar em "Capacidade de triagem"
2. NÃO MISTURE nível de causa: separe o X (causa maior) do sub-X (porque do X). Fique no nível de X direto do Y.
3. ELIMINE indicadores puramente descritivos/contáveis que não representam uma causa real (ex: "Quantidade de pacientes atendidos" não é causa de nada por si só).
4. PRIORIZE os X's mais frequentemente relacionados ao problema.
5. GERE entre 5 e 12 X's consolidados. Não menos que 5, não mais que 12.
6. Cada X deve ser escrito como uma CAUSA ATIVA (substantivo + contexto): ex: "Capacidade instalada insuficiente de X", "Variação no processo de Y".
7. Para cada X, estime:
   - "impacto": número inteiro de 0 a 100 (quanto esse X contribui para o Y do problema)
   - "esforco": número inteiro de 0 a 100 (dificuldade para resolver; 0=fácil, 100=muito complexo)
   - Os valores devem variar entre os Xs para refletir diferentes pesos.
   - "justificativa": frase curta (máx 15 palavras) explicando por que é um X primário relevante

Responda SOMENTE em JSON com a chave "xs":
{
  "xs": [
    {
      "indicador": "nome do X primário consolidado",
      "impacto": 80,
      "esforco": 62,
      "justificativa": "Justificativa curta em português"
    },
    ...
  ]
}
""".strip()

    charter_data = project_state.get("charter", {})
    prob = charter_data.get("problem", "Problema não informado no Charter.")
    y_indicador = charter_data.get("main_indicator", "Indicador principal não informado.")

    # Formata a planilha de indicadores de forma compacta para o prompt
    linhas_formatadas = []
    for row in indicadores_data:
        processo = str(row.get("Processo", "")).strip()
        if not processo:
            continue
        partes = [f"Processo: {processo}"]
        for col in ["Quantidade/Volume", "Quantidade/Recursos", "Quantidade em processamento (WIP)",
                    "Tempo (Lead/Cycle Time)", "Percentual (%)", "Qualidade (Erro/NPS)", "Financeiro (R$)"]:
            val = str(row.get(col, "")).strip()
            if val and val != "-":
                partes.append(f"  {col}: {val}")
        linhas_formatadas.append("\n".join(partes))

    planilha_txt = "\n\n".join(linhas_formatadas) if linhas_formatadas else "Planilha vazia."

    user_str = f"""PROBLEMA DO PROJETO (Y — o que queremos resolver):
{prob}

INDICADOR PRINCIPAL (Y):
{y_indicador}

PLANILHA COMPLETA DE INDICADORES (todos os X's candidatos mapeados por etapa):
{planilha_txt}

Com base nisso, gere os X's primários consolidados conforme as regras metodológicas.
""".strip()

    try:
        out = _chat_json(system, user_str)
        xs_raw = out.get("xs", [])
        resultado = []
        for x in xs_raw:
            indicador = str(x.get("indicador", "")).strip()
            if not indicador:
                continue
            resultado.append({
                "indicador": indicador,
                "impacto": max(0, min(100, int(round(float(x.get("impacto", 50) or 50))))),
                "esforco": max(0, min(100, int(round(float(x.get("esforco", 50) or 50))))),
                "justificativa": str(x.get("justificativa", "")).strip()
            })
        return resultado
    except Exception as e:
        return []


def suggest_plano_coleta(project_state: Dict[str, Any], causas_selecionadas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Gera sugestões de medição para cada causa ou indicador prioritário."""
    system = """
Você é um Coach Lean Seis Sigma especialista em Medição e Metrologia.
Sua missão é detalhar como coletar dados para as causas (X) ou indicadores (Y) fornecidos.
Pense em como garantir a confiabilidade dos dados (MSA), minimizando viés humano e erro de medição.

Para cada item, você deve preencher rigorosamente estas 10 propriedades:
1. "definicao": O que exatamente será medido? (Definição operacional sem ambiguidade)
2. "indicador": Nome curto do indicador (ex: Tempo de Ciclo, % de Erro)
3. "fonte": De onde vem o dado? (ex: SAP, Planilha manual, Cronometragem local)
4. "amostra": Quantos dados coletar? (ex: 30 itens, 100% da população, 5 dias úteis)
5. "responsavel": Quem coleta? (ex: Operador, Analista de Qualidade, Sistema Automático)
6. "quando": Frequência/Momento (ex: Diária ao fim do turno, Semanal, A cada peça produzida)
7. "como": Método técnico (ex: SQL Query, Paquímetro digital, Observação direta com cronômetro)
8. "outros": Variáveis secundárias/estratificação (ex: Turno, Máquina, Tipo de Material)
9. "uso": Para que serve? (ex: Validar causa raiz no Analyze, Monitorar estabilidade no Control)
10. "mostrar": Forma de visualização (ex: Gráfico de Tendência, Histograma, Pareto)

Responda SOMENTE em JSON com a chave "plano":
{
  "plano": [
    {
      "definicao": "...", "indicador": "...", "fonte": "...", "amostra": "...", "responsavel": "...",
      "quando": "...", "como": "...", "outros": "...", "uso": "...", "mostrar": "..."
    },
    ...
  ]
}
""".strip()

    charter_data = project_state.get("charter", {})
    prob = charter_data.get("problem", "Não definido.")
    y_indicador = charter_data.get("main_indicator", "Não definido.")

    causas_txt = []
    for c in causas_selecionadas:
        causas_txt.append(f"- Causa: {c.get('indicador', 'N/A')} (Justificativa: {c.get('justificativa', 'N/A')})")
    
    causas_str = "\n".join(causas_txt) if causas_txt else "Sem causas específicas. Use o Problema/Y como base."

    user_str = f"""
CONTEXTO DO PROJETO:
- Problema: {prob}
- Resultado Desejado (Y): {y_indicador}

CAUSAS (X) OU INDICADORES QUE PRECISAM DE UM PLANO DE COLETA:
{causas_str}

Gere o plano detalhado para cada item acima.
""".strip()

    try:
        out = _chat_json(system, user_str)
        return out.get("plano", [])
    except Exception:
        return []

def suggest_5_porques(project_state: dict, efeito: str) -> list:
    system = """
Você é um Coach Master Black Belt Lean Seis Sigma especialista na ferramenta 5 Porquês.
Sua missão é gerar um caminho ÚNICO, profunde, e linear de 5 Porquês para o Problema/Efeito inicial fornecido.
A técnica exige encadeamento lógico forte: a resposta do 1º Porquê deve ser a causa direta do Efeito.
A resposta do 2º Porquê deve ser a causa direta do 1º Porquê, e assim por diante até o 5º.

Retorne EXATAMENTE UM JSON contendo a chave "branch" com um array de 5 strings representando as respostas.
"""
    user_str = f"Problema Inicial (Y) a ser investigado: {efeito}"
    try:
        out = _chat_json(system, user_str)
        return out.get("branch", [])
    except Exception:
        return []

def suggest_5pq_branches(project_state: dict, efeito: str, context_path: list) -> list:
    """
    context_path é uma lista de strings. 
    Se len(context_path) == 0, pede as causas primárias do efeito (x1, x2, x3...)
    Se len(context_path) > 0, pede 3 a 5 explicações (hipóteses) lógicas para a causa anterior.
    """
    niv = len(context_path) + 1
    system = """
    Você é um Master Black Belt liderando um brainstorming profundo na ferramenta 5 Porquês.
    A ferramenta 5 Porquês não deve ser apenas uma linha única, mas sim uma árvore lógica de investigação.
    Sua missão é fornecer a ramificação para o nó atual, gerando de 3 a 5 hipóteses diferentes ("Por Quês?") que explicam o último estado.
    Retorne EXATAMENTE UM JSON no formato: {"hipoteses": ["causa A", "causa B", "causa C", "causa D"]}
    """
    
    proj_name = project_state.get("name", "Projeto LSS")
    proj_prob = project_state.get("charter", {}).get("problem", "")
    
    if not context_path:
        user_str = f"PROJETO: {proj_name} | CONTEXTO GERAL: {proj_prob}\nO problema central é: '{efeito}'. Gere 3 a 5 causas primárias (hipóteses raiz) para este problema. Essas serão as raízes da investigação."
    else:
        path_str = " -> ".join([efeito] + context_path)
        user_str = f"PROJETO: {proj_name} | CONTEXTO GERAL: {proj_prob}\nA engrenagem lógica exata que ocorreu foi: {path_str}.\n\nPara o último passo ('{context_path[-1]}'), responda 'POR QUE isso ocorreu?' fornecendo 3 a 5 hipóteses investigativas plausíveis de nível {niv}."
        
    try:
        out = _chat_json(system, user_str)
        return out.get("hipoteses", [])
    except Exception:
        return []

