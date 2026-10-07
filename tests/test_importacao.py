"""RF07: importação do XML do Drupal. Dados fictícios no mesmo formato do export real."""

from datetime import date
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import Client

from convenios.importacao import _data, importar, ler_xml
from convenios.models import Concedente, Convenio, Situacao, TipoConcedente

EMAIL_HTML = '&lt;a href="mailto:contato@ficticia.example"&gt;contato@ficticia.example&lt;/a&gt;'
RESOLUCAO_HTML = '&lt;a href="https://exemplo.uff.br/res.pdf"&gt;CEPEX 3463/2024&lt;/a&gt;'


def no(nid: int, **campos: str) -> str:
    padrao = {
        "Titulo": f"Empresa Fictícia {nid}",
        "Nr-CONVENIO": f"PR-{nid}/2026",
        "N-MERO-DO-PROCESSO": "23069.000001/2026-00",
        "In-cio": "01/10/26",
        "Termino": "30/09/31",
        "Cidade": "NITERÓI",
        "UF": "RJ",
        "Ramo-de-atividade": "Atividade fictícia",
        "url": f"http://www.estagio.uff.br/node/{nid}",
        "Objeto": "A CONCEDENTE oferecerá estágios.",
        "Tipo-da-Institui-o": '&lt;a href="/tipo-de-empresa/privada"&gt;Privada&lt;/a&gt;',
        "CNPJ": "11222333000181",
        "Corpo": "",
        "Email": "",
        "Resolu-o-CEP": "",
    }
    corpo = "".join(f"<{k}>{v}</{k}>" for k, v in (padrao | campos).items())
    return f"<node>{corpo}</node>"


def xml(tmp_path: Path, *nos: str) -> Path:
    arquivo = tmp_path / "conveniosestagio.xml"
    arquivo.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><nodes>{"".join(nos)}</nodes>', "utf-8"
    )
    return arquivo


@pytest.mark.unit
@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("01/10/26", date(2026, 10, 1)),
        ("30/12/99", date(2099, 12, 30)),
        ("07/05/15", date(2015, 5, 7)),
        ("", None),
    ],
)
def test_ano_de_dois_digitos_e_sempre_20xx(texto: str, esperado: date | None) -> None:
    assert _data(texto) == esperado


@pytest.mark.unit
def test_le_campos_e_limpa_html(tmp_path: Path) -> None:
    [r] = ler_xml(
        xml(
            tmp_path,
            no(
                15461,
                Email=EMAIL_HTML,
                **{"Resolu-o-CEP": RESOLUCAO_HTML},
            ),
        )
    )
    assert r.id_drupal == 15461
    assert r.tipo_drupal == "Privada"
    assert r.email == "contato@ficticia.example"
    assert r.resolucao == "CEPEX 3463/2024"
    assert r.resolucao_url == "https://exemplo.uff.br/res.pdf"
    assert (r.inicio, r.fim) == (date(2026, 10, 1), date(2031, 9, 30))


@pytest.mark.integration
@pytest.mark.django_db
def test_importa_convenio_completo(tmp_path: Path) -> None:
    relatorio = importar(ler_xml(xml(tmp_path, no(1))))
    assert (relatorio.criados, relatorio.rejeitados) == (1, [])
    c = Convenio.objects.get()
    assert c.id_drupal == 1
    assert c.situacao == Situacao.FINALIZADO
    assert c.finalizado_em is None  # D19: data real desconhecida, fora do tempo de tramitação
    assert c.concedente.tipo == TipoConcedente.EMPRESA_PRIVADA
    assert c.concedente.documento == "11222333000181"
    assert "nó 1" in c.observacoes_internas and "Tipo no Drupal: Privada" in c.observacoes_internas


@pytest.mark.integration
@pytest.mark.django_db
def test_reimportar_atualiza_sem_duplicar(tmp_path: Path) -> None:
    importar(ler_xml(xml(tmp_path, no(1))))
    relatorio = importar(ler_xml(xml(tmp_path, no(1, Termino="29/09/31"))))
    assert (relatorio.criados, relatorio.atualizados) == (0, 1)
    assert Convenio.objects.get().fim_vigencia == date(2031, 9, 29)
    assert Concedente.objects.count() == 1


@pytest.mark.integration
@pytest.mark.django_db
def test_editar_convenio_importado_nao_inventa_data_de_finalizacao(tmp_path: Path) -> None:
    importar(ler_xml(xml(tmp_path, no(1))))
    c = Convenio.objects.get()
    c.observacoes_internas += "\neditado"
    c.save()
    c.refresh_from_db()
    assert c.finalizado_em is None


