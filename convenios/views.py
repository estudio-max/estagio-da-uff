"""Página pública de convênios (RF03, RF04, RN01).

Convênios finalizados vigentes ou a iniciar (estes com selo "a partir de", D18).
Os campos expostos ficam nos templates; observações internas, email, etapas, minuta,
origem e Resolução CEP nunca saem daqui.
"""

from typing import Any

from django.db.models import Q
from django.views.generic import DetailView, ListView

from convenios.documentos import normalizar
from convenios.models import UFS, Convenio, ConvenioQuerySet, TipoConcedente, Vigencia


def convenios_publicos() -> ConvenioQuerySet:
    convenios = Convenio.objects.com_vigencia(Vigencia.VIGENTE) | Convenio.objects.com_vigencia(
        Vigencia.A_INICIAR
    )
    return convenios.select_related("concedente")


class ListaPublica(ListView[Convenio]):
    template_name = "convenios/lista.html"
    context_object_name = "convenios"
    paginate_by = 50

    def get_queryset(self) -> ConvenioQuerySet:
        convenios = convenios_publicos().order_by("concedente__razao_social", "numero")
        busca = self.request.GET.get("q", "").strip()
        if busca:
            filtro = (
                Q(concedente__razao_social__icontains=busca)
                | Q(concedente__nome_fantasia__icontains=busca)
                | Q(numero__icontains=busca)
                | Q(processo_sei__icontains=busca)
            )
            documento = normalizar(busca)
            # Busca por documento só em CNPJ: CPF de pessoa física não é público.
            if len(documento) >= 8:
                filtro |= Q(concedente__documento__contains=documento) & ~Q(
                    concedente__documento__regex=r"^\d{11}$"
                )
            convenios = convenios.filter(filtro)
        if tipo := self.request.GET.get("tipo"):
            convenios = convenios.filter(concedente__tipo=tipo)
        if uf := self.request.GET.get("uf"):
            convenios = convenios.filter(concedente__uf=uf)
        return convenios

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        contexto = super().get_context_data(**kwargs)
        contexto |= {
            "tipos": TipoConcedente.choices,
            "ufs": [uf for uf, _ in UFS],
            "busca": self.request.GET.get("q", ""),
            "tipo_atual": self.request.GET.get("tipo", ""),
            "uf_atual": self.request.GET.get("uf", ""),
            "total_vigentes": Convenio.objects.com_vigencia(Vigencia.VIGENTE).count(),
            "total_a_iniciar": Convenio.objects.com_vigencia(Vigencia.A_INICIAR).count(),
        }
        # Mantém filtros ao trocar de página.
        parametros = self.request.GET.copy()
        parametros.pop("page", None)
        contexto["parametros"] = parametros.urlencode()
        return contexto


class DetalhePublico(DetailView[Convenio]):
    template_name = "convenios/detalhe.html"
    context_object_name = "convenio"

    def get_queryset(self) -> ConvenioQuerySet:
        # Convênio não público dá 404, sem revelar que existe.
        return convenios_publicos()
