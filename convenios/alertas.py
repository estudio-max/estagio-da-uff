"""RF05: alertas de vencimento de convênio para a Divisão de Estágio.

Roda uma vez por dia (`manage.py enviar_alertas_vencimento`). Cada convênio recebe no máximo
um aviso por faixa de antecedência; se o job ficar dias sem rodar, só sai o aviso mais urgente.
Renovar o convênio (mudar o fim da vigência) reinicia os avisos.
"""

from dataclasses import dataclass
from datetime import date

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from convenios.models import AlertaVencimento, Convenio, Vigencia


def faixa_de_alerta(dias_restantes: int, antecedencias: list[int]) -> int | None:
    """Menor antecedência que já foi alcançada; None se ainda está longe do vencimento."""
    alcancadas = [a for a in antecedencias if dias_restantes <= a]
    return min(alcancadas) if alcancadas else None


@dataclass(frozen=True)
class Alerta:
    convenio: Convenio
    fim_vigencia: date
    antecedencia: int
    dias_restantes: int


def alertas_pendentes(hoje: date, antecedencias: list[int]) -> list[Alerta]:
    pendentes = []
    vigentes = Convenio.objects.com_vigencia(Vigencia.VIGENTE, hoje).select_related("concedente")
    for convenio in vigentes.order_by("fim_vigencia"):
        assert convenio.fim_vigencia  # vigente sempre tem fim  # noqa: S101
        dias = (convenio.fim_vigencia - hoje).days
        faixa = faixa_de_alerta(dias, antecedencias)
        if faixa is None:
            continue
        ja_enviado = AlertaVencimento.objects.filter(
            convenio=convenio, fim_vigencia=convenio.fim_vigencia, antecedencia_dias__lte=faixa
        ).exists()
        if not ja_enviado:
            pendentes.append(Alerta(convenio, convenio.fim_vigencia, faixa, dias))
    return pendentes


def montar_mensagem(alertas: list[Alerta]) -> str:
    base = settings.SITE_URL.rstrip("/")
    linhas = [
        "Convênios de estágio que entraram em período de aviso de vencimento:",
        "",
    ]
    for alerta in alertas:
        c = alerta.convenio
        url = base + reverse("admin:convenios_convenio_change", args=[c.pk])
        linhas += [
            f"- {c.numero} — {c.concedente.razao_social}",
            f"  Vence em {alerta.fim_vigencia:%d/%m/%Y} (faltam {alerta.dias_restantes} dias)",
            f"  {url}",
        ]
    linhas += ["", "Mensagem automática do Sistema de Estágios UFF."]
    return "\n".join(linhas)


def enviar_alertas(hoje: date | None = None) -> int:
    """Envia um único email com todos os alertas novos e os registra. Retorna quantos foram."""
    hoje = hoje or timezone.localdate()
    alertas = alertas_pendentes(hoje, settings.ALERTA_ANTECEDENCIAS_DIAS)
    if not alertas:
        return 0
    with transaction.atomic():
        # Registra antes de enviar, dentro da transação: se o email falhar, nada é marcado.
        AlertaVencimento.objects.bulk_create(
            AlertaVencimento(
                convenio=a.convenio,
                fim_vigencia=a.fim_vigencia,
                antecedencia_dias=a.antecedencia,
            )
            for a in alertas
        )
        send_mail(
            subject=f"[Estágios UFF] {len(alertas)} convênio(s) perto do vencimento",
            message=montar_mensagem(alertas),
            from_email=None,
            recipient_list=[settings.DIVISAO_EMAIL],
        )
    return len(alertas)
