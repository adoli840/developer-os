from __future__ import annotations

from pathlib import Path
from typing import Any

from .api_mainline_run import ApiMainlineRunStore
from .control_plane import ControlPlaneError, OrchestrationControlStore
from .dispatch_preview import DispatchPreviewStore
from .workspace_guard import WorkspaceGuardError, capture_workspace_binding


class MainlineDispatchBridge:
    def __init__(
        self,
        runs: ApiMainlineRunStore,
        previews: DispatchPreviewStore,
        control: OrchestrationControlStore,
        workspace: Path,
        *,
        distro: str = "Ubuntu",
    ) -> None:
        self.runs = runs
        self.previews = previews
        self.control = control
        self.workspace = workspace
        self.distro = distro

    def prepare(self, project: str) -> dict[str, Any]:
        if project != "btest":
            raise ValueError("API_MAINLINE_DISPATCH_BTEST_ONLY")
        source_handoff = self.runs.prepared_handoff(project)
        try:
            seal = capture_workspace_binding(project, self.workspace, distro=self.distro)
        except WorkspaceGuardError as error:
            raise ControlPlaneError(str(error)) from error
        self.control.update_node(
            project,
            "BTEST_CODEX_WORKER",
            {"transport_ref": seal.as_transport_ref()},
        )
        return self.previews.prepare_mainline_handoff(project, source_handoff)
