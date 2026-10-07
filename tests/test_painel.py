"""RF06 (painéis) e MS05 (tempo de tramitação medido)."""

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.test import Client
from django.utils import timezone

from convenios import painel
from convenios.models import Concedente, Convenio, EtapaConvenio, Situacao, TipoConcedente

HOJE = date(2026, 10, 6)


def concedente(documento: str, tipo: str = TipoConcedente.EMPRESA_PRIVADA) -> Concedente:
    return Concedente.objects.create(
        documento=documento,
        razao_social=f"Fictícia {documento}",
        tipo=tipo,
        uf="RJ",
        cidade="Niterói",
    )


def finalizado(dono: Concedente, numero: str, vence_em: int, **campos: object) -> Convenio:
    fim = HOJE + timedelta(days=vence_em)
    return Convenio.objects.create(
        concedente=dono,
        numero=numero,
        situacao=Situacao.FINALIZADO,
        inicio_vigencia=fim - timedelta(days=1000),
        fim_vigencia=fim,
        **campos,
    )


@pytest.mark.integration
@pytest.mark.django_db
def test_finalizado_em_e_preenchido_e_limpo_automaticamente() -> None:
    c = Convenio.objects.create(concedente=concedente("11222333000181"))
    assert c.finalizado_em is None
    c.numero, c.situacao = "PR-1/2026", Situacao.FINALIZADO
    c.inicio_vigencia, c.fim_vigencia = HOJE, HOJE + timedelta(days=100)
    c.save()
    assert c.finalizado_em == timezone.localdate()
    data_original = c.finalizado_em
    c.save()  # salvar de novo não muda a data
    assert c.finalizado_em == data_original
    c.situacao = Situacao.CANCELADO
    c.save()
    assert c.finalizado_em is None


@pytest.mark.integration
@pytest.mark.django_db
def test_contagens_por_situacao_vencimento_e_tipo() -> None:
    empresa = concedente("11222333000181")
    ong = concedente("12ABC34501DE35", TipoConcedente.ONG_OSCIP)
    finalizado(empresa, "PR-20D/2026", 20)
    finalizado(empresa, "PR-60D/2026", 60)
    finalizado(ong, "PR-150D/2026", 150)
    finalizado(ong, "PR-500D/2026", 500)
    finalizado(empresa, "PR-VENCIDO/2026", -1)
    Convenio.objects.create(concedente=empresa)  # em tramitação
    Convenio.objects.create(concedente=empresa, situacao=Situacao.CANCELADO)

    r = painel.calcular(HOJE)
    assert r.por_vigencia == {
        "Em tramitação": 1,
        "Cancelado": 1,
        "A iniciar": 0,
        "Vigente": 4,
        "Vencido": 1,
    }
    assert r.vencendo == {30: 1, 90: 2, 180: 3}
    tipos = dict(r.por_tipo)
    assert tipos["Empresa Privada"] == 2
    assert tipos["ONGs e OSCIPs"] == 2
    assert tipos["Microempresas"] == 0  # todos os tipos aparecem, mesmo zerados


@pytest.mark.integration
@pytest.mark.django_db
def test_tempo_de_tramitacao_usa_primeira_etapa_e_janela_de_um_ano() -> None:
    dono = concedente("11222333000181")
    rapido = finalizado(dono, "PR-1/2026", 300)
    EtapaConvenio.objects.create(convenio=rapido, etapa="analise", data=HOJE - timedelta(days=5))
    EtapaConvenio.objects.create(
        convenio=rapido, etapa="documentacao_recebida", data=HOJE - timedelta(days=20)
    )
    lento = finalizado(dono, "PR-2/2026", 300)
    EtapaConvenio.objects.create(
        convenio=lento, etapa="documentacao_recebida", data=HOJE - timedelta(days=80)
    )
    antigo = finalizado(dono, "PR-3/2026", 300)
    # finalizado_em é automático; aqui forçamos datas para o cenário do teste.
    Convenio.objects.filter(pk__in=[rapido.pk, lento.pk]).update(finalizado_em=HOJE)
    Convenio.objects.filter(pk=antigo.pk).update(finalizado_em=HOJE - timedelta(days=400))

    r = painel.calcular(HOJE)
    assert r.tramitacao_amostra == 2  # o antigo fica fora da janela de 365 dias
    assert r.tramitacao_media == 50  # (20 + 80) / 2
    assert r.tramitacao_mediana == 50


@pytest.mark.integration
@pytest.mark.django_db
def test_sem_finalizados_nao_ha_media() -> None:
    r = painel.calcular(HOJE)
    assert r.tramitacao_media is None
    assert r.tramitacao_amostra == 0


@pytest.mark.integration
@pytest.mark.django_db
def test_parados_ordenados_do_mais_antigo_e_limitados() -> None:
    dono = concedente("11222333000181")
    for dias in range(12):
        c = Convenio.objects.create(concedente=dono)
        EtapaConvenio.objects.create(
            convenio=c, etapa="documentacao_recebida", data=HOJE - timedelta(days=dias * 10)
        )
    r = painel.calcular(HOJE)
    assert [p.dias for p in r.parados] == [110, 100, 90, 80, 70, 60, 50, 40, 30, 20]


def usuario(client: Client, *, divisao: bool) -> Client:
    user = User.objects.create_user("u", password="senha-teste-123", is_staff=True)
    if divisao:
        user.groups.add(Group.objects.get(name="Divisão de Estágio"))
    client.force_login(user)
    return client


URL = "/admin/convenios/convenio/painel/"


@pytest.mark.security
@pytest.mark.django_db
def test_painel_exige_login(client: Client) -> None:
    resposta = client.get(URL, secure=True)
    assert resposta.status_code == 302
    assert "/admin/login/" in resposta["Location"]


@pytest.mark.security
@pytest.mark.django_db
def test_painel_bloqueado_para_staff_fora_da_divisao(client: Client) -> None:
    assert usuario(client, divisao=False).get(URL, secure=True).status_code == 403


@pytest.mark.e2e
@pytest.mark.django_db
def test_divisao_abre_o_painel_pela_lista_de_convenios(client: Client) -> None:
    c = usuario(client, divisao=True)
    lista = c.get("/admin/convenios/convenio/", secure=True).content.decode()
    assert URL in lista

    hoje = timezone.localdate()
    Convenio.objects.create(
        concedente=concedente("11222333000181"),
        numero="PR-PERTO/2026",
        situacao=Situacao.FINALIZADO,
        inicio_vigencia=hoje - timedelta(days=10),
        fim_vigencia=hoje + timedelta(days=15),
    )
    html = c.get(URL, secure=True).content.decode()
    for trecho in [
        "Painel de convênios",
        "Convênios por situação",
        "?vence_em=30",
        "Tempo de tramitação",
        "Vigentes por tipo de concedente",
        "Em tramitação há mais tempo",
    ]:
        assert trecho in html
