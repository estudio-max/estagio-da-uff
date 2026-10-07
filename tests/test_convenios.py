from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from convenios.models import (
    Concedente,
    Convenio,
    Situacao,
    TipoConcedente,
    Vigencia,
    somar_anos,
)

HOJE = date(2026, 10, 6)


def novo_convenio(**campos: object) -> Convenio:
    padrao: dict[str, object] = {
        "numero": "PR-001/2026",
        "situacao": Situacao.FINALIZADO,
        "inicio_vigencia": date(2026, 1, 1),
        "fim_vigencia": date(2030, 12, 31),
    }
    return Convenio(**(padrao | campos))


@pytest.fixture
def concedente(db: None) -> Concedente:
    return Concedente.objects.create(
        documento="11222333000181",
        razao_social="Empresa Fictícia Ltda",
        tipo=TipoConcedente.EMPRESA_PRIVADA,
        uf="RJ",
        cidade="Niterói",
    )


# --- RN02: vigência derivada (unitário, sem banco) ---


@pytest.mark.unit
@pytest.mark.parametrize(
    ("campos", "esperado"),
    [
        ({"situacao": Situacao.EM_TRAMITACAO}, Vigencia.EM_TRAMITACAO),
        ({"situacao": Situacao.CANCELADO}, Vigencia.CANCELADO),
        ({"inicio_vigencia": date(2026, 10, 7)}, Vigencia.A_INICIAR),
        ({"inicio_vigencia": HOJE}, Vigencia.VIGENTE),
        ({"fim_vigencia": HOJE}, Vigencia.VIGENTE),
        ({"fim_vigencia": date(2026, 10, 5)}, Vigencia.VENCIDO),
    ],
)
def test_vigencia_derivada(campos: dict[str, object], esperado: Vigencia) -> None:
    assert novo_convenio(**campos).vigencia(HOJE) == esperado


# --- RN07: vigência máxima de 5 anos ---


@pytest.mark.unit
def test_somar_anos_trata_29_de_fevereiro() -> None:
    assert somar_anos(date(2028, 2, 29), 5) == date(2033, 3, 1)
    assert somar_anos(date(2026, 9, 8), 5) == date(2031, 9, 8)


@pytest.mark.unit
def test_cinco_anos_menos_um_dia_e_aceito() -> None:
    # Mesmo padrão do convênio real PR-212/2026: 08/09/2026 a 07/09/2031.
    novo_convenio(inicio_vigencia=date(2026, 9, 8), fim_vigencia=date(2031, 9, 7)).clean()


@pytest.mark.unit
def test_vigencia_de_cinco_anos_completos_e_rejeitada() -> None:
    convenio = novo_convenio(inicio_vigencia=date(2026, 9, 8), fim_vigencia=date(2031, 9, 8))
    with pytest.raises(ValidationError) as erro:
        convenio.clean()
    assert "fim_vigencia" in erro.value.message_dict


# --- Constraints no banco (integração) ---


@pytest.mark.integration
def test_fim_antes_do_inicio_e_barrado_no_banco(concedente: Concedente) -> None:
    with pytest.raises(IntegrityError):
        novo_convenio(
            concedente=concedente, inicio_vigencia=date(2026, 5, 1), fim_vigencia=date(2026, 4, 1)
        ).save()


@pytest.mark.integration
@pytest.mark.parametrize("faltando", ["numero", "inicio_vigencia", "fim_vigencia"])
def test_finalizado_exige_numero_e_datas(concedente: Concedente, faltando: str) -> None:
    vazio = "" if faltando == "numero" else None
    with pytest.raises(IntegrityError):
        novo_convenio(concedente=concedente, **{faltando: vazio}).save()


@pytest.mark.integration
def test_em_tramitacao_pode_ficar_sem_numero_e_datas(concedente: Concedente) -> None:
    for _ in range(2):  # número vazio não conta para a unicidade
        Convenio.objects.create(concedente=concedente)
    assert Convenio.objects.count() == 2


@pytest.mark.integration
def test_numero_do_convenio_e_unico(concedente: Concedente) -> None:
    novo_convenio(concedente=concedente).save()
    with pytest.raises(IntegrityError):
        novo_convenio(concedente=concedente).save()


@pytest.mark.integration
def test_filtro_de_vigencia_no_banco_bate_com_a_regra(concedente: Concedente) -> None:
    casos: dict[str, dict[str, object]] = {
        "PR-1/2026": {"situacao": Situacao.EM_TRAMITACAO},
        "PR-2/2026": {"situacao": Situacao.CANCELADO},
        "PR-3/2026": {"inicio_vigencia": date(2026, 12, 1)},
        "PR-4/2026": {},
        "PR-5/2026": {"inicio_vigencia": date(2021, 1, 1), "fim_vigencia": date(2025, 12, 31)},
    }
    for numero, campos in casos.items():
        novo_convenio(concedente=concedente, numero=numero, **campos).save()

    for vigencia in Vigencia:
        no_banco = set(Convenio.objects.com_vigencia(vigencia, HOJE).values_list("pk", flat=True))
        na_regra = {c.pk for c in Convenio.objects.all() if c.vigencia(HOJE) == vigencia}
        assert no_banco == na_regra, vigencia
        assert len(no_banco) == 1, vigencia


# --- Concedente (RN03/RN06) ---


@pytest.mark.integration
def test_concedente_normaliza_documento_e_barra_duplicado(concedente: Concedente) -> None:
    outra = Concedente(
        documento="11.222.333/0001-81",
        razao_social="Duplicada",
        tipo=TipoConcedente.OUTROS,
        uf="RJ",
        cidade="Niterói",
    )
    with pytest.raises(ValidationError) as erro:
        outra.full_clean()
    assert outra.documento == "11222333000181"
    assert "documento" in erro.value.message_dict


@pytest.mark.integration
def test_profissional_liberal_entra_com_cpf(db: None) -> None:
    pessoa = Concedente(
        documento="529.982.247-25",
        razao_social="Profissional Fictício",
        tipo=TipoConcedente.PROFISSIONAL_LIBERAL,
        uf="RJ",
        cidade="Niterói",
    )
    pessoa.full_clean()
    pessoa.save()
    assert pessoa.documento_formatado == "529.982.247-25"
    assert str(pessoa) == "Profissional Fictício"
