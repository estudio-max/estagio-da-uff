"""RF03/RF04/RN01: página pública mostra só convênios vigentes e só campos públicos."""

from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from convenios.models import Concedente, Convenio, Situacao, TipoConcedente

HOJE = timezone.localdate()


def concedente(documento: str = "11222333000181", **campos: str) -> Concedente:
    padrao = {
        "razao_social": "Empresa Fictícia Ltda",
        "tipo": TipoConcedente.EMPRESA_PRIVADA,
        "uf": "RJ",
        "cidade": "Niterói",
    }
    return Concedente.objects.create(documento=documento, **(padrao | campos))


def convenio(dono: Concedente, numero: str = "PR-1/2026", **campos: object) -> Convenio:
    padrao: dict[str, object] = {
        "situacao": Situacao.FINALIZADO,
        "inicio_vigencia": HOJE - timedelta(days=30),
        "fim_vigencia": HOJE + timedelta(days=365),
        "processo_sei": "23069.000001/2026-00",
    }
    return Convenio.objects.create(concedente=dono, numero=numero, **(padrao | campos))


def pagina(client: Client, url: str = "/", **params: str) -> str:
    resposta = client.get(url, params, secure=True)
    assert resposta.status_code == 200
    return resposta.content.decode()


# --- RN01: só vigentes e a iniciar ---


@pytest.mark.integration
@pytest.mark.django_db
def test_lista_so_convenios_vigentes(client: Client) -> None:
    dono = concedente()
    convenio(dono, "PR-VIGENTE/2026")
    convenio(dono, "PR-TRAMITANDO/2026", situacao=Situacao.EM_TRAMITACAO)
    convenio(dono, "PR-CANCELADO/2026", situacao=Situacao.CANCELADO)
    convenio(
        dono,
        "PR-VENCIDO/2020",
        inicio_vigencia=HOJE - timedelta(days=900),
        fim_vigencia=HOJE - timedelta(days=1),
    )
    convenio(dono, "PR-FUTURO/2026", inicio_vigencia=HOJE + timedelta(days=1))

    html = pagina(client)
    assert "PR-VIGENTE/2026" in html
    assert "PR-FUTURO/2026" in html  # D18: a iniciar aparece, com selo
    for oculto in ["TRAMITANDO", "CANCELADO", "VENCIDO"]:
        assert oculto not in html
    assert "1 convênio vigente · 1 a iniciar" in html


@pytest.mark.integration
@pytest.mark.django_db
def test_convenio_entra_na_pagina_ao_ser_finalizado(client: Client) -> None:
    c = convenio(concedente(), situacao=Situacao.EM_TRAMITACAO)
    assert "PR-1/2026" not in pagina(client)
    c.situacao = Situacao.FINALIZADO
    c.save()
    assert "PR-1/2026" in pagina(client)


@pytest.mark.security
@pytest.mark.django_db
@pytest.mark.parametrize("situacao", [Situacao.EM_TRAMITACAO, Situacao.CANCELADO])
def test_detalhe_de_convenio_nao_vigente_da_404(client: Client, situacao: str) -> None:
    c = convenio(concedente(), situacao=situacao)
    assert client.get(f"/convenios/{c.pk}/", secure=True).status_code == 404


# --- RF03: campos internos nunca aparecem ---


@pytest.mark.security
@pytest.mark.django_db
def test_campos_internos_nao_vazam_na_lista_nem_no_detalhe(client: Client) -> None:
    dono = concedente(email="contato-interno@ficticia.example")
    c = convenio(
        dono,
        observacoes_internas="NOTA-INTERNA-SECRETA",
        resolucao_cep="RESOLUCAO-INTERNA-123",
    )
    c.etapas.create(etapa="analise", observacao="ETAPA-INTERNA")
    for html in [pagina(client), pagina(client, f"/convenios/{c.pk}/")]:
        for segredo in ["NOTA-INTERNA", "contato-interno", "RESOLUCAO-INTERNA", "ETAPA-INTERNA"]:
            assert segredo not in html


