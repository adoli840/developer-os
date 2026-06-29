# Language Policy

## Purpose

DeveloperOS is expected to be used for many years by the developer, GPT, Codex, and other AI coding agents.

This policy keeps DeveloperOS portable, searchable, and easy for AI tools to parse.

## Official Policy

English is the official documentation language for DeveloperOS.

All governance documents under DeveloperOS shall be written in English. Existing Korean governance documents must be migrated to English to maintain a single documentation language.

## Communication Rule

The developer may communicate with GPT and Codex in Korean.

AI should respond to the developer in Korean by default unless the developer requests another language.

## Language Matrix

| Area | Default Language | Notes |
|---|---|---|
| Code | English | Filenames, modules, functions, classes, variables, constants |
| Directory names | English | Use stable and searchable names |
| DeveloperOS governance Markdown | English | Architecture, rules, standards, workflow, safety policy |
| README files | English | Add `README_KO.md` only when Korean onboarding is explicitly useful |
| AI rules | English | Shared by GPT, Codex, and future AI agents |
| Commit messages | English | Keep Git history searchable and tool-friendly |
| Code comments | English | Prefer clear code; comment only non-obvious intent |
| Knowledge notes | Korean allowed | Use Korean when personal recall or local domain accuracy is better |
| Developer to GPT conversation | Korean allowed | Use the most comfortable language |
| Developer to Codex conversation | Korean allowed | Codex should respond in Korean by default |

## English Required

- `Workspace.md`
- `Architecture.md`
- `GovernanceModel.md`
- `CodingStandards.md`
- `AI_Rules.md`
- `AI_Collaboration.md`
- `AI_Workflow_Safety_Policy.md`
- `LanguagePolicy.md`
- `Decisions.md`
- project `README.md`
- project `PROJECT_CONTEXT.md`
- project `PROJECT_RULES.md`

## Korean Allowed

Korean may be used for personal or domain-specific knowledge when it improves accuracy or recall.

Examples:

- Personal lessons learned
- Troubleshooting notes written for personal memory
- Meeting notes
- Korean tax, HR, compliance, or government-service notes
- Business context that is naturally Korean

## Migration Rule

Existing Korean governance documents must be migrated to English.

Personal knowledge notes do not require immediate translation unless they become governance or reusable project policy.

## AI Behavior

- Answer the developer in Korean by default.
- Write durable DeveloperOS policy documents in English.
- Keep implementation artifacts in English.
- Preserve Korean only when it carries personal or local-domain meaning.
- If the developer provides Korean design text, Codex may convert it into English policy documentation while preserving intent.

## Goal

The goal is not to force the developer to think in English.

The goal is to let the developer communicate comfortably in Korean while keeping DeveloperOS useful to GPT, Codex, IDEs, search tools, and future AI coding agents.

