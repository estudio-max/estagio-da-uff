# STEPS — Sistema de Estágios UFF

Estado em 06/10/2026: Fase 1a concluída (pipeline local verde). **Próxima: Fase 1b (importação), que depende das planilhas (D8).**

| Fase | Objetivo | Status | Complexidade |
|---|---|---|---|
| 0 | Fundação | Concluída | Baixa |
| 1 | Convênios internos + página pública + alertas + painéis (MVP) | Em andamento (1a concluída) | Média |
| 2 | Solicitação externa via gov.br | Pendente (depende D1, D10) | Média |
| 3 | TCE e ciclo do estágio | Fora do escopo atual | Alta |
| 4 | Assinatura gov.br, SEI, SDC, sistema acadêmico | Fora do escopo atual | Alta |

## Fase 0 — Fundação

- **Inclui**: repositório git, projeto no framework escolhido, Postgres em container, lint/formatação/tipagem, testes rodando, pipeline de CI, `.env.example`.
- **Feito**: Django 5.2 + Postgres 17 (Docker), ruff, mypy strict, vulture, pip-audit, pytest com marcadores por categoria, cobertura mínima de 90%, `check --deploy`, `tools/ci.py` e GitHub Actions. Endpoint `/health/`. Admin com login nativo do Django.
- **Critério de conclusão**: pipeline local verde ✅; CI verde no primeiro PR.
- **Ficou para depois**: SonarQube (depende da infraestrutura da STI); teste de mutação (entra na Fase 1, quando houver regra de negócio; ferramenta prevista: mutmut).

## Fase 1 — MVP de convênios

Entregas em incrementos curtos, cada um mostrado na reunião semanal:

1. **1a** ✅ — Modelo Concedente/Convênio/Etapa + interface interna de cadastro e edição + auditoria. (RF01, RF02, RF08). App `convenios`; cadastro pelo admin do Django; grupo "Divisão de Estágio"; vigência derivada com filtro; CPF/CNPJ (inclusive alfanumérico) com máscara opcional; vigência de no máximo 5 anos. 45 testes, cobertura de 98%. Para a Divisão usar: adicionar o usuário (com `is_staff`) ao grupo.
2. **1b** — Importação das planilhas. (RF07) — depende de D8.
3. **1c** — Página pública com busca, só campos públicos. (RF03, RF04) — depende de D2.
4. **1d** — Job diário de alertas. (RF05) — depende de D3.
5. **1e** — Painéis estratégicos. (RF06) — depende de D4.

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
