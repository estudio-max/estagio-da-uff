# REQUIREMENTS — Sistema de Estágios UFF

> Fontes: briefing técnico (SGE/SIGE, base Lei 11.788/2008 e páginas da PROGRAD), brainstorming da equipe e reunião Estágios@PROGRAD de 05/10/2026.
> Estado do projeto em 06/10/2026: **nenhum código existe**. Tudo abaixo está **pendente**.

## 1. Objetivo

Substituir o controle disperso (planilhas internas de convênios públicos e privados, página estática no site, e-mails, peticionamento no SEI) por um sistema único que:

1. Controle o ciclo de vida dos convênios de estágio com alertas proativos de vencimento.
2. Publique automaticamente os convênios vigentes (com campos seletivos definidos pela PROGRAD).
3. Reduza a barreira de entrada de empresas e instituições públicas na solicitação de convênio.
4. Em fases posteriores, conduza o TCE, aditivos, relatórios e encerramento do estágio.

Diretriz da reunião: **separar o "o quê" do "como"**. O "o quê" do processo atual se mantém; o "como" pode mudar. Entregas pequenas e frequentes (ágil); primeiro micropasso é o módulo de convênios.

## 2. Usuários

| Perfil | Fase em que entra | Papel |
|---|---|---|
| Divisão de Estágio / PROGRAD | MVP | Única com escrita no MVP. Cadastra e acompanha convênios, define o que é público, recebe alertas. |
| Público (qualquer pessoa) | MVP | Consulta convênios vigentes. |
| Concedente / Agente de Integração (externo) | Fase 2 | Solicita convênio e envia documentos via gov.br. |
| Estudante | Fase 3+ | Consulta, submete TCE, relatórios. |
| Coordenação de curso / Orientador / Supervisor | Fase 3+ | Aprovação e assinatura de TCE e plano de atividades. |
| SDC (arquivo da UFF) | Futuro | Guarda histórica legal dos documentos. |

## 3. Requisitos funcionais

### Alta prioridade — MVP (Fase 1: convênios internos)

| ID | Requisito | Status |
|---|---|---|
| RF01 | Cadastrar convênio: concedente (razão social, CNPJ, tipo — ver RN05), nº do convênio, nº do processo SEI, modalidade de minuta (padrão UFF / externa), datas de início e fim de vigência, situação, observações internas. | Pendente |
| RF02 | Registrar o andamento interno do processo (etapas: documentação recebida, análise, termo preparado, assinatura concedente, assinatura pró-reitor, ratificação, publicação do extrato no BS, finalizado). | Pendente |
| RF03 | Marcar, por campo, o que é público. Definição pela PROGRAD. | Pendente |
| RF04 | Página pública com convênios vigentes, com busca por nome/CNPJ/tipo. Convênio entra na página automaticamente ao ser finalizado. | Pendente |
| RF05 | Alertas de vencimento para a Divisão (e-mail e painel), com antecedências configuráveis. | Pendente |
| RF06 | Painéis estratégicos: vigentes, encerrados/vencidos, vencendo em 30/90/180 dias, em tramitação, por tipo de concedente. Visibilidade (pública/privada) definida pela PROGRAD. | Pendente |
| RF07 | Importar os dados atuais das planilhas (públicos e privados) e da página do site. | Pendente |
| RF08 | Histórico de alterações de cada convênio (quem, quando, o quê). | Pendente |

### Média prioridade — Fase 2 (entrada externa)

| ID | Requisito | Status |
|---|---|---|
| RF09 | Login de usuário externo via gov.br (login único); primeira entrada gera pré-cadastro. | Pendente |
| RF10 | Divisão valida o pré-cadastro e vincula a pessoa como representante do CNPJ. | Pendente |
| RF11 | Representante solicita convênio com checklist dinâmico de documentos por tipo de proponente e upload. | Pendente |
| RF12 | Divisão analisa a documentação e, aprovada, abre o processo no SEI (manualmente no início). | Pendente |
| RF13 | Proponente acompanha o andamento da solicitação. | Pendente |
| RF14 | Fluxo interno distinto para convênios iniciados pela UFF (instituições públicas). | Pendente |

### Baixa prioridade / futuro (Fases 3+)

- TCE + Plano de Atividades com validações automáticas; assinatura em cadeia (gov.br).
- Termos aditivos, relatórios semestrais com lembrete, rescisão e Termo de Realização.
- Integração com sistema acadêmico (matrícula ativa, pré-requisitos, horários).
- Assinatura eletrônica gov.br de convênios dentro do sistema.
- Integração com SEI e transferência ao arquivo (SDC).
- Publicação de vagas pela concedente.

