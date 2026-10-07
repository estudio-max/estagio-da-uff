"""RF06: indicadores estratégicos de convênios. MS05: tempo de tramitação medido."""

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import mean, median

from django.db.models import Count, Min

from convenios.models import Convenio, Situacao, TipoConcedente, Vigencia

JANELAS_VENCIMENTO = (30, 90, 180)
PERIODO_TRAMITACAO_DIAS = 365
QUANTOS_PARADOS = 10


@dataclass(frozen=True)
class Parado:
    convenio: Convenio
    dias: int


@dataclass(frozen=True)
class Indicadores:
    por_vigencia: dict[str, int]
    vencendo: dict[int, int]
    por_tipo: list[tuple[str, int]]
    tramitacao_media: float | None
    tramitacao_mediana: float | None
    tramitacao_amostra: int
    parados: list[Parado]


def _inicio_da_tramitacao(convenio: Convenio) -> date:
    """Primeira etapa registrada; sem etapas, a data do cadastro."""
    primeira = getattr(convenio, "primeira_etapa", None)
    return primeira or convenio.criado_em.date()


def calcular(hoje: date) -> Indicadores:
    convenios = Convenio.objects.all()
    vigentes = convenios.com_vigencia(Vigencia.VIGENTE, hoje)

    por_vigencia = {v.label: convenios.com_vigencia(v, hoje).count() for v in Vigencia}
    vencendo = {
        dias: vigentes.filter(fim_vigencia__lte=hoje + timedelta(days=dias)).count()
        for dias in JANELAS_VENCIMENTO
    }
    contagem_tipo = dict(
        vigentes.values("concedente__tipo")
        .annotate(n=Count("id"))
        .values_list("concedente__tipo", "n")
    )
    por_tipo = [(rotulo, contagem_tipo.get(valor, 0)) for valor, rotulo in TipoConcedente.choices]

    com_inicio = convenios.annotate(primeira_etapa=Min("etapas__data"))
    # ponytail: média calculada em Python; ~centenas de convênios por ano. Agregar no banco
    # se o volume crescer muito.
    duracoes = [
        (c.finalizado_em - _inicio_da_tramitacao(c)).days
        for c in com_inicio.filter(
            situacao=Situacao.FINALIZADO,
            finalizado_em__gte=hoje - timedelta(days=PERIODO_TRAMITACAO_DIAS),
        )
        if c.finalizado_em
    ]
    parados = sorted(
        (
            Parado(c, (hoje - _inicio_da_tramitacao(c)).days)
            for c in com_inicio.filter(situacao=Situacao.EM_TRAMITACAO).select_related("concedente")
        ),
        key=lambda p: p.dias,
        reverse=True,
    )[:QUANTOS_PARADOS]

    return Indicadores(
        por_vigencia=por_vigencia,
        vencendo=vencendo,
        por_tipo=por_tipo,
        tramitacao_media=mean(duracoes) if duracoes else None,
        tramitacao_mediana=median(duracoes) if duracoes else None,
        tramitacao_amostra=len(duracoes),
        parados=parados,
    )
