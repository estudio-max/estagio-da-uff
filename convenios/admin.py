from typing import cast

from django.contrib import admin
from django.db import models
from django.db.models import QuerySet
from django.http import HttpRequest

from convenios.documentos import normalizar
from convenios.models import Concedente, Convenio, ConvenioQuerySet, EtapaConvenio, Vigencia

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
    ]
    list_filter = [VigenciaFilter, "situacao", "concedente__tipo", "minuta", "origem"]
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
    inlines = [EtapaInline]
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

    @admin.display(description="vigência")
    def vigencia_atual(self, obj: Convenio) -> str:
        return obj.vigencia().label
