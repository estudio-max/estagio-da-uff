from django import template

from convenios.documentos import formatar

register = template.Library()


@register.filter
def documento_publico(documento: str | None) -> str:
    """CNPJ formatado para a página pública; CPF não é exibido (RN08, LGPD)."""
    if not documento or len(documento) == 11:
        return ""
    return f"CNPJ {formatar(documento)}"
