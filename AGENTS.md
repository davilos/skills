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