@pytest.mark.security
@pytest.mark.django_db
def test_cpf_de_pessoa_fisica_nunca_e_exibido_nem_buscavel(client: Client) -> None:
    pessoa = concedente(
        "52998224725",
        razao_social="Profissional Fictício",
        tipo=TipoConcedente.PROFISSIONAL_LIBERAL,
    )
    c = convenio(pessoa)
    for html in [pagina(client), pagina(client, f"/convenios/{c.pk}/")]:
        assert "Profissional Fictício" in html
        assert "529.982.247-25" not in html
        assert "52998224725" not in html
    # Quem sabe o CPF não consegue confirmar, pela busca, que a pessoa tem convênio.
    assert "Profissional Fictício" not in pagina(client, q="529.982.247-25")


@pytest.mark.security
@pytest.mark.django_db
def test_conteudo_cadastrado_e_escapado_no_html(client: Client) -> None:
    c = convenio(concedente(razao_social="<script>alert(1)</script>"))
    for html in [pagina(client), pagina(client, f"/convenios/{c.pk}/")]:
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html


@pytest.mark.security
@pytest.mark.django_db
def test_pagina_publica_nao_exige_login(client: Client) -> None:
    assert client.get("/", secure=True).status_code == 200


# --- RF04: busca e filtros ---


@pytest.mark.e2e
@pytest.mark.django_db
def test_busca_por_nome_cnpj_numero_e_filtros(client: Client) -> None:
    convenio(concedente(razao_social="Alfa Tecnologia", nome_fantasia="AlfaTec"), "PR-10/2026")
    convenio(
        concedente(
            "12ABC34501DE35",
            razao_social="Beta Saúde",
            tipo=TipoConcedente.ONG_OSCIP,
            uf="SP",
            cidade="São Paulo",
        ),
        "PR-20/2026",
    )

    def encontra(**params: str) -> set[str]:
        html = pagina(client, **params)
        return {nome for nome in ["Alfa Tecnologia", "Beta Saúde"] if nome in html}

    assert encontra() == {"Alfa Tecnologia", "Beta Saúde"}
    assert encontra(q="alfatec") == {"Alfa Tecnologia"}
    assert encontra(q="PR-20") == {"Beta Saúde"}
    assert encontra(q="11.222.333/0001-81") == {"Alfa Tecnologia"}
    assert encontra(q="12.abc.345/01de-35") == {"Beta Saúde"}
    assert encontra(tipo=TipoConcedente.ONG_OSCIP) == {"Beta Saúde"}
    assert encontra(uf="RJ") == {"Alfa Tecnologia"}
    assert encontra(q="inexistente") == set()
    assert "Nenhum convênio vigente encontrado" in pagina(client, q="inexistente")


@pytest.mark.e2e
@pytest.mark.django_db
def test_detalhe_mostra_os_campos_publicos(client: Client) -> None:
    c = convenio(
        concedente(ramo_atividade="Serviços de assistência social"),
        "PR-212/2026",
        objeto="A CONCEDENTE oferecerá estágios.",
    )
    html = pagina(client, f"/convenios/{c.pk}/")
    for esperado in [
        "PR-212/2026",
        "23069.000001/2026-00",
        "11.222.333/0001-81",
        "Empresa Privada",
        "Serviços de assistência social",
        "Niterói/RJ",
        "A CONCEDENTE oferecerá estágios.",
        f"{c.inicio_vigencia:%Y}",
    ]:
        assert esperado in html


@pytest.mark.e2e
@pytest.mark.django_db
def test_paginacao_mantem_os_filtros(client: Client) -> None:
    dono = concedente()
    for i in range(51):
        convenio(dono, f"PR-{i:03d}/2026")
    html = pagina(client, uf="RJ")
    assert "Página 1 de 2" in html
    assert "uf=RJ&amp;page=2" in html
    assert "Página 2 de 2" in pagina(client, uf="RJ", page="2")


@pytest.mark.e2e
@pytest.mark.django_db
def test_convenio_a_iniciar_tem_selo_com_a_data_de_inicio(client: Client) -> None:
    inicio = HOJE + timedelta(days=20)
    c = convenio(concedente(), inicio_vigencia=inicio)
    selo = f"A partir de {inicio:%d/%m/%Y}"
    assert selo in pagina(client)
    detalhe = pagina(client, f"/convenios/{c.pk}/")
    assert selo in detalhe
    assert ">Vigente<" not in detalhe


@pytest.mark.e2e
@pytest.mark.django_db
def test_convenio_vigente_nao_tem_selo_de_futuro(client: Client) -> None:
    c = convenio(concedente())
    assert "A partir de" not in pagina(client)
    assert ">Vigente<" in pagina(client, f"/convenios/{c.pk}/")
