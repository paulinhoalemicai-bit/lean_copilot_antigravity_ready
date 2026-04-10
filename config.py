from __future__ import annotations

TOOLS = [
    "Capa do Projeto",
    "VOC/VOB",
    "Project Charter",
    "Matriz RACI",
    "Saving Projetado",
    "Plano de Coleta de Dados",
    "SIPOC (por etapa)",
    "Fluxograma",
    "Matriz de Indicadores",
    "Causa & Efeito - Esforço Impacto",
    "Ishikawa",
    "5 Porquês",
    "Plano de Validação de Causas",
    "Plano de Ação",
    "Quick Wins",
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
    "Ishikawa": """
Ferramenta de análise de causas potenciais (Espinha de Peixe).
Objetivo:
- Permitir ramificações de causas (causa da causa).
- Garantir que o Doutor Lean não misture causas primárias com causas raízes, decompondo todas de forma lógica.
- O Coach deve observar causas repetidas ou misturadas (primárias vs raízes). Sem se preocupar em julgar se a causa pertence a grupo A ou B.
""",
    "5 Porquês": """
Ferramenta dos 5 Porquês.
Objetivo:
- Aprofundar as causas primárias até chegar às raízes infinitamente por ramificações.
- Garantir que o Doutor Lean avalie a qualidade da decomposição sem misturar sintomas com raízes.
""",
    "Plano de Validação de Causas": """
Ferramenta Plano de Validação de Causas.
Objetivo:
- Validar hipóteses formuladas no Ishikawa / 5 PQs usando dados (estatística) ou dedução analítica comprovada.
- O Coach deve atuar sugerindo testes estatísticos e barrando validação caso os dados fornecidos pelo aluno sejam inconclusivos ou ruins.
""",
    "Plano de Soluções": """
Ferramenta Plano de Soluções.
Objetivo:
- Pensar em até 5 soluções por causa raiz.
- Explicar através da matriz B.A.S.I.C.O (Benefícios, Abrangência, Satisfação, Investimento, Cliente, Operacionalidade) os prós e contras textualmente, sem atribuir notas.
""",
    "Plano de Ação": """
Ferramenta Plano de Ação (5W2H).
Objetivo:
- Detalhar as ações das soluções escolhidas (o que, como, quem, etc).
- Coach deve auxiliar apenas no "O que" e "Como".
""",
    "Quick Wins": """
Ferramenta Quick Wins (Ganhos Rápidos).
Objetivo:
- Mapear e executar ações de baixa complexidade e alto impacto imediato que não exigem validações complexas.
- Segue a estrutura 5W2H para execução ágil.
""",
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
""",
    "Matriz de Indicadores": """
Ferramenta Matriz de Indicadores baseada no SIPOC.
Objetivo:
- Identificar indicadores de processo focados nas etapas (P) mapeadas no nível Macro ou SIPOC.
- Fornecer métricas em diferentes dimensões (Quantidade, WIP, Tempo, %, Qualidade, Finanças) formadas a partir do Problema de negócio definido.
""",
    "Causa & Efeito - Esforço Impacto": """
Ferramenta Causa & Efeito (Esforço × Impacto).
Objetivo:
- Listar as principais causas (X's) que impactam o problema central do projeto.
- Estimar o Impacto de cada causa no problema (escala 0-100): quanto aquela causa contribui para o problema.
- Estimar o Esforço necessário para endereçá-la (escala 0-100): quanto custa em tempo/recurso/dificuldade resolver aquela causa.
- Priorizar as causas de maior impacto e menor esforço (Alta Prioridade) para ação imediata baseado na Teoria das Restrições.
""",
    "Plano de Coleta de Dados": """
Ferramenta Plano de Coleta de Dados.
Objetivo:
- Planejar detalhadamente como cada indicador ou causa prioritária será medido.
- Definir Definição Operacional, Fonte, Amostra, Responsável, Frequência (Quando) e Método (Como).
- Identificar como os dados serão utilizados para análise e como serão apresentados (gráficos).
"""
}
