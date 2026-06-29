# Prompts

## New Project Prompt

```text
Before starting a new project, review the following:

1. Check whether the feature already exists in another project.
2. Check whether existing code or Blueprints can be reused.
3. Recommend a language and database based on the project purpose.
4. Create a basic folder structure and README.
5. Decide whether Docker, tests, and AI integration are needed.
6. Record important decisions in Decisions.md.
```

## Project Inspection Prompt

```text
Inspect the project for runtime readiness, README quality, configuration, tests, folder structure, database choice, convenience, efficiency, duplicated functionality, and AI automation opportunities.

Do not only list problems. Provide improvement proposals.
```

## Handoff Prompt From GPT To Codex

```text
Goal:
Constraints:
Design decision:
Implementation scope:
Do not change:
Verification:
```

## Handoff Prompt From Codex To GPT

```text
Context:
What changed:
Why:
Open questions:
Files:
```

## Token-Efficient Codex Implementation Prompt

```text
Use the provided design as the implementation specification.

Do not repeat broad architectural analysis unless the code contradicts the design or the design is incomplete.

Read context in this order:

1. README.md
2. PROJECT_CONTEXT.md
3. PROJECT_RULES.md, if present
4. Relevant DeveloperOS policy
5. Files explicitly named in the task
6. Additional files only when needed

Implement the requested change, verify it, and summarize what changed.
```

