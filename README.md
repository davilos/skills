# skills

Skills para agentes de código (Claude Code, Cursor, Windsurf e outros compatíveis com o formato `SKILL.md`), feitas para o dia a dia de engenheiros de software.

Uma skill é uma pasta com instruções e scripts que o agente carrega sozinho quando o pedido combina com a descrição dela. Você instala uma vez e passa a pedir em linguagem natural, por exemplo "make the review page for the plan".

## Skills disponíveis

| Skill                                     | O que faz                                                                                                                                                           | Versão |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| [`plan-review`](skills/plan-review/SKILL.md) | Transforma um `plan.md` do tlc-spec-lean numa página HTML interativa de revisão, seção por seção, e prova com scripts que nada do plano ficou de fora da página. | 1.0.0  |

## Instalação

Com o CLI [`skills`](https://www.npmjs.com/package/skills), na raiz do seu projeto:

```bash
# escolhe interativamente quais skills e quais agentes
npx skills add davilos/skills

# só uma skill
npx skills add davilos/skills --skill plan-review
```

O CLI copia a skill para a pasta de cada agente (`.claude/skills/`, `.cursor/skills/`, `.windsurf/skills/`...).

Instalação manual: copie a pasta `skills/<nome>/` para `.claude/skills/` do projeto ou para `~/.claude/skills/` (vale para todos os projetos). O caminho muda conforme o agente.

## plan-review

Gera uma página de revisão que espelha o `plan.md` de uma feature (`.specs/features/{slug}/plan.md`): Problem, Flow, Impact e Landing ganham visões visuais, cada mudança mostra **Where / Why / Proof** (arquivo e linha, motivo, critério que garante) e cada seção pode ser validada na própria página.

- **Fiel ao plano, e isso é verificado.** O build recusa gerar a página se algum trecho do `plan.md` não chegou aos dados, e o check roda a página no jsdom para confirmar que cada trecho aparece na seção certa e na ordem do plano (`planCoverage: N/N`).
- **Sabe quando ficou desatualizada.** A página guarda o hash do `plan.md` publicado. Se o plano mudar, o build avisa `STALE` e o que foi validado sobre o texto antigo aparece como "validated · changed since".
- **Validação na página.** Publicada como Artifact no claude.ai, a página tem botões "Validate" por seção e "Confirm" por One-way door, e `sync_review.py` traz essas validações de volta para o projeto. Sem Artifact, gera um HTML local que funciona offline.

**Requisitos:** Python 3 (só biblioteca padrão), Node.js com [jsdom](https://www.npmjs.com/package/jsdom) para o check, e um plano no formato do tlc-spec-lean.

**Como pedir:** "make a page for the plan", "plan review page", "update the plan page", "sync what I validated on the page".

Procedimento completo, regras da página e troubleshooting no [SKILL.md](skills/plan-review/SKILL.md). Formato do `review-page.json` em [references/review-page-json.md](skills/plan-review/references/review-page-json.md).

## Estrutura

```
skills/{nome-da-skill}/
├── SKILL.md       # obrigatório: frontmatter YAML + instruções
├── scripts/       # scripts executáveis
├── assets/        # templates e arquivos usados na saída
└── references/    # documentação carregada sob demanda
```

## Contribuindo

As regras para criar ou alterar uma skill estão em [AGENTS.md](AGENTS.md). Em resumo:

- `SKILL.md` com menos de 500 linhas; o resto vai para `references/`.
- A `description` segue `[o que faz] + Use when ... + Do NOT use for ...`, com frases que o usuário realmente diria, até 1024 caracteres e sem `< >`.
- Use a skill `skill-architect` ao criar ou modificar uma skill.

## Licença

[CC BY 4.0](LICENSE) © 2026 Dávilos Tavares. Pode usar, adaptar e redistribuir, inclusive comercialmente, desde que dê crédito ao autor, inclua o link da licença e indique o que foi alterado.
