import json
from .coach_extensions import _chat_json

def suggest_5_porques(project_state: dict, efeito: str) -> list:
    system = """
Você é um Coach Master Black Belt Lean Seis Sigma especialista na ferramenta 5 Porquês.
Sua missão é gerar um caminho ÚNICO, profunde, e linear de 5 Porquês para o Problema/Efeito inicial fornecido.
A técnica exige encadeamento lógico forte: a resposta do 1º Porquê deve ser a causa direta do Efeito.
A resposta do 2º Porquê deve ser a causa direta do 1º Porquê, e assim por diante até o 5º que deve revelar uma Causa Raiz Sistêmica/Processual.

Retorne EXATAMENTE UM JSON contendo a chave "branch" com um array de 5 strings representando as respostas (os porquês).
Exemplo:
{
  "branch": [
    "Porque o equipamento superaqueceu",
    "Porque o óleo lubrificante não estava no nível adequado",
    "Porque não houve reposição do óleo na manutenção",
    "Porque o checklist de manutenção preventiva não contempla a checagem de óleo",
    "Porque não existe um padrão definido pela engenharia de manutenção (Causa Raiz)"
  ]
}
"""
    user_str = f"Problema Inicial (Y) a ser investigado: {efeito}"
    try:
        out = _chat_json(system, user_str)
        return out.get("branch", [])
    except Exception:
        return []
