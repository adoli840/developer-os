PYTHON ?= python
CONSOLE_SERVER ?= opc@168.107.18.16
CONSOLE_SSH_KEY ?= X:/Settings/ssh/ssh-key-ops.key
DEVOS_OPENAI_ENV ?= X:/Settings/env/developer-os.env

.PHONY: console-run console-test console-deploy console-status console-logs console-restart console-stop console-backup console-backup-verify console-backup-status console-usage-status terminal-status terminal-logs terminal-tunnel-install terminal-tunnel terminal-developer-os terminal-oa terminal-gaia terminal-close workstation-home-install workstation-home-report

console-run:
	$(PYTHON) -m console.devos_console --dev --bind 127.0.0.1 --port 8080

console-test:
	$(PYTHON) -m unittest discover -s console/tests -v

console-deploy:
	powershell -ExecutionPolicy Bypass -File deployment/console/Manage-DeveloperOSConsole.ps1 -Action Deploy -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)" -OpenAiEnv "$(DEVOS_OPENAI_ENV)"

console-status:
	powershell -ExecutionPolicy Bypass -File deployment/console/Manage-DeveloperOSConsole.ps1 -Action Status -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

console-logs:
	powershell -ExecutionPolicy Bypass -File deployment/console/Manage-DeveloperOSConsole.ps1 -Action Logs -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

console-restart:
	powershell -ExecutionPolicy Bypass -File deployment/console/Manage-DeveloperOSConsole.ps1 -Action Restart -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

console-stop:
	powershell -ExecutionPolicy Bypass -File deployment/console/Manage-DeveloperOSConsole.ps1 -Action Stop -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

console-backup:
	powershell -ExecutionPolicy Bypass -File deployment/console/Manage-DeveloperOSConsole.ps1 -Action Backup -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

console-backup-verify:
	powershell -ExecutionPolicy Bypass -File deployment/console/Manage-DeveloperOSConsole.ps1 -Action VerifyBackup -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

console-backup-status:
	powershell -ExecutionPolicy Bypass -File deployment/console/Manage-DeveloperOSConsole.ps1 -Action BackupStatus -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

console-usage-status:
	powershell -ExecutionPolicy Bypass -File deployment/console/Manage-DeveloperOSConsole.ps1 -Action UsageStatus -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

terminal-status:
	powershell -ExecutionPolicy Bypass -File deployment/console/Manage-DeveloperOSConsole.ps1 -Action TerminalStatus -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

terminal-logs:
	powershell -ExecutionPolicy Bypass -File deployment/console/Manage-DeveloperOSConsole.ps1 -Action TerminalLogs -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

terminal-tunnel-install:
	powershell -ExecutionPolicy Bypass -File deployment/workstations/Install-DeveloperOSServerTerminalTunnel.ps1 -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

terminal-tunnel:
	powershell -ExecutionPolicy Bypass -File deployment/workstations/Ensure-DeveloperOSServerTerminalTunnel.ps1 -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

terminal-developer-os:
	powershell -ExecutionPolicy Bypass -File deployment/workstations/Open-DeveloperOSServerTerminal.ps1 -Project developer-os -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

terminal-oa:
	powershell -ExecutionPolicy Bypass -File deployment/workstations/Open-DeveloperOSServerTerminal.ps1 -Project oa -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

terminal-gaia:
	powershell -ExecutionPolicy Bypass -File deployment/workstations/Open-DeveloperOSServerTerminal.ps1 -Project gaia -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

terminal-close:
	powershell -ExecutionPolicy Bypass -File deployment/workstations/Close-DeveloperOSServerTerminalTunnel.ps1

workstation-home-install:
	powershell -ExecutionPolicy Bypass -File deployment/workstations/Install-DeveloperOSWorkstationReporter.ps1 -Workstation home -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

workstation-home-report:
	powershell -ExecutionPolicy Bypass -File deployment/workstations/Report-DeveloperOSGitStatus.ps1 -Workstation home -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"
