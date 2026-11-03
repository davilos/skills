# Lembrete de vencimento Specification

**Approved**: 2026-11-03 - user: "pode seguir com o lembrete"

## Problem Statement

Clientes esquecem o vencimento das faturas e pagam com multa; o suporte recebe dezenas de pedidos de segunda via por semana. Um lembrete enviado antes do vencimento reduz atrasos sem esforço do time.

## Goals

- [ ] Reduzir em 30% as faturas pagas com atraso no primeiro mês
- [ ] Nenhum cliente recebe mais de um lembrete por fatura

## Out of Scope

| Feature                | Reason                                     |
| ---------------------- | ------------------------------------------ |
| Lembrete por SMS       | custo por mensagem ainda não aprovado      |
| Cobrança após vencido  | fluxo de cobrança é de outra equipe        |

---

## Assumptions & Open Questions

| Assumption / decision      | Chosen default        | Rationale                                  | Confirmed? |
| -------------------------- | --------------------- | ------------------------------------------ | ---------- |
| Quantos dias antes enviar  | 3 dias                | o mesmo prazo do boleto registrado         | y          |
| Horário do envio           | 9h no fuso do cliente | fora do horário de pico do suporte         | y          |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Lembrete por e-mail ⭐ MVP

**User Story**: As a cliente, I want receber um e-mail antes do vencimento so that eu pague sem multa.

**Why P1**: é o canal que todo cliente já tem cadastrado.

**Acceptance Criteria** (each line is one EARS pattern):

1. WHEN uma fatura em aberto vence em 3 dias THEN system SHALL enviar um e-mail de lembrete às 9h no fuso do cliente
2. IF o cliente não tem e-mail válido THEN system SHALL registrar a fatura como "sem canal" e não enviar nada
3. WHILE a fatura estiver paga system SHALL não enviar lembrete
4. The system SHALL enviar no máximo um lembrete por fatura

**Independent Test**: criar uma fatura que vence em 3 dias, avançar o relógio até as 9h e ver o e-mail na caixa de teste.

---

### P2: Preferência de lembrete

**User Story**: As a cliente, I want desligar os lembretes so that eu não receba e-mails que não quero.

**Why P2**: exigido pela política de comunicação, mas não bloqueia o MVP.

**Acceptance Criteria**:

1. WHEN o cliente desliga os lembretes no perfil THEN system SHALL não enviar lembretes das faturas dele
2. WHEN o cliente religa os lembretes THEN system SHALL voltar a enviar a partir da próxima fatura

**Independent Test**: desligar no perfil, criar uma fatura que vence em 3 dias e ver que nenhum e-mail sai.

---

## Edge Cases

- IF a fatura é criada a menos de 3 dias do vencimento THEN system SHALL enviar o lembrete na próxima janela das 9h
- WHEN o vencimento cai num fim de semana THEN system SHALL usar a data de vencimento original, sem adiar

---

## Requirement Traceability

| Requirement ID | Story                       | Phase | Status  |
| -------------- | --------------------------- | ----- | ------- |
| LEMB-01        | P1: Lembrete por e-mail     | Tasks | In Tasks |
| LEMB-02        | P1: Lembrete por e-mail     | Tasks | In Tasks |
| LEMB-03        | P2: Preferência de lembrete | Tasks | In Tasks |

**Coverage:** 3 total, 3 mapped to tasks, 0 unmapped

---

## Differences from the source

None - no capture or document binds this feature.

## Sources

- Ticket SUP-412 - pedido do suporte para reduzir segunda via

---

## Success Criteria

- [ ] Faturas pagas com atraso caem 30% no primeiro mês
- [ ] Zero reclamações de lembrete duplicado
