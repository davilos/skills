# Lembrete de vencimento verification

**Verdict**: FAIL
**Proofs**: `proofs.md` at 3f9c2a1
**Verifier**: independent sub-agent (author != verifier)

## Checks

| Check | Test | Holds |
| --- | --- | --- |
| C1 | `reminder-job.test.ts` `sends one e-mail at 9h local time` | yes |
| C2 | `reminders.test.ts` `rejects a second reminder for the same invoice` | yes |
| C3 | `reminder-service.test.ts` `skips customers who turned reminders off` | no - asserts that no e-mail was queued, not that `shouldSend` returned "não enviar" |

## Findings

| Finding | Evidence | Fix | Closed |
| --- | --- | --- | --- |
| C3 passa mesmo se a preferência for ignorada quando a fila está vazia | `reminder-service.test.ts:41` - o teste não cria fatura na janela | criar a fatura na janela e afirmar a decisão "não enviar" | |
