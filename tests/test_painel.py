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
    tipos = {b.rotulo: b.valor for b in r.por_tipo}
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
        "Convênios vigentes",
        "Não renovaram",
        "Vencimentos nos próximos 12 meses",
        "Convênios por ano de início",
        "Vigentes por UF",
        "Ver valores em tabela",
        "Concedentes que não renovaram",
        "Convênios por situação",
        "?vence_em=90",
        "Tempo de tramitação",
        "Vigentes por tipo de concedente",
        "Em tramitação há mais tempo",
    ]:
        assert trecho in html


# --- Gráficos de insights ---


@pytest.mark.unit
def test_barras_calculam_proporcao_e_destaque() -> None:
    barras = painel._barras([("a", 50), ("b", 100), ("c", 0)], destacar=1)
    assert [(b.pct, b.destaque) for b in barras] == [(50.0, True), (100.0, False), (0.0, False)]
    assert painel._barras([("vazio", 0)])[0].pct == 0.0  # sem divisão por zero


@pytest.mark.integration
@pytest.mark.django_db
def test_convenios_por_ano_cobrem_todos_os_anos_ate_hoje() -> None:
    dono = concedente("11222333000181")
    Convenio.objects.create(
        concedente=dono,
        numero="PR-A/2018",
        situacao=Situacao.FINALIZADO,
        inicio_vigencia=date(2018, 3, 1),
        fim_vigencia=date(2020, 3, 1),
    )
    Convenio.objects.create(concedente=dono)  # em tramitação: não conta
    anos = {b.rotulo: b.valor for b in painel.calcular(HOJE).novos_por_ano}
    assert (min(anos), max(anos)) == ("2015", "2026")
    assert anos["2018"] == 1
    assert sum(anos.values()) == 1


@pytest.mark.integration
@pytest.mark.django_db
def test_vencimentos_por_mes_a_partir_do_mes_atual() -> None:
    dono = concedente("11222333000181")
    finalizado(dono, "PR-OUT/2026", 10)  # 16/10/2026
    finalizado(dono, "PR-JAN/2027", 100)  # 14/01/2027
    finalizado(dono, "PR-LONGE/2028", 400)  # fora dos 12 meses
    meses = painel.calcular(HOJE).vencimentos_por_mes
    assert len(meses) == 12
    assert [(b.rotulo, b.valor) for b in meses][:4] == [
        ("out/26", 1),
        ("nov/26", 0),
        ("dez/26", 0),
        ("jan/27", 1),
    ]
    assert [b.destaque for b in meses[:4]] == [True, True, True, False]
    assert [b.rotulo_eixo for b in meses[:5]] == ["out/26", "nov", "dez", "jan/27", "fev"]
    assert sum(b.valor for b in meses) == 2


@pytest.mark.integration
@pytest.mark.django_db
def test_vigentes_por_uf_agrupa_o_resto_em_outras() -> None:
    for i, uf in enumerate(["RJ", "RJ", "SP", "MG", "SC", "RS", "PR", "BA", "", "ES"]):
        dono = Concedente.objects.create(
            documento=None, razao_social=f"Fictícia {i}", tipo="outros", uf=uf, cidade="X"
        )
        finalizado(dono, f"PR-{i}/2026", 300)
    por_uf = {b.rotulo: b.valor for b in painel.calcular(HOJE).por_uf}
    assert por_uf["RJ"] == 2
    assert len(por_uf) == 7  # 6 UFs + Outras
    assert por_uf["Outras"] == 3  # 2 UFs que sobraram + 1 sem UF
    assert sum(por_uf.values()) == 10


@pytest.mark.integration
@pytest.mark.django_db
def test_renovacao_conta_quem_venceu_e_nao_tem_outro_ativo() -> None:
    renovou = concedente("11222333000181")
    finalizado(renovou, "PR-VELHO/2021", -30)
    finalizado(renovou, "PR-NOVO/2026", 900)
    sumiu = concedente("12ABC34501DE35")
    finalizado(sumiu, "PR-SUMIU/2021", -10)
    antigo = concedente("52998224725")
    finalizado(antigo, "PR-ANTIGO/2020", -500)  # venceu há mais de 1 ano: fora da conta

    r = painel.calcular(HOJE)
    assert r.total_nao_renovados == 1
    assert [n.concedente for n in r.nao_renovados] == [sumiu]
    assert r.nao_renovados[0].ultimo_fim == HOJE - timedelta(days=10)
    assert r.taxa_renovacao == 0.5


@pytest.mark.integration
@pytest.mark.django_db
def test_vigentes_sem_documento() -> None:
    sem = Concedente.objects.create(
        documento=None, razao_social="Sem CNPJ", tipo="outros", uf="RJ", cidade="X"
    )
    finalizado(sem, "PR-1/2026", 100)
    finalizado(concedente("11222333000181"), "PR-2/2026", 100)
    r = painel.calcular(HOJE)
    assert r.vigentes_sem_documento == 1
    assert (r.vencem_30, r.vencem_90) == (0, 0)
