import pytest
from django.core.exceptions import ValidationError

from convenios.documentos import formatar, normalizar, validar_documento

pytestmark = pytest.mark.unit

CPF_VALIDO = "52998224725"
CNPJ_VALIDO = "11222333000181"
CNPJ_ALFANUMERICO_VALIDO = "12ABC34501DE35"  # exemplo oficial da Receita Federal


@pytest.mark.parametrize("valor", [CPF_VALIDO, CNPJ_VALIDO, CNPJ_ALFANUMERICO_VALIDO])
def test_aceita_documento_valido(valor: str) -> None:
    validar_documento(valor)


@pytest.mark.parametrize(
    "valor",
    [
        "52998224724",  # CPF com DV errado
        "11222333000180",  # CNPJ com DV errado
        "12ABC34501DE36",  # CNPJ alfanumérico com DV errado
        "11111111111",  # CPF com dígitos repetidos (passa no cálculo, mas é inválido)
        "00000000000000",  # CNPJ com dígitos repetidos
        "12ABC34501DEAB",  # DV do CNPJ alfanumérico tem de ser numérico
        "5299822472",  # tamanho errado
        "",
    ],
)
def test_rejeita_documento_invalido(valor: str) -> None:
    with pytest.raises(ValidationError):
        validar_documento(valor)


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("529.982.247-25", CPF_VALIDO),
        ("11.222.333/0001-81", CNPJ_VALIDO),
        (" 12.abc.345/01de-35 ", CNPJ_ALFANUMERICO_VALIDO),
    ],
)
def test_normaliza_mascara_espacos_e_caixa(entrada: str, esperado: str) -> None:
    assert normalizar(entrada) == esperado


def test_formata_cpf_e_cnpj() -> None:
    assert formatar(CPF_VALIDO) == "529.982.247-25"
    assert formatar(CNPJ_VALIDO) == "11.222.333/0001-81"
    assert formatar(CNPJ_ALFANUMERICO_VALIDO) == "12.ABC.345/01DE-35"
    assert formatar("123") == "123"
