# STEPS — Sistema de Estágios UFF

Estado em 07/10/2026: **Fase 1 completa** (1a a 1e). Próximo: homologação com a Divisão usando os dados reais importados, e respostas às dúvidas D3, D4, D11, D15, D17, D20 e D21.

| Fase | Objetivo | Status | Complexidade |
|---|---|---|---|
| 0 | Fundação | Concluída | Baixa |
| 1 | Convênios internos + página pública + alertas + painéis (MVP) | Concluída, aguardando homologação | Média |
| 2 | Solicitação externa via gov.br | Pendente (depende D1, D10) | Média |
| 3 | TCE e ciclo do estágio | Fora do escopo atual | Alta |
| 4 | Assinatura gov.br, SEI, SDC, sistema acadêmico | Fora do escopo atual | Alta |

Toda fase entrega as melhorias sobre o SIGAA que lhe cabem (REQUIREMENTS §4.0) e só é concluída com elas testadas.

## Fase 0 — Fundação

- **Inclui**: repositório git, projeto no framework escolhido, Postgres em container, lint/formatação/tipagem, testes rodando, pipeline de CI, `.env.example`.
- **Feito**: Django 5.2 + Postgres 17 (Docker), ruff, mypy strict, vulture, pip-audit, pytest com marcadores por categoria, cobertura mínima de 90%, `check --deploy`, `tools/ci.py` e GitHub Actions. Endpoint `/health/`. Admin com login nativo do Django.
- **Critério de conclusão**: pipeline local verde ✅; CI verde no primeiro PR.
- **Ficou para depois**: SonarQube (depende da infraestrutura da STI); teste de mutação (entra na Fase 1, quando houver regra de negócio; ferramenta prevista: mutmut).

## Fase 1 — MVP de convênios

Entregas em incrementos curtos, cada um mostrado na reunião semanal:

1. **1a** ✅ — Modelo Concedente/Convênio/Etapa + interface interna de cadastro e edição + auditoria. (RF01, RF02, RF08). App `convenios`; cadastro pelo admin do Django; grupo "Divisão de Estágio"; vigência derivada com filtro; CPF/CNPJ (inclusive alfanumérico) com máscara opcional; vigência de no máximo 5 anos. 45 testes, cobertura de 98%. Para a Divisão usar: adicionar o usuário (com `is_staff`) ao grupo.
2. **1b** ✅ — Importação do estagio.uff.br. (RF07). Comando `importar_convenios_drupal <xml>` com `--simular` e relatório CSV; idempotente pelo nó do Drupal. Carga real: 4.133 de 4.190 convênios em ~3 min (ver REQUIREMENTS §4.1.1). A fonte foi a exportação XML do Drupal, não as planilhas (D8 deixa de bloquear). 104 testes, cobertura de 99%.
3. **1c** ✅ — Página pública com busca, só campos públicos. (RF03, RF04, MS06, MS07 parcial). Lista em `/` com busca por nome, CNPJ (com ou sem máscara), nº do convênio e processo; filtros por tipo e UF; paginação; detalhe em `/convenios/<id>/`. Campos públicos espelham o estagio.uff.br; CPF nunca aparece nem é buscável. 56 testes, cobertura de 98%.
4. **1d** ✅ — Job diário de alertas. (RF05, MS01 parcial). Comando `enviar_alertas_vencimento`: um email por dia à Divisão com os convênios que entraram em faixa de aviso; nunca repete aviso; job parado manda só o mais urgente; renovação reinicia. No admin: filtro "vence em", coluna de dias e avisos enviados. Antecedências por premissa (D3). 79 testes, cobertura de 99%. **Para produção:** STI agenda o comando 1x por dia e configura SMTP e `DIVISAO_EMAIL`.
5. **1e** ✅ (+ gráficos em 07/10/2026: indicadores, vencimentos por mês, convênios por ano, vigentes por UF e por tipo, concedentes que não renovaram) — Painéis estratégicos. (RF06, MS05 parcial). Página "Painel" no admin, restrita à Divisão (D4): convênios por situação, vigentes que vencem em 30/90/180 dias (com link para a lista filtrada), vigentes por tipo, tempo médio e mediano de tramitação no último ano, e os 10 convênios em tramitação há mais tempo. Novo campo `finalizado_em`, automático. 87 testes, cobertura de 99%.

- **Testes**: unitário (validação de CNPJ, situação derivada de datas, seleção de alertas por data), integração (CRUD + auditoria no banco, importação com rejeitos), segurança (rota interna exige login; página pública não vaza campo interno), ponta a ponta (cadastrar → finalizar → aparece na página pública).
- **Critério de conclusão**: critérios de aceitação do REQUIREMENTS §6 atendidos em homologação com a Divisão; Divisão deixa de usar as planilhas.
- **Riscos**: qualidade dos dados legados; definição de campos públicos atrasar 1c.

## Fase 2 — Entrada externa

- **Inclui**: RF09–RF14, upload de documentos, checklist por tipo de proponente.
- **Pré-requisitos**: Fase 1 em produção; D1 e D10 resolvidas; D7 (passo a passo dos dois modelos).
- **Critério**: empresa solicita convênio sem conta no SEI; Divisão recebe documentação completa no sistema.

## Fases 3 e 4

Insumo da Fase 3: o fluxo e as falhas do SIGAA levantados no REQUIREMENTS §4.3.

Replanejar quando a Fase 2 estiver em produção, com SDC e coordenações participando.
