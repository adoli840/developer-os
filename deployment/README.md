# Deployment Standard Manager

## Purpose

This directory defines the DeveloperOS deployment standard for workspace projects.

DeveloperOS owns the reusable deployment standard. Individual project repositories own their actual application code, Docker files, compose files, GitHub workflow files, and production-specific exceptions.

## Scope

The deployment manager can:

- Store project deployment configuration in `projects.yml`
- Generate GitHub Actions workflow files from templates
- Check whether projects look deploy-ready
- Print required GitHub Secrets names
- Generate Codex-readable deployment guidance

The deployment manager must not store secret values.

## Commands

Check all configured projects:

```powershell
.\deployment\scripts\check-project-deploy-ready.ps1
```

Generate one project's workflow:

```powershell
.\deployment\scripts\generate-deploy-workflow.ps1 -Project bTest
```

Generate every configured workflow:

```powershell
.\deployment\scripts\generate-deploy-workflow.ps1 -All
```

Print deployment guide:

```powershell
.\deployment\scripts\print-deploy-guide.ps1
```

## Safety

The scripts do not push code, connect to production servers, or write GitHub Secrets.

GitHub Secrets should be registered manually in GitHub.
