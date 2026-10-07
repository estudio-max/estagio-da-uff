"""RN04 (só a Divisão escreve), RF08 (histórico) e o fluxo de cadastro pelo admin."""

from datetime import timedelta

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group, User
from django.test import Client
from django.utils import timezone

from convenios.models import Concedente, Convenio, EtapaConvenio, Situacao

SENHA = "senha-de-teste-123"


def usuario(nome: str, *, divisao: bool) -> User:
    user = User.objects.create_user(username=nome, password=SENHA, is_staff=True)
    if divisao:
        user.groups.add(Group.objects.get(name="Divisão de Estágio"))
    return user


def logado(client: Client, user: User) -> Client:
    assert client.login(username=user.username, password=SENHA)
    return client


@pytest.mark.security
@pytest.mark.django_db
def test_staff_fora_da_divisao_nao_ve_convenios(client: Client) -> None:
    c = logado(client, usuario("outro", divisao=False))
    assert c.get("/admin/convenios/convenio/", secure=True).status_code == 403
    assert c.get("/admin/convenios/convenio/add/", secure=True).status_code == 403


@pytest.mark.security
@pytest.mark.django_db
def test_divisao_nao_exclui_convenio(client: Client) -> None:
    user = usuario("divisao", divisao=True)
    assert user.has_perm("convenios.change_convenio")
    assert not user.has_perm("convenios.delete_convenio")
    assert not user.has_perm("convenios.delete_concedente")


@pytest.mark.security
@pytest.mark.django_db
def test_anonimo_e_mandado_para_o_login(client: Client) -> None:
    resposta = client.get("/admin/convenios/convenio/", secure=True)
    assert resposta.status_code == 302
    assert "/admin/login/" in resposta["Location"]


def dados_convenio(concedente: Concedente, **extra: str) -> dict[str, str]:
    return {
        "concedente": str(concedente.pk),
        "numero": "PR-212/2026",
        "processo_sei": "23069.000001/2026-00",
        "situacao": Situacao.FINALIZADO,
        # Começa daqui a 30 dias: "a iniciar" seja qual for a data em que o teste roda.
        "inicio_vigencia": f"{timezone.localdate() + timedelta(days=30):%d/%m/%Y}",
        "fim_vigencia": f"{timezone.localdate() + timedelta(days=395):%d/%m/%Y}",
        "minuta": "padrao_uff",
        "origem": "concedente",
        "resolucao_cep": "",
        "resolucao_cep_url": "",
        "objeto": "",
        "observacoes_internas": "",
        "etapas-TOTAL_FORMS": "1",
        "etapas-INITIAL_FORMS": "0",
        "etapas-MIN_NUM_FORMS": "0",
        "etapas-MAX_NUM_FORMS": "1000",
        "etapas-0-etapa": "documentacao_recebida",
        "etapas-0-data": "01/09/2026",
        "etapas-0-observacao": "",
        **extra,
    }


@pytest.mark.e2e
@pytest.mark.django_db
def test_divisao_cadastra_concedente_e_convenio_com_historico(client: Client) -> None:
    user = usuario("divisao", divisao=True)
    c = logado(client, user)

    resposta = c.post(
        "/admin/convenios/concedente/add/",
        {
            "documento": "11.222.333/0001-81",
            "razao_social": "Empresa Fictícia Ltda",
            "nome_fantasia": "Fictícia",
            "tipo": "empresa_privada",
            "uf": "RJ",
            "cidade": "Niterói",
            "ramo_atividade": "",
            "email": "",
        },
        secure=True,
    )
    assert resposta.status_code == 302, resposta.context["adminform"].errors
    concedente = Concedente.objects.get()
    assert concedente.documento == "11222333000181"

    resposta = c.post("/admin/convenios/convenio/add/", dados_convenio(concedente), secure=True)
    assert resposta.status_code == 302, resposta.context["adminform"].errors
    convenio = Convenio.objects.get()
    assert EtapaConvenio.objects.get(convenio=convenio).etapa == "documentacao_recebida"

    # RF08: quem, quando e o quê
    registro = LogEntry.objects.get(content_type__model="convenio", object_id=str(convenio.pk))
    assert registro.user == user
    assert registro.action_time is not None
    assert "etapa" in registro.get_change_message().lower()

    # Busca pelo documento com máscara encontra a concedente
    lista = c.get("/admin/convenios/concedente/", {"q": "11.222.333/0001-81"}, secure=True)
    assert "Empresa Fictícia Ltda" in lista.content.decode()

    # Lista de convênios mostra a vigência derivada e aceita o filtro
    lista = c.get("/admin/convenios/convenio/", {"vigencia": "a_iniciar"}, secure=True)
    assert "PR-212/2026" in lista.content.decode()


@pytest.mark.e2e
@pytest.mark.django_db
def test_admin_mostra_erro_de_vigencia_acima_de_cinco_anos(client: Client) -> None:
    c = logado(client, usuario("divisao", divisao=True))
    concedente = Concedente.objects.create(
        documento="11222333000181", razao_social="X", tipo="outros", uf="RJ", cidade="Niterói"
    )
    resposta = c.post(
        "/admin/convenios/convenio/add/",
        dados_convenio(concedente, inicio_vigencia="08/09/2026", fim_vigencia="08/09/2031"),
        secure=True,
    )
    assert resposta.status_code == 200
    assert "vigência máxima é de 5 anos" in resposta.content.decode()
    assert not Convenio.objects.exists()
