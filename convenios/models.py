from datetime import date
from typing import Any

from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from convenios import documentos

VIGENCIA_MAXIMA_ANOS = 5  # RN07 (premissa D15)

UFS = [
    (uf, uf)
    for uf in [
        "AC",
        "AL",
        "AM",
        "AP",
        "BA",
        "CE",
        "DF",
        "ES",
        "GO",
        "MA",
        "MG",
        "MS",
        "MT",
        "PA",
        "PB",
        "PE",
        "PI",
        "PR",
        "RJ",
        "RN",
        "RO",
        "RR",
        "RS",
        "SC",
        "SE",
        "SP",
        "TO",
    ]
]


class _DocumentoFormField(forms.CharField):
    def to_python(self, value: Any) -> str:
        # Tira a máscara antes do limite de 14 caracteres ser verificado.
        return documentos.normalizar(super().to_python(value) or "")


class DocumentoField(models.CharField):  # type: ignore[type-arg]
    def formfield(self, **kwargs: Any) -> Any:
        return super().formfield(**{"form_class": _DocumentoFormField, **kwargs})


class TipoConcedente(models.TextChoices):
    """RN05: lista oficial do formulário da PROGRAD."""

    ENSINO_PRIVADA = "ensino_privada", "Instituição de Ensino Privada"
    EMPRESA_PRIVADA = "empresa_privada", "Empresa Privada"
    ONG_OSCIP = "ong_oscip", "ONGs e OSCIPs"
    ORGAO_PUBLICO = "orgao_publico", "Órgãos dos Governos Federal, Estadual e Municipal"
    PROFISSIONAL_LIBERAL = "profissional_liberal", "Profissional Liberal"
    AGENTE_INTEGRACAO = "agente_integracao", "Agente de Integração"
    ENSINO_PUBLICA = "ensino_publica", "Instituições de Ensino Públicas"
    MICROEMPRESA = "microempresa", "Microempresas"
    OUTROS = "outros", "Outros"


class Concedente(models.Model):
    documento = DocumentoField(
        "CPF/CNPJ",
        max_length=14,
        unique=True,
        validators=[documentos.validar_documento],
        help_text="Com ou sem pontuação. Pessoa física (ex.: profissional liberal) usa CPF.",
    )
    razao_social = models.CharField("razão social / nome", max_length=255)
    nome_fantasia = models.CharField(max_length=255, blank=True)
    tipo = models.CharField(max_length=30, choices=TipoConcedente.choices)
    uf = models.CharField("UF", max_length=2, choices=UFS)
    cidade = models.CharField(max_length=100)
    ramo_atividade = models.CharField("ramo de atividade", max_length=255, blank=True)
    email = models.EmailField(blank=True)

    class Meta:
        ordering = ["razao_social"]

    def __str__(self) -> str:
        return self.nome_fantasia or self.razao_social

    def clean_fields(self, exclude: object = None) -> None:
        # Normaliza antes de validar: validador e unique comparam só os caracteres do documento.
        self.documento = documentos.normalizar(self.documento)
        super().clean_fields(exclude=exclude)  # type: ignore[arg-type]

    @property
    def documento_formatado(self) -> str:
        return documentos.formatar(self.documento)


class Situacao(models.TextChoices):
    EM_TRAMITACAO = "em_tramitacao", "Em tramitação"
    FINALIZADO = "finalizado", "Finalizado"
    CANCELADO = "cancelado", "Cancelado"


class Vigencia(models.TextChoices):
    """Derivada de situação + datas (RN02); nunca armazenada."""

    EM_TRAMITACAO = "em_tramitacao", "Em tramitação"
    CANCELADO = "cancelado", "Cancelado"
    A_INICIAR = "a_iniciar", "A iniciar"
    VIGENTE = "vigente", "Vigente"
    VENCIDO = "vencido", "Vencido"


class ConvenioQuerySet(models.QuerySet["Convenio"]):
    def com_vigencia(self, vigencia: str, hoje: date | None = None) -> "ConvenioQuerySet":
        hoje = hoje or timezone.localdate()
        finalizado = Q(situacao=Situacao.FINALIZADO)
        filtros = {
            Vigencia.EM_TRAMITACAO: Q(situacao=Situacao.EM_TRAMITACAO),
            Vigencia.CANCELADO: Q(situacao=Situacao.CANCELADO),
            Vigencia.A_INICIAR: finalizado & Q(inicio_vigencia__gt=hoje),
            Vigencia.VIGENTE: finalizado & Q(inicio_vigencia__lte=hoje, fim_vigencia__gte=hoje),
            Vigencia.VENCIDO: finalizado & Q(fim_vigencia__lt=hoje),
        }
        return self.filter(filtros[Vigencia(vigencia)])


def somar_anos(data: date, anos: int) -> date:
    try:
        return data.replace(year=data.year + anos)
    except ValueError:  # 29/02 caindo em ano não bissexto
        return data.replace(year=data.year + anos, month=3, day=1)


