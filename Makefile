PYTHON ?= python
CONSOLE_SERVER ?= opc@168.107.18.16
CONSOLE_SSH_KEY ?= X:/Settings/ssh/ssh-key-ops.key
DEVOS_OPENAI_ENV ?= X:/Settings/env/developer-os.env
DEVOS_DEPLOY_TARGET := console-deploy
WORKSTATION_REPORT_INTERVAL_MINUTES ?= 5

.PHONY: self-enable self-check make-check docker-policy-check console-run console-test console-deploy console-status console-logs console-restart console-stop console-backup console-backup-verify console-backup-status console-usage-status terminal-status terminal-logs terminal-tunnel terminal-developer-os terminal-oa terminal-gaia terminal-close workstation-home-report workstation-office-report workstation-home-auto-enable workstation-home-auto-disable workstation-home-auto-status workstation-office-auto-enable workstation-office-auto-disable workstation-office-auto-status

self-enable:
	powershell -NoProfile -ExecutionPolicy Bypass -File 04_Tools/self/Enable-DeveloperOSSelfApplication.ps1

self-check:
	powershell -NoProfile -ExecutionPolicy Bypass -File 04_Tools/self/Test-DeveloperOSSelfApplication.ps1

make-check:
	powershell -NoProfile -ExecutionPolicy Bypass -File 04_Tools/make/Test-DeveloperOSMake.ps1
	powershell -NoProfile -ExecutionPolicy Bypass -File 04_Tools/docker/Test-DockerImageBuildPolicy.ps1

docker-policy-check:
	powershell -NoProfile -ExecutionPolicy Bypass -File 04_Tools/docker/Test-DockerImageBuildPolicy.ps1

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

ifeq ($(OS),Windows_NT)
	powershell -ExecutionPolicy Bypass -File deployment/console/Manage-DeveloperOSConsole.ps1 -Action UsageStatus -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"
else
	systemctl list-timers developer-os-openai-usage.timer --no-pager; sudo systemctl --no-pager --full status developer-os-openai-usage.service || true; sudo journalctl -u developer-os-openai-usage.service --no-pager -n 60; test -s /var/lib/developer-os-console/openai-usage.json && echo OPENAI_USAGE_SNAPSHOT=present || echo OPENAI_USAGE_SNAPSHOT=missing; test -s /var/lib/developer-os-console/oracle-usage.json && echo ORACLE_USAGE_SNAPSHOT=present || echo ORACLE_USAGE_SNAPSHOT=missing
endif

terminal-status:
	powershell -ExecutionPolicy Bypass -File deployment/console/Manage-DeveloperOSConsole.ps1 -Action TerminalStatus -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

terminal-logs:
	powershell -ExecutionPolicy Bypass -File deployment/console/Manage-DeveloperOSConsole.ps1 -Action TerminalLogs -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

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

workstation-home-report:
	powershell -ExecutionPolicy Bypass -File deployment/workstations/Report-DeveloperOSGitStatus.ps1 -Workstation home -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

workstation-office-report:
	powershell -ExecutionPolicy Bypass -File deployment/workstations/Report-DeveloperOSGitStatus.ps1 -Workstation office -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

workstation-home-auto-enable:
	powershell -NoProfile -ExecutionPolicy Bypass -File deployment/workstations/Manage-DeveloperOSWorkstationReporter.ps1 -Action Install -Workstation home -IntervalMinutes "$(WORKSTATION_REPORT_INTERVAL_MINUTES)" -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

workstation-home-auto-disable:
	powershell -NoProfile -ExecutionPolicy Bypass -File deployment/workstations/Manage-DeveloperOSWorkstationReporter.ps1 -Action Remove -Workstation home

workstation-home-auto-status:
	powershell -NoProfile -ExecutionPolicy Bypass -File deployment/workstations/Manage-DeveloperOSWorkstationReporter.ps1 -Action Status -Workstation home

workstation-office-auto-enable:
	powershell -NoProfile -ExecutionPolicy Bypass -File deployment/workstations/Manage-DeveloperOSWorkstationReporter.ps1 -Action Install -Workstation office -IntervalMinutes "$(WORKSTATION_REPORT_INTERVAL_MINUTES)" -Server "$(CONSOLE_SERVER)" -SshKey "$(CONSOLE_SSH_KEY)"

workstation-office-auto-disable:
	powershell -NoProfile -ExecutionPolicy Bypass -File deployment/workstations/Manage-DeveloperOSWorkstationReporter.ps1 -Action Remove -Workstation office

workstation-office-auto-status:
	powershell -NoProfile -ExecutionPolicy Bypass -File deployment/workstations/Manage-DeveloperOSWorkstationReporter.ps1 -Action Status -Workstation office
