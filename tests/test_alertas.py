"""RF05: alertas de vencimento de convênio."""

from datetime import date, timedelta
from typing import Any

import pytest
from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.management import CommandError, call_command
from django.test import Client

from convenios.alertas import enviar_alertas, faixa_de_alerta
from convenios.models import AlertaVencimento, Concedente, Convenio, Situacao

HOJE = date(2026, 10, 6)
ANTECEDENCIAS = [365, 180, 90, 30]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("dias", "esperado"),
    [
        (400, None),
        (366, None),
        (365, 365),
        (200, 365),
        (180, 180),
        (91, 180),
        (90, 90),
        (31, 90),
        (30, 30),
        (0, 30),
    ],
)
def test_faixa_de_alerta(dias: int, esperado: int | None) -> None:
    assert faixa_de_alerta(dias, ANTECEDENCIAS) == esperado


@pytest.fixture(autouse=True)
def configuracao(settings: Any) -> None:
    settings.DIVISAO_EMAIL = "divisao@exemplo.uff.br"
    settings.ALERTA_ANTECEDENCIAS_DIAS = ANTECEDENCIAS
    settings.SITE_URL = "https://estagios.exemplo.uff.br"


@pytest.fixture
def concedente(db: None) -> Concedente:
    return Concedente.objects.create(
        documento="11222333000181",
        razao_social="Empresa Fictícia",
        tipo="outros",
        uf="RJ",
        cidade="Niterói",
    )


def convenio(dono: Concedente, numero: str, vence_em_dias: int, **campos: object) -> Convenio:
    fim = HOJE + timedelta(days=vence_em_dias)
    padrao: dict[str, object] = {
        "situacao": Situacao.FINALIZADO,
        "inicio_vigencia": fim - timedelta(days=1000),
        "fim_vigencia": fim,
    }
    return Convenio.objects.create(concedente=dono, numero=numero, **(padrao | campos))


@pytest.mark.integration
def test_envia_um_email_so_com_os_convenios_na_faixa(concedente: Concedente) -> None:
    convenio(concedente, "PR-LONGE/2026", 500)
    convenio(concedente, "PR-90D/2026", 85)
    convenio(concedente, "PR-30D/2026", 10)
    convenio(concedente, "PR-TRAMITANDO/2026", 10, situacao=Situacao.EM_TRAMITACAO)
    convenio(concedente, "PR-VENCIDO/2026", -5)

    assert enviar_alertas(HOJE) == 2
    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.to == ["divisao@exemplo.uff.br"]
    assert "2 convênio(s)" in email.subject
    assert "PR-90D/2026" in email.body and "faltam 85 dias" in email.body
    assert "PR-30D/2026" in email.body and "faltam 10 dias" in email.body
    for fora in ["LONGE", "TRAMITANDO", "VENCIDO"]:
        assert fora not in email.body
    assert "https://estagios.exemplo.uff.br/admin/convenios/convenio/" in email.body


@pytest.mark.integration
def test_nao_repete_aviso_da_mesma_faixa(concedente: Concedente) -> None:
    convenio(concedente, "PR-1/2026", 85)
    assert enviar_alertas(HOJE) == 1
    assert enviar_alertas(HOJE + timedelta(days=1)) == 0
    assert len(mail.outbox) == 1


@pytest.mark.integration
def test_avisa_de_novo_ao_entrar_na_proxima_faixa(concedente: Concedente) -> None:
    convenio(concedente, "PR-1/2026", 95)
    assert enviar_alertas(HOJE) == 1  # faixa de 180
    assert enviar_alertas(HOJE + timedelta(days=5)) == 1  # faixa de 90
    assert list(
        AlertaVencimento.objects.order_by("antecedencia_dias").values_list(
            "antecedencia_dias", flat=True
        )
    ) == [90, 180]


@pytest.mark.integration
def test_job_parado_varios_dias_manda_so_o_aviso_mais_urgente(concedente: Concedente) -> None:
    convenio(concedente, "PR-1/2026", 20)  # já passou de 365, 180, 90 e 30
    assert enviar_alertas(HOJE) == 1
    assert AlertaVencimento.objects.get().antecedencia_dias == 30
    assert enviar_alertas(HOJE + timedelta(days=1)) == 0


