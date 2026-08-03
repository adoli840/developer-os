# AI Development Workflow & Safety Policy

## Purpose

This policy defines the safety workflow for AI-assisted development.

Goals:

- Maximize developer productivity.
- Minimize Codex token usage.
- Make AI mistakes easy to recover from.
- Keep Git history clean and meaningful.

## Git Operating Principles

Git manages final development history.

Git history should remain readable and meaningful.

Do not create final commits only for typo fixes, tiny bug fixes, minor refactoring, or intermediate AI work.

Create commits at meaningful boundaries:

- Feature completion
- Meaningful refactoring completion
- End-of-day checkpoint

## Recovery Principle

Git is the sole recovery mechanism for source-code work. AI agents must not
create parallel file-copy snapshots before edits.

Before changing tracked files, inspect the working tree and preserve unrelated
developer changes. Use normal Git commits and branches at meaningful boundaries
so completed work remains recoverable. Never discard or overwrite existing
uncommitted work to simplify recovery.

Database backups, deployment rollback artifacts, provider usage records, and
other project-owned operational recovery data are separate from this source-code
rule and continue to follow their own policies.

## AI Work Sequence

```text
Git inspection
-> Implementation
-> Verification
-> Commit
```

## Role Split

GPT handles design, technical review, documentation, code review, and direction setting.

Codex handles code creation, code modification, file creation, tests, and Git work.

## Token Saving Policy

Use GPT for long explanations, technology comparisons, architecture discussion, and documentation drafts.

Use Codex for implementation, modification, refactoring, file creation, tests, and Git work.

## Commit Policy

Git commits should be infrequent but meaningful.

Committed Git history protects completed work. Keep intermediate edits scoped
and verify them before committing.

## AI Behavior Rules

- Codex must inspect Git state before large or risky changes.
- Codex should not perform broad project analysis only to create a commit.
- Checkpoint work should use minimal analysis.
- Codex should avoid large speculative edits.

## DeveloperOS Goal

DeveloperOS is not an application project repository. DeveloperOS is the developer's operating system.

DeveloperOS manages development philosophy, global rules, AI collaboration,
technical decisions, knowledge, Blueprints, and Git safety policy.

## AI Handoff Principles

GPT and Codex are separate sessions and do not share chat memory.

They must document handoff information through DeveloperOS.

Important decisions, development direction, technology choices, and workflow rules must be recorded in DeveloperOS documents.

DeveloperOS documents are the official communication channel between GPT and Codex.

## Context And Token Cost Policy

The most expensive Codex activities are usually:

1. Large project analysis
2. Long architectural reasoning
3. Multi-file edits that require reading many files
4. Context restoration from vague requests

Command execution such as Docker or test commands usually costs little AI token budget compared with reading and reasoning.

Codex should minimize context restoration by relying on existing design documents and project context files.

If GPT has already produced a design, Codex should implement that design instead of repeating the design process.

