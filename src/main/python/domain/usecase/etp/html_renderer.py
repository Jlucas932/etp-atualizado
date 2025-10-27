from flask import render_template
from typing import Dict, Any

def render_etp_html(doc: Dict[str, Any]) -> str:
    """
    Renderiza o documento ETP usando templates/etp_document.html.j2.
    """
    return render_template('etp_document.html.j2', doc=doc)
