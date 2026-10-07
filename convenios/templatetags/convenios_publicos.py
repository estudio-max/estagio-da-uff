from django import template

from convenios.documentos import formatar

register = template.Library()


@register.filter
def cnpj_publico(documento: str) -> str:
    """CNPJ formatado; CPF (pessoa física) nunca é exibido na página pública (LGPD)."""
    return "" if len(documento) == 11 else formatar(documento)
