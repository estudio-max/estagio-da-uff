"""Pipeline local, o mesmo que roda no GitHub Actions. Falha na primeira etapa reprovada.

Uso:  uv run python tools/ci.py [etapa ...]
Sem argumento roda tudo. Etapas: format lint types deadcode migrations audit unit integration
security smoke e2e coverage check
"""

import os
import secrets
import subprocess
import sys

PYTEST = ["pytest", "-q", "-p", "no:cacheprovider"]

ETAPAS: dict[str, list[str]] = {
    "format": ["ruff", "format", "--check", "."],
    "lint": ["ruff", "check", "."],
    "types": ["mypy", "."],
    "deadcode": ["vulture"],
    "migrations": [sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"],
    "audit": ["pip-audit", "--progress-spinner", "off"],
    "unit": [*PYTEST, "-m", "unit"],
    "integration": [*PYTEST, "-m", "integration"],
    "security": [*PYTEST, "-m", "security"],
    "smoke": [*PYTEST, "-m", "smoke"],
    "e2e": [*PYTEST, "-m", "e2e"],
    "coverage": [
        *PYTEST,
        "--cov",
        "--cov-report=term-missing",
        "--cov-report=xml:reports/coverage.xml",
        "--junitxml=reports/junit.xml",
    ],
    "check": [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
}


def main(nomes: list[str]) -> int:
    # Valores só para o check --deploy simular produção; nunca usados fora do pipeline.
    os.environ.setdefault("DJANGO_SECRET_KEY", secrets.token_urlsafe(50))
    os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "estagios.exemplo.uff.br")
    for nome in nomes or list(ETAPAS):
        print(f"\n=== {nome} ===", flush=True)
        codigo = subprocess.call(ETAPAS[nome])  # noqa: S603 — comandos fixos acima
        # pytest sai com 5 quando nenhum teste tem o marcador: etapa vazia não reprova
        if codigo not in (0, 5):
            print(f"\nREPROVADO na etapa '{nome}'", file=sys.stderr)
            return codigo
    print("\nPipeline verde.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
