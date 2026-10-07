# Sistema de Estágios UFF — instruções para o Claude

Projeto em equipe (STI + bolsistas), todos usando Claude Code. Este arquivo é compartilhado: mudanças aqui passam por PR.

## Fonte da verdade

Leia antes de qualquer tarefa:
- `REQUIREMENTS.md`: o quê, regras, critérios de aceitação, dúvidas pendentes (D1…)
- `ARCHITECTURE.md`: como está construído e as decisões (A1…)
- `STEPS.md`: fase atual e incremento em andamento

As **melhorias em relação ao SIGAA** (`REQUIREMENTS.md` §4.0, IDs MS01…) são requisito fundamental do projeto. Toda fase entrega as que lhe cabem, com teste. Nenhuma funcionalidade nova pode reproduzir uma falha listada ali.

Não implemente nada que esteja fora da fase atual do `STEPS.md`. Se o assunto ainda é uma dúvida pendente (D#), não invente a regra: pergunte ao desenvolvedor.

## Fluxo de trabalho em equipe

- Uma branch por incremento (`fase1a-cadastro-convenio`) e PR para `main`. Nunca commitar direto na `main`.
- Antes de começar, rode `git pull` e confira no `STEPS.md` se alguém já assumiu o item.
- O PR que muda comportamento atualiza no mesmo PR o `REQUIREMENTS.md`, o `ARCHITECTURE.md` e o `STEPS.md` afetados.
- Nova decisão técnica entra como uma linha na tabela de decisões do `ARCHITECTURE.md`.
- O PR só é aberto com o pipeline local verde, e o merge só acontece com o CI verde e a revisão de outro desenvolvedor.

## Comandos

- Pipeline completo antes de abrir o PR: `uv run python tools/ci.py`. O README lista as demais etapas.
- Postgres local: `docker compose up -d db`.

## Regras

- Português nos documentos, nas mensagens de commit e na interface; código e identificadores em inglês.
- Nunca colocar credenciais, `.env` ou dados reais de estudantes ou empresas no repositório nem nos testes. Use dados fictícios.
- Toda regra de negócio nova vem com o seu teste.
- CPF não aparece em tela ou saída pública. Se um requisito novo exigir expor, use a máscara do gov.br (`***.456.789-**`, RN08) e confirme antes com o responsável.
