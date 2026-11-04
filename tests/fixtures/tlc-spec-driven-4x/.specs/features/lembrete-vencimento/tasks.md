# Lembrete de vencimento Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, the walk, check_proofs, the Verifier and the screens sub-agent).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/lembrete-vencimento/design.md`
**Status**: Approved
**Approved**: 2026-11-03 - user: "tasks ok"
**Build**: `npm run build; npx tsc --noEmit; npm run lint`
**Run unit**: `npx vitest run src/reminders src/jobs --reporter=verbose`

---

## Test Coverage Matrix

| Layer      | Test type   | Location                          |
| ---------- | ----------- | --------------------------------- |
| Service    | unit        | `src/reminders/*.test.ts`         |
| Job        | integration | `src/jobs/reminder-job.test.ts`   |

## Gate Check Commands

| Gate  | Command                                  |
| ----- | ---------------------------------------- |
| quick | `npx vitest run src/reminders`           |
| full  | `npx vitest run src/reminders src/jobs`  |
| build | `npm run build`                          |

---

## Execution Plan

### Phase 1: Foundation

```
T1 → T2
```

### Phase 2: Core Implementation

```
T3 → T4
```

---

## Task Breakdown

### T1: Criar a tabela reminders

**What**: migração com a tabela `reminders` e o índice único em `invoiceId`.
**Where**: `migrations/2026_11_03_reminders.sql`
**Depends on**: None
**Reuses**: o formato das migrações em `migrations/`
**Requirement**: LEMB-02

**Done when**:

- [ ] A migração sobe e desce sem erro
- [ ] Inserir duas linhas com o mesmo `invoiceId` falha

**Tests**: integration
**Gate**: full

---

### T2: Implementar ReminderService

**What**: `shouldSend` e `record` com as regras de pago, sem canal, preferência e duplicado.
**Where**: `src/reminders/reminder-service.ts`
**Depends on**: T1
**Reuses**: `src/services/base.ts`
**Requirement**: LEMB-01

**Done when**:

- [ ] Fatura paga devolve "não enviar"
- [ ] Cliente sem e-mail devolve "sem canal"
- [ ] Gate check passes: `npx vitest run src/reminders`

**Tests**: unit
**Gate**: quick

---

### T3: Respeitar a preferência do cliente

**What**: `shouldSend` lê `CustomerPrefs` e não envia para quem desligou os lembretes.
**Where**: `src/reminders/reminder-service.ts` (modify)
**Depends on**: T2
**Reuses**: `src/customers/prefs.ts`
**Requirement**: LEMB-03

**Done when**:

- [ ] Cliente com lembrete desligado devolve "não enviar"
- [ ] Gate check passes: `npx vitest run src/reminders`

**Tests**: unit
**Gate**: quick

---

### T4: Criar o ReminderJob

**What**: job horário que seleciona a janela das 9h e envia pelo Mailer.
**Where**: `src/jobs/reminder-job.ts`
**Depends on**: T3
**Reuses**: `src/jobs/scheduler.ts`
**Requirement**: LEMB-01

**Done when**:

- [ ] O job envia um e-mail por fatura da janela
- [ ] Gate check passes: `npx vitest run src/reminders src/jobs`

**Tests**: integration
**Gate**: full

**Commit**: `feat(reminders): send due-date reminders by e-mail`

---

## Checks

**C1** - uma fatura que vence em 3 dias recebe um e-mail às 9h no fuso do cliente (LEMB-01, AC 1)
Proof: run unit | ✓ reminder-job > sends one e-mail at 9h local time

**C2** - um segundo envio da mesma fatura é recusado pelo banco (LEMB-02, AC 4)
Proof: run unit | ✓ reminders > rejects a second reminder for the same invoice

**C3** - cliente com lembrete desligado não recebe e-mail (LEMB-03, AC 1)
Proof: run unit | ✓ reminder-service > skips customers who turned reminders off

---

## Handoff

**Settled mid-build:** none
**Dispatched:** none
**Walked:** none

---

## Phase Execution Map

```
Phase 1 → Phase 2

Phase 1:  T1 ------→ T2
Phase 2:  T2 ------→ T3 ------→ T4
```