@pytest.mark.integration
@pytest.mark.django_db
@pytest.mark.parametrize(
    ("campos", "motivo"),
    [
        ({"Nr-CONVENIO": ""}, "sem nº"),
        ({"In-cio": ""}, "sem data"),
        ({"Termino": "01/10/26"}, "não é depois do início"),
        ({"CNPJ": "11222333000180"}, "dígito verificador inválido"),
    ],
)
def test_rejeita_e_explica(tmp_path: Path, campos: dict[str, str], motivo: str) -> None:
    relatorio = importar(ler_xml(xml(tmp_path, no(1, **campos))))
    assert relatorio.criados == 0
    [(nid, _titulo, texto)] = relatorio.rejeitados
    assert nid == 1 and motivo in texto


@pytest.mark.integration
@pytest.mark.django_db
def test_numero_repetido_rejeita_o_segundo_e_nao_deixa_lixo(tmp_path: Path) -> None:
    relatorio = importar(
        ler_xml(xml(tmp_path, no(1), no(2, **{"Nr-CONVENIO": "PR-1/2026", "CNPJ": ""})))
    )
    assert relatorio.criados == 1
    assert "PR-1/2026 já usado" in relatorio.rejeitados[0][2]
    assert Concedente.objects.count() == 1  # a concedente do rejeitado foi desfeita
    assert not any(nid == 2 for nid, _, _ in relatorio.avisos)


@pytest.mark.integration
@pytest.mark.django_db
def test_sem_cnpj_entra_com_aviso_e_agrupa_pelo_nome(tmp_path: Path) -> None:
    relatorio = importar(
        ler_xml(
            xml(
                tmp_path,
                no(1, CNPJ="", Titulo="Loja Antiga"),
                no(2, CNPJ="", Titulo="LOJA ANTIGA", **{"Nr-CONVENIO": "PR-2/2026"}),
            )
        )
    )
    assert relatorio.criados == 2
    assert Concedente.objects.filter(documento__isnull=True).count() == 1
    assert sum("sem CNPJ" in motivo for _, _, motivo in relatorio.avisos) == 2


@pytest.mark.integration
@pytest.mark.django_db
def test_avisa_tipo_desconhecido_uf_invalida_e_vigencia_longa(tmp_path: Path) -> None:
    relatorio = importar(
        ler_xml(
            xml(
                tmp_path,
                no(
                    1,
                    UF="EUA",
                    Termino="30/12/99",
                    **{"Tipo-da-Institui-o": "INSTITUIÇÃO DE ENSINO"},
                ),
                no(2, UF="RIO DE JANEIRO", CNPJ="12ABC34501DE35", **{"Nr-CONVENIO": "PR-2/2026"}),
            )
        )
    )
    motivos = " | ".join(m for _, _, m in relatorio.avisos)
    assert '"INSTITUIÇÃO DE ENSINO" sem correspondência' in motivos
    assert 'UF "EUA" inválida' in motivos
    assert "acima de 5 anos" in motivos
    assert Concedente.objects.get(documento="12ABC34501DE35").uf == "RJ"
    assert Concedente.objects.get(documento="11222333000181").tipo == TipoConcedente.OUTROS


@pytest.mark.e2e
@pytest.mark.django_db
def test_comando_simula_importa_e_publica(tmp_path: Path, client: Client) -> None:
    arquivo = xml(tmp_path, no(1), no(2, **{"In-cio": ""}))
    relatorio = tmp_path / "rel.csv"

    call_command("importar_convenios_drupal", arquivo, "--simular", "--relatorio", relatorio)
    assert not Convenio.objects.exists()

    call_command("importar_convenios_drupal", arquivo, "--relatorio", relatorio)
    assert Convenio.objects.count() == 1
    csv = relatorio.read_text("utf-8-sig")
    assert "rejeitado;2;" in csv and "sem data" in csv

    # Convênio importado vigente aparece na página pública.
    assert "PR-1/2026" in client.get("/", secure=True).content.decode()


@pytest.mark.security
@pytest.mark.django_db
def test_concedente_sem_cnpj_nao_quebra_pagina_publica_e_admin_exige_documento(
    tmp_path: Path, client: Client
) -> None:
    from django.contrib.auth.models import Group, User

    importar(ler_xml(xml(tmp_path, no(1, CNPJ=""))))
    assert client.get("/", secure=True).status_code == 200
    c = Convenio.objects.get()
    assert client.get(f"/convenios/{c.pk}/", secure=True).status_code == 200

    user = User.objects.create_user("divisao", password="senha-teste-123", is_staff=True)
    user.groups.add(Group.objects.get(name="Divisão de Estágio"))
    client.force_login(user)
    url = f"/admin/convenios/concedente/{c.concedente.pk}/change/"
    resposta = client.post(
        url,
        {"documento": "", "razao_social": "X", "tipo": "outros", "uf": "RJ", "cidade": "Niterói"},
        secure=True,
    )
    assert resposta.status_code == 200  # não salvou: documento obrigatório na edição
    assert "documento" in resposta.context["adminform"].form.errors
