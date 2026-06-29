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

## AI Snapshot Policy

Snapshots are separate from Git.

A snapshot is a short-term recovery mechanism for AI work. It does not replace Git commits.

Use snapshots to recover quickly when AI changes are wrong or too broad.

## Snapshot Creation Triggers

Create a snapshot before:

- Changes over 100 lines
- Changes across 3 or more files
- File deletion
- Structural changes
- Refactoring
- Database schema changes
- Multi-file AI edits

Small edits do not require snapshots.

## Snapshot Contents

A snapshot should record:

- Target files
- Work purpose
- Creation timestamp

Snapshots must not pollute Git history.

## Recovery Principle

Git is long-term version control. Snapshots are short-term recovery.

If AI makes a mistake, prefer simple snapshot restore over complex Git recovery commands.

## AI Work Sequence

```text
Snapshot
-> Implementation
-> Verification
-> Next task
```

## Role Split

GPT handles design, technical review, documentation, code review, and direction setting.

Codex handles code creation, code modification, file creation, tests, and Git work.

## Token Saving Policy

Use GPT for long explanations, technology comparisons, architecture discussion, and documentation drafts.

Use Codex for implementation, modification, refactoring, file creation, tests, and Git work.

## Commit Policy

Git commits should be infrequent but meaningful.

Intermediate work is protected by snapshots.

## AI Behavior Rules

- Codex must create snapshots before large or risky changes.
- Codex should not perform broad project analysis only to create a commit.
- Checkpoint work should use minimal analysis.
- Codex should avoid large speculative edits.

## DeveloperOS Goal

DeveloperOS is not an application project repository. DeveloperOS is the developer's operating system.

DeveloperOS manages development philosophy, global rules, AI collaboration, technical decisions, knowledge, Blueprints, and snapshot policy.

## Snapshot Manager

DeveloperOS should eventually include Snapshot Manager.

Goal:

- Automatically create snapshots before risky AI work.
- Restore failed AI work with one simple command.
- Operate separately from Git.

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

