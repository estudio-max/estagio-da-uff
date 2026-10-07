from datetime import timedelta
from typing import cast

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.urls import URLPattern, path
from django.utils import timezone

from convenios import painel
from convenios.documentos import normalizar
from convenios.models import (
    AlertaVencimento,
    Concedente,
    Convenio,
    ConvenioQuerySet,
    EtapaConvenio,
    Vigencia,
)

admin.site.site_header = "Sistema de Estágios UFF"
admin.site.site_title = "Estágios UFF"
admin.site.index_title = "Divisão de Estágio"


@admin.register(Concedente)
class ConcedenteAdmin(admin.ModelAdmin[Concedente]):
    list_display = ["razao_social", "nome_fantasia", "documento_formatado", "tipo", "uf", "cidade"]
    list_filter = ["tipo", "uf"]
    search_fields = ["razao_social", "nome_fantasia", "documento"]

    @admin.display(description="CPF/CNPJ", ordering="documento")
    def documento_formatado(self, obj: Concedente) -> str:
        return obj.documento_formatado

    def get_search_results(
        self, request: HttpRequest, queryset: QuerySet[Concedente], search_term: str
    ) -> tuple[QuerySet[Concedente], bool]:
        # Busca por documento funciona com ou sem máscara.
        resultado, duplicados = super().get_search_results(request, queryset, search_term)
        documento = normalizar(search_term)
        if documento and documento != search_term:
            resultado |= queryset.filter(documento__contains=documento)
        return resultado, duplicados


class VigenciaFilter(admin.SimpleListFilter):
    title = "vigência"
    parameter_name = "vigencia"

    def lookups(self, request: HttpRequest, _model_admin: object) -> list[tuple[str, str]]:
        return list(Vigencia.choices)

    def queryset(self, request: HttpRequest, queryset: QuerySet[Convenio]) -> QuerySet[Convenio]:
        if valor := self.value():
            return cast(ConvenioQuerySet, queryset).com_vigencia(valor)
        return queryset


class VencimentoFilter(admin.SimpleListFilter):
    """RF05 no painel: convênios vigentes que vencem nos próximos N dias."""

    title = "vence em"
    parameter_name = "vence_em"

    def lookups(self, request: HttpRequest, _model_admin: object) -> list[tuple[str, str]]:
        return [(str(d), f"até {d} dias") for d in (30, 90, 180, 365)]

    def queryset(self, request: HttpRequest, queryset: QuerySet[Convenio]) -> QuerySet[Convenio]:
        if (valor := self.value()) and valor.isdigit():
            hoje = timezone.localdate()
            limite = hoje + timedelta(days=int(valor))
            return (
                cast(ConvenioQuerySet, queryset)
                .com_vigencia(Vigencia.VIGENTE, hoje)
                .filter(fim_vigencia__lte=limite)
            )
        return queryset


class AlertaInline(admin.TabularInline[AlertaVencimento, Convenio]):
    model = AlertaVencimento
    extra = 0
    can_delete = False
    fields = ("antecedencia_dias", "fim_vigencia", "enviado_em")
    readonly_fields = fields
    verbose_name_plural = "alertas de vencimento enviados"

    def has_add_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False


class EtapaInline(admin.TabularInline[EtapaConvenio, Convenio]):
    model = EtapaConvenio
    extra = 1


@admin.register(Convenio)
class ConvenioAdmin(admin.ModelAdmin[Convenio]):
    list_display = [
        "numero",
        "concedente",
        "inicio_vigencia",
        "fim_vigencia",
        "situacao",
        "vigencia_atual",
        "dias_para_vencer",
    ]
    list_filter = [
        VigenciaFilter,
        VencimentoFilter,
        "situacao",
        "concedente__tipo",
        "minuta",
        "origem",
    ]
    search_fields = [
        "numero",
        "processo_sei",
        "concedente__razao_social",
        "concedente__nome_fantasia",
        "concedente__documento",
    ]
    autocomplete_fields = ["concedente"]
    formfield_overrides = {models.URLField: {"assume_scheme": "https"}}
    date_hierarchy = "fim_vigencia"
    inlines = [EtapaInline, AlertaInline]
    readonly_fields = ["criado_em", "atualizado_em"]
    fieldsets = [
        (None, {"fields": ["concedente", "numero", "processo_sei", "situacao"]}),
        ("Vigência", {"fields": ["inicio_vigencia", "fim_vigencia"]}),
        (
            "Detalhes",
            {"fields": ["minuta", "origem", "resolucao_cep", "resolucao_cep_url", "objeto"]},
        ),
        (
            "Uso interno",
            {"fields": ["observacoes_internas", "criado_em", "atualizado_em"]},
        ),
    ]

    def get_urls(self) -> list[URLPattern]:
        rota = path(
            "painel/",
            self.admin_site.admin_view(self.painel_view),
            name="convenios_convenio_painel",
        )
        return [rota, *super().get_urls()]

    def painel_view(self, request: HttpRequest) -> HttpResponse:
        """RF06/MS05. Restrito a quem vê convênios (D4: visibilidade pública pendente)."""
        if not self.has_view_permission(request):
            raise PermissionDenied
        contexto = {
            **self.admin_site.each_context(request),
            "title": "Painel de convênios",
            "opts": self.model._meta,
            "indicadores": painel.calcular(timezone.localdate()),
            "periodo_tramitacao": painel.PERIODO_TRAMITACAO_DIAS,
        }
        return TemplateResponse(request, "admin/convenios/convenio/painel.html", contexto)

    @admin.display(description="vigência")
    def vigencia_atual(self, obj: Convenio) -> str:
        return obj.vigencia().label

    @admin.display(description="dias para vencer", ordering="fim_vigencia")
    def dias_para_vencer(self, obj: Convenio) -> int | None:
        if obj.vigencia() != Vigencia.VIGENTE or obj.fim_vigencia is None:
            return None
        return (obj.fim_vigencia - timezone.localdate()).days
