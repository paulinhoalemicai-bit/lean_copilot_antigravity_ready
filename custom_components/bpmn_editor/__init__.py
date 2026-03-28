import os
import streamlit.components.v1 as components

# Pegar o caminho absoluto desta pasta e mirar no /frontend
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_FRONTEND_DIR = os.path.join(_CURRENT_DIR, "frontend")

# Declara o componente. O Streamlit automaticamente levanta um servidor estático
# para servir os arquivos HTML/JS presentes nessa pasta
_st_bpmn_editor = components.declare_component(
    "bpmn_editor",
    path=_FRONTEND_DIR
)

def st_bpmn(xml: str = "", height: int = 600, key=None):
    """
    Renderiza o modelador visual do BPMN.io.
    Se xml for passado, o diagrama será carregado na tela em estado editável.
    Retorna a string XML mais recente confirmada pelo botão "Extrar Diagrama no Frontend"
    """
    return _st_bpmn_editor(xml=xml, height=height, key=key)
