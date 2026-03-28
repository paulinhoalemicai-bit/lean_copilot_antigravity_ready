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
        model=MODEL,
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
Ferramenta atual: {tool}
Modo: {mode}

Estado resumido do projeto:
{json.dumps(project_state, ensure_ascii=False, indent=2)}

Conteúdo atual do aluno:
{draft_text}

Tarefa:
1. Liste 2 a 5 coisas que estão boas em "ok"
2. Liste lacunas em "gaps"
3. Faça 1 a 3 perguntas prioritárias
4. Dê 1 próximo passo concreto em "next_action"
5. Defina "allow_generate"
6. Se mode="generate", inclua até 4 "candidates"

Formatação dos gaps:
- id: algo curto e claro, de preferência no padrão RUBRIC.<Ferramenta>.<Campo>
- severity: high, medium ou low
- reason: em português, começando por "Gap ..."
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
            model=MODEL,
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
    except Exception:
        return current_sipoc

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
