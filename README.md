# Sistema de Estágios UFF

Gestão de convênios e estágios da PROGRAD/UFF. Escopo, arquitetura e fases estão em
[REQUIREMENTS.md](REQUIREMENTS.md), [ARCHITECTURE.md](ARCHITECTURE.md) e [STEPS.md](STEPS.md).

## Ambiente do zero

Pré-requisitos: [uv](https://docs.astral.sh/uv/) e Docker.

```bash
uv sync                      # instala Python e dependências travadas no uv.lock
docker compose up -d db      # Postgres local (127.0.0.1:5432)
DJANGO_DEBUG=1 uv run python manage.py migrate
DJANGO_DEBUG=1 uv run python manage.py createsuperuser
DJANGO_DEBUG=1 uv run python manage.py runserver
```

## Importação do estagio.uff.br

```bash
uv run python manage.py importar_convenios_drupal conveniosestagio.xml --simular
uv run python manage.py importar_convenios_drupal conveniosestagio.xml
```

O XML vem da exportação do Drupal, feita com login. Rejeitados e avisos vão para `reports/importacao.csv` (abre no Excel). Rodar de novo atualiza, sem duplicar. O arquivo tem dados reais: não o coloque no repositório.

## Tarefas agendadas

Em produção, rode uma vez por dia (cron da STI):

```bash
uv run python manage.py enviar_alertas_vencimento
```

Requer `DIVISAO_EMAIL` e as variáveis de SMTP (`.env.example`). Em modo debug, o email sai no console.

Para um usuário da Divisão de Estágio editar convênios no admin, ele precisa de `is_staff` e de estar no grupo "Divisão de Estágio".

No PowerShell, defina antes `$env:DJANGO_DEBUG="1"`. Variáveis disponíveis: `.env.example`.

## Pipeline

```bash
uv run python tools/ci.py                 # pipeline completo (o mesmo do GitHub Actions)
uv run python tools/ci.py unit            # só unitários
uv run python tools/ci.py integration     # só integração
uv run python tools/ci.py security        # só segurança
uv run python tools/ci.py smoke e2e       # fumaça e ponta a ponta
uv run python tools/ci.py coverage        # cobertura (relatório em reports/)
```

Etapas, na ordem: formatação (ruff), lint + segurança estática (ruff com regras bandit),
tipos (mypy strict), código morto (vulture), migração esquecida (`makemigrations --check`), vulnerabilidades em dependências (pip-audit),
testes por categoria, cobertura mínima de 90%, `manage.py check --deploy`.
Para na primeira etapa reprovada.

## Regras do projeto

- Todo código gerado ou alterado vem com teste unitário.
- Funcionalidade que envolve vários módulos tem teste de integração (`@pytest.mark.integration`).
- Fluxo crítico tem teste ponta a ponta (`@pytest.mark.e2e`).
- O código atende às regras de tipagem, segurança, lint e formatação do pipeline.
- Todo push passa pelo CI; rode `tools/ci.py` localmente antes.
- Cobertura mínima de 90%; não baixe o limite para passar.
- Bug corrigido ganha teste de regressão.
- Nenhuma credencial, `.env` ou dado pessoal real no repositório. Testes usam dados fictícios.
