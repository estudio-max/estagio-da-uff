"""CPF e CNPJ: normalização, validação de dígito verificador e máscara.

Aceita o CNPJ alfanumérico (IN RFB 2.229/2024, emitido desde julho de 2026):
12 caracteres [A-Z0-9] + 2 dígitos verificadores numéricos.
"""

import re

from django.core.exceptions import ValidationError

_PESOS_CNPJ = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def normalizar(valor: str) -> str:
    """Remove máscara e espaços; letras em maiúsculas."""
    return re.sub(r"[\s./-]", "", valor).upper()


def _dv_cpf(base: str) -> str:
    soma = sum(int(d) * peso for d, peso in zip(base, range(len(base) + 1, 1, -1), strict=True))
    resto = soma * 10 % 11
    return str(0 if resto == 10 else resto)


def _dv_cnpj(base: str, pesos: list[int]) -> str:
    # No CNPJ alfanumérico cada caractere vale ord(c) - 48: "0"=0 ... "9"=9, "A"=17 ...
    soma = sum((ord(c) - 48) * peso for c, peso in zip(base, pesos, strict=True))
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def cpf_valido(cpf: str) -> bool:
    if not re.fullmatch(r"\d{11}", cpf) or len(set(cpf)) == 1:
        return False
    dv1 = _dv_cpf(cpf[:9])
    return cpf[9:] == dv1 + _dv_cpf(cpf[:9] + dv1)


def cnpj_valido(cnpj: str) -> bool:
    if not re.fullmatch(r"[A-Z0-9]{12}\d{2}", cnpj) or len(set(cnpj)) == 1:
        return False
    dv1 = _dv_cnpj(cnpj[:12], _PESOS_CNPJ)
    return cnpj[12:] == dv1 + _dv_cnpj(cnpj[:12] + dv1, [6, *_PESOS_CNPJ])


def validar_documento(valor: str) -> None:
    """Validador de campo: espera o valor já normalizado."""
    if (len(valor) == 11 and cpf_valido(valor)) or (len(valor) == 14 and cnpj_valido(valor)):
        return
    raise ValidationError("CPF ou CNPJ inválido.", code="documento_invalido")


def formatar(valor: str) -> str:
    if len(valor) == 11:
        return f"{valor[:3]}.{valor[3:6]}.{valor[6:9]}-{valor[9:]}"
    if len(valor) == 14:
        return f"{valor[:2]}.{valor[2:5]}.{valor[5:8]}/{valor[8:12]}-{valor[12:]}"
    return valor
