from __future__ import annotations

TOOLS = [
    "Capa do Projeto",
    "D - VOC/VOB",
    "D - SIPOC (por etapa)",
    "D - Matriz RACI",
    "D - Saving Projetado",
    "D - Project Charter",
    "D - Capabilidade (Baseline)",
    "M - Fluxograma",
    "M - Matriz de Indicadores",
    "M - Repositório de Medições",
    "M - Causa & Efeito - Esforço Impacto",
    "M - Plano de Coleta de Dados",
    "M - Quick Wins",
    "M - Ishikawa",
    "A - 5 Porquês",
    "A - Plano de Validação de Causas",
    "I - Plano de Soluções",
    "I - Plano de Ação",
    "I - Capabilidade (Melhoria)",
    "C - Saving Realizado",
    "C - Plano de Controle"
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
    "D - VOC/VOB": """
Ferramenta VOC/VOB.
Objetivo:
- Estruturar voz do cliente (VOC) e voz do negócio (VOB)
- Em cada linha: voz/necessidade, problema, requisito crítico e Y (indicador)
- Ajudar a alimentar Project Charter, especialmente problema e objetivo
""",
    "D - Project Charter": """
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
    "D - SIPOC (por etapa)": """
Ferramenta SIPOC por etapa.
Objetivo:
- Começar pelo diagrama de serpentes (macro etapas)
- Depois montar SIPOC por etapa
- Cada etapa P tem seus próprios fornecedores, entradas, saídas e clientes
- Não usar SIPOC global genérico no preenchimento inicial
""",
    "M - Ishikawa": """
Ferramenta de análise de causas potenciais (Espinha de Peixe).
Objetivo:
- Permitir ramificações de causas (causa da causa).
- Garantir que o Doutor Lean não misture causas primárias com causas raízes, decompondo todas de forma lógica.
- O Coach deve observar causas repetidas ou misturadas (primárias vs raízes). Sem se preocupar em julgar se a causa pertence a grupo A ou B.
""",
    "A - 5 Porquês": """
Ferramenta dos 5 Porquês.
Objetivo:
- Aprofundar as causas primárias até chegar às raízes infinitamente por ramificações.
- Garantir que o Doutor Lean avalie a qualidade da decomposição sem misturar sintomas com raízes.
""",
    "A - Plano de Validação de Causas": """
Ferramenta Plano de Validação de Causas.
Objetivo:
- Validar hipóteses formuladas no Ishikawa / 5 PQs usando dados (estatística) ou dedução analítica comprovada.
- O Coach deve atuar sugerindo testes estatísticos e barrando validação caso os dados fornecidos pelo aluno sejam inconclusivos ou ruins.
""",
    "I - Plano de Soluções": """
Ferramenta Plano de Soluções.
Objetivo:
- Pensar em até 5 soluções por causa raiz.
- Explicar através da matriz B.A.S.I.C.O (Benefícios, Abrangência, Satisfação, Investimento, Cliente, Operacionalidade) os prós e contras textualmente, sem atribuir notas.
""",
    "I - Plano de Ação": """
Ferramenta Plano de Ação (5W2H).
Objetivo:
- Detalhar as ações das soluções escolhidas (o que, como, quem, etc).
- Coach deve auxiliar apenas no "O que" e "Como".
""",
    "M - Quick Wins": """
Ferramenta Quick Wins (Ganhos Rápidos).
Objetivo:
- Mapear e executar ações de baixa complexidade e alto impacto imediato que não exigem validações complexas.
- Segue a estrutura 5W2H para execução ágil.
""",
    "D - Saving Projetado": """
Ferramenta Financeira de Cálculo de Saving Projetado (Define).
Objetivo:
- Dimensionar monetariamente o ganho prospectado baseado no Business Case do Charter.
- Separar o racional de cálculo entre Hard Saving, Soft Saving e Cost Avoidance.
- O Coach deve atuar como Diretor Financeiro, instigando como precificar horas improdutivas, custo de funcionário/hora e mitigadores.
""",
    "C - Saving Realizado": """
Ferramenta Financeira de Cálculo de Saving Realizado (Control).
Objetivo:
- Apuração final contábil.
- Avaliar se a contabilidade bateu com a meta projetada no início.
- O Coach ajuda a formatar relatórios financeiros finais fáceis para diretoria.
""",
    "M - Matriz de Indicadores": """
Ferramenta Matriz de Indicadores baseada no SIPOC.
Objetivo:
- Identificar indicadores de processo focados nas etapas (P) mapeadas no nível Macro ou SIPOC.
- Fornecer métricas em diferentes dimensões (Quantidade, WIP, Tempo, %, Qualidade, Finanças) formadas a partir do Problema de negócio definido.
""",
    "M - Repositório de Medições": """
Ferramenta Repositório de Medições (Laboratório de Dados).
Objetivo:
- Permitir que o aluno cole ou faça upload de tabelas de dados.
- O Coach deve atuar como Cientista de Dados (gerando gráficos e estatísticas).
- Regra rígida: Instruir sempre que "a interpretação humana e conhecimento do processo é fundamental".
- Se os dados excederem 2000 linhas, orientar uso de IA externa.
""",
    "M - Causa & Efeito - Esforço Impacto": """
Ferramenta Causa & Efeito (Esforço × Impacto).
Objetivo:
- Listar as principais causas (X's) que impactam o problema central do projeto.
- Estimar o Impacto de cada causa no problema (escala 0-100): quanto aquela causa contribui para o problema.
- Estimar o Esforço necessário para endereçá-la (escala 0-100): quanto custa em tempo/recurso/dificuldade resolver aquela causa.
- Priorizar as causas de maior impacto e menor esforço (Alta Prioridade) para ação imediata baseado na Teoria das Restrições.
""",
    "M - Plano de Coleta de Dados": """
Ferramenta Plano de Coleta de Dados.
Objetivo:
- Planejar detalhadamente como cada indicador ou causa prioritária será medido.
- Definir Definição Operacional, Fonte, Amostra, Responsável, Frequência (Quando) e Método (Como).
- Identificar como os dados serão utilizados para análise e como serão apresentados (gráficos).
""",
    "C - Plano de Controle": """
Ferramenta Plano de Controle.
Objetivo:
- Garantir a sustentabilidade das melhorias a longo prazo (Fase Control)
- Definir métodos de medição, responsáveis, metas e limites
- Especificar ações preventivas e corretivas em caso de desvio dos indicadores e causas tratadas
""",
    "D - Capabilidade (Baseline)": """
Ferramenta Capabilidade de Processo (Medição do Status Quo do Y).
Objetivo:
- Analisar a performance de dados discretos ou contínuos sobre as especificações.
- Em dados discretos: Calcular Oportunidades, DPMO e Nível Sigma baseado nos defeitos atuais.
- Em dados contínuos: Gerar gráfico de distribuição e calcular o Z.Score a partir de amostragens reais.
- O Coach atua como Mestre Estatístico (Estatístico Black Belt), usando o Problema Central da fase de Definição (Charter) para instigar se o aluno possui as coletas necessárias e calcular a distribuição por ele caso solicitado (uso de CSV/XLSX).
""",
    "I - Capabilidade (Melhoria)": """
Ferramenta Capabilidade de Processo (Após a Melhoria).
Objetivo:
- Validar estatisticamente as melhorias através do recálculo do Nível Sigma (Z.B/Z.L).
- Os padrões seguem idênticos, porém visa confirmar a quebra de patamar na fase de Improve para ser levado ao Control.
"""
}
