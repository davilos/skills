# skills

## Skills disponíveis

| Skill                                     | O que faz                                                                                                                                                           | Versão |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| [`local-judge`](skills/local-judge/SKILL.md) | Revisa a branch local contra a base (com mudanças não commitadas) antes de abrir o PR: só findings com evidência `arquivo:linha` ou URL, gate determinístico, ledger por branch para re-runs e aplicação dos fixes escolhidos. | 1.0.0 |
| [`doc-spec-review`](skills/doc-spec-review/SKILL.md) | Transforma documentos Markdown locais numa página HTML interativa de revisão, seção por seção, e prova com scripts que nada ficou de fora. Reconhece o formato: plano da tlc-spec-lean (abas Visual, cards Where / Why / Proof, doors), feature da tlc-spec-driven (uma aba por arquivo, critérios EARS, tasks e checks revisáveis um a um, IDs ligados entre abas) ou qualquer outro documento (TDD, ADR, RFC, PRD). Substitui `plan-review` e `doc-review`. | 1.0.0 |

## Instalação

Com o CLI [`skills`](https://www.npmjs.com/package/skills), na raiz do seu projeto:

```bash
# escolhe interativamente quais skills e quais agentes
npx skills add davilos/skills

# só uma skill
npx skills add davilos/skills --skill doc-spec-review
npx skills add davilos/skills --skill local-judge
```

Quem usava `plan-review` ou `doc-review`: instale `doc-spec-review` e remova as duas. Os arquivos de estado antigos (`review-page.json`, `x-doc-review.json`) são renomeados para `doc-spec-review.json` / `x-doc-spec-review.json` no primeiro build, e as páginas publicadas mantêm o link e as validações.

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
- Ao criar ou alterar uma skill, suba o `metadata.version` no `SKILL.md` e atualize a coluna "Versão" deste README no mesmo commit.
- Rode `scripts/security-scan.sh` (com `SNYK_TOKEN` definido) antes de commitar: o Snyk Agent Scan procura prompt injection, código malicioso e segredos nas skills, e o Snyk Code analisa os scripts. O mesmo roda no CI a cada push e PR.

## Licença

[CC BY 4.0](LICENSE) © 2026 Dávilos Tavares. Pode usar, adaptar e redistribuir, inclusive comercialmente, desde que dê crédito ao autor, inclua o link da licença e indique o que foi alterado.
