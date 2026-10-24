Always follow the general rules in @general-rules.md.

## Skill Structure

```
skills/{skill-name}/
├── SKILL.md          # Required — YAML frontmatter + markdown body
├── scripts/          # Optional executable scripts
├── templates/        # Optional file templates
└── references/       # Optional on-demand documentation
```

Keep `SKILL.md` under 500 lines; offload reference material to `references/`.

### Skill Quality Standards

**When creating a new skill or modifying an existing one, you MUST use the `skill-architect` skill** to ensure it follows best practices. If the `skill-architect` skill is not installed, follow these mandatory description rules:

- **Structure**: `[What it does] + [Use when ...] + [Do NOT use for ...]`
- **"Use when"** is mandatory — include actual phrases users would say
- **"Do NOT use for"** is mandatory — add negative triggers to prevent overlap with similar skills
- **Under 1024 characters** — no XML angle brackets (`< >`)
- **User perspective** — write trigger phrases as things the user would actually say, not internal jargon

### Versioning

**Whenever a skill is created or updated, bump `metadata.version` in its `SKILL.md` and update the matching "Versão" column in `README.md` in the same commit.** The two must always match.

### Security

**Before committing a new or changed skill, run `scripts/security-scan.sh`** (needs `SNYK_TOKEN`). It runs Snyk Agent Scan on `skills/` (prompt injection, malicious code, secrets) and Snyk Code on the scripts — the same checks as `.github/workflows/snyk.yml`. Fix findings instead of ignoring them; if one is a false positive, say so in the commit message.