class Convenio(models.Model):
    class Minuta(models.TextChoices):
        PADRAO_UFF = "padrao_uff", "Padrão UFF"
        EXTERNA = "externa", "Externa (proposta pela concedente)"

    class Origem(models.TextChoices):
        CONCEDENTE = "concedente", "Concedente procurou a UFF"
        UFF = "uff", "UFF procurou a concedente"

    concedente = models.ForeignKey(Concedente, on_delete=models.PROTECT, related_name="convenios")
    numero = models.CharField(
        "nº do convênio", max_length=30, blank=True, help_text="Ex.: PR-212/2026"
    )
    processo_sei = models.CharField(
        "nº do processo SEI", max_length=25, blank=True, help_text="Ex.: 23069.179497/2026-46"
    )
    resolucao_cep = models.CharField("Resolução CEP", max_length=100, blank=True)
    resolucao_cep_url = models.URLField("link da Resolução CEP", blank=True)
    objeto = models.TextField(blank=True)
    minuta = models.CharField(max_length=20, choices=Minuta.choices, default=Minuta.PADRAO_UFF)
    origem = models.CharField(max_length=20, choices=Origem.choices, default=Origem.CONCEDENTE)
    inicio_vigencia = models.DateField("início da vigência", null=True, blank=True)
    fim_vigencia = models.DateField("fim da vigência", null=True, blank=True)
    situacao = models.CharField(
        "situação", max_length=20, choices=Situacao.choices, default=Situacao.EM_TRAMITACAO
    )
    observacoes_internas = models.TextField("observações internas", blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    finalizado_em = models.DateField(
        "finalizado em",
        null=True,
        blank=True,
        editable=False,
        help_text="Preenchido ao marcar como finalizado; base do tempo de tramitação (MS05).",
    )

    objects = ConvenioQuerySet.as_manager()

    class Meta:
        verbose_name = "convênio"
        ordering = ["-inicio_vigencia", "-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["numero"],
                condition=~Q(numero=""),
                name="convenio_numero_unico",
                violation_error_message="Já existe convênio com este número.",
            ),
            models.CheckConstraint(
                condition=Q(fim_vigencia__gt=models.F("inicio_vigencia"))
                | Q(inicio_vigencia__isnull=True)
                | Q(fim_vigencia__isnull=True),
                name="convenio_fim_depois_do_inicio",
                violation_error_message="O fim da vigência deve ser depois do início.",
            ),
            models.CheckConstraint(
                condition=~Q(situacao="finalizado")
                | (Q(inicio_vigencia__isnull=False, fim_vigencia__isnull=False) & ~Q(numero="")),
                name="convenio_finalizado_completo",
                violation_error_message="Finalizado exige número e datas de vigência.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.numero or 'sem número'} — {self.concedente}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.situacao == Situacao.FINALIZADO and self.finalizado_em is None:
            self.finalizado_em = timezone.localdate()
        elif self.situacao != Situacao.FINALIZADO:
            self.finalizado_em = None
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if (
            self.inicio_vigencia
            and self.fim_vigencia
            and self.fim_vigencia >= somar_anos(self.inicio_vigencia, VIGENCIA_MAXIMA_ANOS)
        ):
            raise ValidationError(
                {"fim_vigencia": f"A vigência máxima é de {VIGENCIA_MAXIMA_ANOS} anos."}
            )

    def vigencia(self, hoje: date | None = None) -> Vigencia:
        if self.situacao != Situacao.FINALIZADO:
            return Vigencia(self.situacao)
        hoje = hoje or timezone.localdate()
        if self.inicio_vigencia and hoje < self.inicio_vigencia:
            return Vigencia.A_INICIAR
        if self.fim_vigencia and hoje > self.fim_vigencia:
            return Vigencia.VENCIDO
        return Vigencia.VIGENTE


class AlertaVencimento(models.Model):
    """Aviso enviado (RF05). O fim da vigência entra na chave: renovar reinicia os avisos."""

    convenio = models.ForeignKey(Convenio, on_delete=models.CASCADE, related_name="alertas")
    fim_vigencia = models.DateField()
    antecedencia_dias = models.PositiveIntegerField()
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "alerta de vencimento"
        verbose_name_plural = "alertas de vencimento"
        constraints = [
            models.UniqueConstraint(
                fields=["convenio", "fim_vigencia", "antecedencia_dias"], name="alerta_unico"
            )
        ]

    def __str__(self) -> str:
        return f"{self.convenio} — aviso de {self.antecedencia_dias} dias"


class EtapaConvenio(models.Model):
    """RF02: andamento interno. Quem registrou fica no histórico do admin (RF08)."""

    class Etapa(models.TextChoices):
        DOCUMENTACAO_RECEBIDA = "documentacao_recebida", "Documentação recebida"
        ANALISE = "analise", "Análise da documentação"
        TERMO_PREPARADO = "termo_preparado", "Termo de convênio preparado"
        ASSINATURA_CONCEDENTE = "assinatura_concedente", "Assinado pela concedente"
        ASSINATURA_PRO_REITOR = "assinatura_pro_reitor", "Assinado pelo pró-reitor"
        RATIFICACAO = "ratificacao", "Ratificação"
        EXTRATO_BS = "extrato_bs", "Extrato publicado no Boletim de Serviço"
        OUTRA = "outra", "Outra (descrever na observação)"

    convenio = models.ForeignKey(Convenio, on_delete=models.CASCADE, related_name="etapas")
    etapa = models.CharField(max_length=30, choices=Etapa.choices)
    data = models.DateField(default=timezone.localdate)
    observacao = models.CharField("observação", max_length=255, blank=True)

    class Meta:
        verbose_name = "etapa"
        ordering = ["data", "id"]

    def __str__(self) -> str:
        return f"{self.get_etapa_display()} em {self.data:%d/%m/%Y}"
