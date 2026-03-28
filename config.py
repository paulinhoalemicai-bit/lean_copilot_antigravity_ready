from __future__ import annotations

TOOLS = [
    "Capa do Projeto",
    "VOC/VOB",
    "Project Charter",
    "Matriz RACI",
    "Saving Projetado",
    "SIPOC (por etapa)",
    "Ishikawa",
    "CauseEvidenceMatrix",
    "Solution",
    "Pilot",
    "ControlPlan",
    "Saving Realizado"
]

VOCVOB_COLUMNS = [
    "Voz (necessidade)",
    "Problema",
    "Requisito crítico",
    "Y (indicador)",
]

SIPOC_EDITOR_COLUMNS = [
    "S (Fornecedores)",
    "I (Entradas)",
    "P (Etapa do processo)",
    "O (Saídas)",
    "C (Clientes)",
]

DMAIC_PHASES = ["Define", "Measure", "Analyze", "Improve", "Control"]

TOOL_GUIDANCE = {
    "VOC/VOB": """
Ferramenta VOC/VOB.
Objetivo:
- Estruturar voz do cliente (VOC) e voz do negócio (VOB)
- Em cada linha: voz/necessidade, problema, requisito crítico e Y (indicador)
- Ajudar a alimentar Project Charter, especialmente problema e objetivo
""",
    "Project Charter": """
Ferramenta Project Charter.
Objetivo:
- Definir problema em 1 frase clara
- Definir objetivo SMART
- Delimitar escopo
- Explicitar CTQ e Y
- Identificar stakeholders
- Estimar cronograma DMAIC
Importante:
- Não entrar em causa raiz aqui
- Não misturar com Measure/Analyze
""",
    "SIPOC (por etapa)": """
Ferramenta SIPOC por etapa.
Objetivo:
- Começar pelo diagrama de serpentes (macro etapas)
- Depois montar SIPOC por etapa
- Cada etapa P tem seus próprios fornecedores, entradas, saídas e clientes
- Não usar SIPOC global genérico no preenchimento inicial
""",
    "Ishikawa": "Ferramenta de análise de causas potenciais.",
    "CauseEvidenceMatrix": "Matriz hipótese/evidência/teste.",
    "Solution": "Desenho de soluções e contramedidas.",
    "Pilot": "Planejamento do piloto.",
    "ControlPlan": "Plano de controle e sustentação.",
    "Saving Projetado": """
Ferramenta Financeira de Cálculo de Saving Projetado (Define).
Objetivo:
- Dimensionar monetariamente o ganho prospectado baseado no Business Case do Charter.
- Separar o racional de cálculo entre Hard Saving, Soft Saving e Cost Avoidance.
- O Coach deve atuar como Diretor Financeiro, instigando como precificar horas improdutivas, custo de funcionário/hora e mitigadores.
""",
    "Saving Realizado": """
Ferramenta Financeira de Cálculo de Saving Realizado (Control).
Objetivo:
- Apuração final contábil.
- Avaliar se a contabilidade bateu com a meta projetada no início.
- O Coach ajuda a formatar relatórios financeiros finais fáceis para diretoria.
"""
}
