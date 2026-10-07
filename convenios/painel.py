"""RF06: indicadores estratégicos de convênios. MS05: tempo de tramitação medido."""

from dataclasses import dataclass, replace
from datetime import date, timedelta
from statistics import mean, median

from django.db.models import Count, Max, Min, Q
from django.db.models.functions import ExtractYear, TruncMonth

from convenios.models import (
    Concedente,
    Convenio,
    ConvenioQuerySet,
    Situacao,
    TipoConcedente,
    Vigencia,
)

JANELAS_VENCIMENTO = (30, 90, 180)
PERIODO_TRAMITACAO_DIAS = 365
QUANTOS_PARADOS = 10
QUANTAS_UFS = 6
QUANTOS_NAO_RENOVADOS = 10
ANO_INICIAL = 2015  # primeiro ano com dados no estagio.uff.br
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


@dataclass(frozen=True)
class Barra:
    """Um valor de gráfico de uma série. `pct` é a altura/largura relativa ao maior valor."""

    rotulo: str
    valor: int
    pct: float
    destaque: bool = True
    eixo: str = ""  # rótulo curto no eixo; vazio = usa o rótulo

    @property
    def rotulo_eixo(self) -> str:
        return self.eixo or self.rotulo


def _barras(pares: list[tuple[str, int]], destacar: int | None = None) -> list[Barra]:
    """`destacar`: só os N primeiros em destaque (o resto em cinza); None destaca todos."""
    maior = max((v for _, v in pares), default=0) or 1
    return [
        Barra(r, v, round(v / maior * 100, 1), destacar is None or i < destacar)
        for i, (r, v) in enumerate(pares)
    ]


@dataclass(frozen=True)
class NaoRenovado:
    concedente: Concedente
    ultimo_fim: date


@dataclass(frozen=True)
class Parado:
    convenio: Convenio
    dias: int


@dataclass(frozen=True)
class Indicadores:
    por_vigencia: dict[str, int]
    vencendo: dict[int, int]
    por_tipo: list[Barra]
    novos_por_ano: list[Barra]
    vencimentos_por_mes: list[Barra]
    por_uf: list[Barra]
    nao_renovados: list[NaoRenovado]
    total_nao_renovados: int
    taxa_renovacao: float | None
    vigentes_sem_documento: int

    @property
    def vencem_30(self) -> int:
        return self.vencendo[30]

    @property
    def vencem_90(self) -> int:
        return self.vencendo[90]

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
    por_tipo = _barras(
        sorted(
            ((rotulo, contagem_tipo.get(valor, 0)) for valor, rotulo in TipoConcedente.choices),
            key=lambda par: -par[1],
        )
    )

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

    nao_renovados, total_nao_renovados, taxa = _renovacao(hoje)
    return Indicadores(
        por_vigencia=por_vigencia,
        vencendo=vencendo,
        por_tipo=por_tipo,
        novos_por_ano=_novos_por_ano(hoje),
        vencimentos_por_mes=_vencimentos_por_mes(vigentes, hoje),
        por_uf=_por_uf(vigentes),
        nao_renovados=nao_renovados,
        total_nao_renovados=total_nao_renovados,
        taxa_renovacao=taxa,
        vigentes_sem_documento=vigentes.filter(concedente__documento__isnull=True).count(),
        tramitacao_media=mean(duracoes) if duracoes else None,
        tramitacao_mediana=median(duracoes) if duracoes else None,
        tramitacao_amostra=len(duracoes),
        parados=parados,
    )


def _novos_por_ano(hoje: date) -> list[Barra]:
    contagem = dict(
        Convenio.objects.filter(situacao=Situacao.FINALIZADO, inicio_vigencia__isnull=False)
        .annotate(ano=ExtractYear("inicio_vigencia"))
        .values("ano")
        .annotate(n=Count("id"))
        .values_list("ano", "n")
    )
    return _barras([(str(a), contagem.get(a, 0)) for a in range(ANO_INICIAL, hoje.year + 1)])


def _vencimentos_por_mes(vigentes: ConvenioQuerySet, hoje: date) -> list[Barra]:
    """Próximos 12 meses a partir do mês atual; os 3 primeiros em destaque (fila urgente)."""
    meses = [
        date(hoje.year + (hoje.month - 1 + i) // 12, (hoje.month - 1 + i) % 12 + 1, 1)
        for i in range(12)
    ]
    contagem = {
        m.date() if hasattr(m, "date") else m: n
        for m, n in vigentes.filter(fim_vigencia__lt=_mes_seguinte(meses[-1]))
        .annotate(mes=TruncMonth("fim_vigencia"))
        .values("mes")
        .annotate(n=Count("id"))
        .values_list("mes", "n")
    }
    barras = _barras(
        [(f"{MESES[m.month - 1]}/{m:%y}", contagem.get(m, 0)) for m in meses], destacar=3
    )
    # Eixo só com o mês; o ano aparece no primeiro mês e em janeiro.
    return [
        replace(b, eixo=b.rotulo if i == 0 or m.month == 1 else MESES[m.month - 1])
        for i, (b, m) in enumerate(zip(barras, meses, strict=True))
    ]


def _mes_seguinte(mes: date) -> date:
    return date(mes.year + mes.month // 12, mes.month % 12 + 1, 1)


def _por_uf(vigentes: ConvenioQuerySet) -> list[Barra]:
    contagem = sorted(
        vigentes.values("concedente__uf")
        .annotate(n=Count("id"))
        .values_list("concedente__uf", "n"),
        key=lambda par: -par[1],
    )
    validas = [(uf, n) for uf, n in contagem if uf]
    principais = validas[:QUANTAS_UFS]
    outras = sum(n for _, n in contagem) - sum(n for _, n in principais)
    return _barras(principais + ([("Outras", outras)] if outras else []))


def _renovacao(hoje: date) -> tuple[list[NaoRenovado], int, float | None]:
    """Concedentes cujo convênio venceu nos últimos 12 meses e que não têm outro ativo."""
    finalizado = Q(convenios__situacao=Situacao.FINALIZADO)
    venceram = Concedente.objects.filter(
        finalizado,
        convenios__fim_vigencia__lt=hoje,
        convenios__fim_vigencia__gte=hoje - timedelta(days=365),
    ).distinct()
    ativos = Concedente.objects.filter(finalizado, convenios__fim_vigencia__gte=hoje)
    sem_renovar = (
        venceram.exclude(pk__in=ativos)
        .annotate(ultimo_fim=Max("convenios__fim_vigencia"))
        .order_by("-ultimo_fim")
    )
    total_venceram = venceram.count()
    total = sem_renovar.count()
    taxa = (total_venceram - total) / total_venceram if total_venceram else None
    lista = [NaoRenovado(c, c.ultimo_fim) for c in sem_renovar[:QUANTOS_NAO_RENOVADOS]]
    return lista, total, taxa