@pytest.mark.integration
def test_aviso_mais_urgente_ja_enviado_cobre_faixas_maiores(concedente: Concedente) -> None:
    c = convenio(concedente, "PR-1/2026", 20)
    AlertaVencimento.objects.create(
        convenio=c, fim_vigencia=HOJE + timedelta(days=20), antecedencia_dias=30
    )
    assert enviar_alertas(HOJE) == 0


@pytest.mark.integration
def test_renovar_o_convenio_reinicia_os_avisos(concedente: Concedente) -> None:
    c = convenio(concedente, "PR-1/2026", 20)
    assert enviar_alertas(HOJE) == 1
    # Aditivo de prazo: novo fim daqui a 80 dias (dentro de 5 anos do início).
    c.fim_vigencia = HOJE + timedelta(days=80)
    c.save()
    assert enviar_alertas(HOJE) == 1
    assert AlertaVencimento.objects.count() == 2


@pytest.mark.integration
def test_sem_alertas_nao_envia_email(concedente: Concedente) -> None:
    convenio(concedente, "PR-1/2026", 500)
    assert enviar_alertas(HOJE) == 0
    assert mail.outbox == []


@pytest.mark.integration
def test_falha_no_envio_nao_marca_alerta_como_enviado(
    concedente: Concedente, monkeypatch: pytest.MonkeyPatch
) -> None:
    convenio(concedente, "PR-1/2026", 10)

    def falha(*_args: object, **_kwargs: object) -> None:
        raise ConnectionError("servidor de email fora do ar")

    monkeypatch.setattr("convenios.alertas.send_mail", falha)
    with pytest.raises(ConnectionError):
        enviar_alertas(HOJE)
    assert not AlertaVencimento.objects.exists()


@pytest.mark.integration
def test_comando_exige_email_da_divisao(db: None, settings: Any) -> None:
    settings.DIVISAO_EMAIL = ""
    with pytest.raises(CommandError, match="DIVISAO_EMAIL"):
        call_command("enviar_alertas_vencimento")


@pytest.mark.smoke
def test_comando_roda(db: None, capsys: pytest.CaptureFixture[str]) -> None:
    call_command("enviar_alertas_vencimento")
    assert "0 alerta(s) enviado(s)." in capsys.readouterr().out


@pytest.mark.e2e
@pytest.mark.django_db
def test_painel_filtra_por_vencimento_e_mostra_alertas(client: Client) -> None:
    from django.utils import timezone

    hoje = timezone.localdate()
    dono = Concedente.objects.create(
        documento="11222333000181",
        razao_social="Empresa Fictícia",
        tipo="outros",
        uf="RJ",
        cidade="Niterói",
    )
    perto = Convenio.objects.create(
        concedente=dono,
        numero="PR-PERTO/2026",
        situacao=Situacao.FINALIZADO,
        inicio_vigencia=hoje - timedelta(days=700),
        fim_vigencia=hoje + timedelta(days=20),
    )
    Convenio.objects.create(
        concedente=dono,
        numero="PR-LONGE/2026",
        situacao=Situacao.FINALIZADO,
        inicio_vigencia=hoje - timedelta(days=10),
        fim_vigencia=hoje + timedelta(days=700),
    )
    AlertaVencimento.objects.create(
        convenio=perto, fim_vigencia=hoje + timedelta(days=20), antecedencia_dias=30
    )
    user = User.objects.create_user("divisao", password="senha-teste-123", is_staff=True)
    user.groups.add(Group.objects.get(name="Divisão de Estágio"))
    client.force_login(user)

    html = client.get("/admin/convenios/convenio/", {"vence_em": "30"}, secure=True)
    assert "PR-PERTO/2026" in html.content.decode()
    assert "PR-LONGE/2026" not in html.content.decode()
    # Valor inválido na URL é ignorado, não derruba a página.
    assert client.get("/admin/convenios/convenio/", {"vence_em": "x"}, secure=True).status_code
    detalhe = client.get(f"/admin/convenios/convenio/{perto.pk}/change/", secure=True)
    assert "alertas de vencimento enviados" in detalhe.content.decode().lower()