## 4. Regras de negócio

Aplicáveis ao MVP:

- RN01 — Convênio aparece na página pública somente quando finalizado e com vigência em curso.
- RN02 — Convênio com fim de vigência passado muda para "vencido" automaticamente (derivado da data, não editado à mão).
- RN03 — CNPJ válido (dígito verificador) e único por concedente.
- RN04 — Apenas a Divisão de Estágio escreve no MVP.
- RN05 — Tipos de convênio (lista oficial do formulário atual da PROGRAD): Instituição de Ensino Privada; Empresa Privada; ONGs e OSCIPs; Órgãos dos Governos Federal, Estadual e Municipal; Profissional Liberal; Agente de Integração; Instituições de Ensino Públicas; Microempresas; Outros.

Para fases futuras (fonte: Lei 11.788/2008 e páginas da PROGRAD — confirmar com a Divisão antes de implementar):

- Jornada máxima 6h/dia e 30h/semana (graduação); estágio interno não obrigatório 4h/20h.
- Vigência máxima de 24 meses na mesma concedente, exceto estudante com deficiência.
- Recesso de 30 dias a cada 12 meses (proporcional).
- TCE só com convênio vigente da concedente ou de agente de integração conveniado.
- Apólice de seguro obrigatória no TCE; no obrigatório sem apólice da empresa, usar apólice institucional.
- Matrícula ativa como pré-condição para início e continuidade.
- Convênio com minuta externa exige ratificação pelos Conselhos Superiores.

## 5. Requisitos não funcionais

- RNF01 — Dados pessoais tratados conforme LGPD; hospedagem na infraestrutura da UFF.
- RNF02 — Login institucional para usuários internos; gov.br para externos (Fase 2).
- RNF03 — Trilha de auditoria em toda alteração de convênio.
- RNF04 — Página pública acessível (WCAG AA básico) e responsiva.
- RNF05 — Volume de referência: ~2.000 convênios ativos; ~60 mil estudantes nas fases futuras.
- RNF06 — Documentos em armazenamento de objetos; banco guarda só metadados.
- RNF07 — Backup diário do banco e dos documentos.

## 6. Critérios de aceitação do MVP

- Divisão cadastra, edita e consulta convênio sem planilha paralela.
- Ao marcar "finalizado", o convênio aparece na página pública sem passo manual, exibindo só os campos marcados como públicos.
- Usuário não autenticado não acessa campos internos (teste automatizado).
- Alerta é enviado nas antecedências configuradas; teste com data simulada.
- Painel mostra contagens que batem com consulta direta ao banco.
- Dados das planilhas atuais importados com relatório de linhas rejeitadas.

## 7. Fora do escopo atual

TCE e ciclo do estágio, integração com sistema acadêmico, assinatura digital, integração automática com SEI e SDC, vagas, app móvel.

## 8. Dúvidas e decisões pendentes

| # | Dúvida | Alternativas | Quem decide |
|---|---|---|---|
| D1 | O processo de convênio precisa obrigatoriamente tramitar no SEI? | (a) SEI continua sendo o processo oficial, sistema só controla; (b) sistema abre processo no SEI via API; (c) migrar fluxo para fora do SEI. Consenso provisório: trabalhar em paralelo, Divisão abre o processo no SEI. | PROGRAD + STI |
| D2 | Quais campos do convênio são públicos? | Lista atual do site como ponto de partida. | PROGRAD |
| D3 | Antecedências dos alertas de vencimento? | 12, 6, 3 e 1 mês (sugestão da reunião: "um ano, seis meses"). | PROGRAD |
| D4 | Quais painéis são públicos? | STI sugere público; PROGRAD decide. | PROGRAD |
| D5 | ~~Stack~~ Django decidido em 06/10/2026. Hospedagem: padrão da STI? | — | STI |
| D6 | Login: gov.br ou idUFF (provável), a definir. | Até lá, login nativo do Django; o escolhido entra como backend de autenticação sem reestruturar. | STI |
| D7 | Etapas exatas do processo interno, nos dois modelos (empresa procura UFF / UFF procura instituição pública). | Passo a passo prometido pela Divisão. | PROGRAD |
| D8 | Formato e qualidade das planilhas atuais (colunas, duplicatas). | — | PROGRAD envia cópia |
| D9 | Exigências do SDC sobre guarda de documentos. | Aguardar participação do SDC. | SDC |
| D10 | Credenciamento gov.br da UFF para login único (Fase 2) já existe? | — | STI |
