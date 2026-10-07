from django import template

from convenios.documentos import formatar

register = template.Library()


@register.filter
def cnpj_publico(documento: str | None) -> str:
    """CNPJ formatado; CPF (pessoa física) nunca é exibido na página pública (LGPD)."""
    if not documento or len(documento) == 11:
        return ""
    return formatar(documento)
