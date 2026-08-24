# Docker Desktop VHD Final Global Asset Gate

Reconciled: 2026-08-15

This report reconciles later project forensic evidence into the existing
82-asset inventory. It does not authorize or execute Docker Desktop removal.

## A. Project Approval State

| Project | Final vote | Persistent UNKNOWN | Evidence conclusion |
|---|---|---:|---|
| bTest | APPROVE_DELETION | 0 | 679 user tables compared; 4,709 meaningful Desktop-only provenance rows are externally preserved and restore-verified |
| OA | APPROVE_DELETION | 0 | `OA_DESKTOP_PERSISTENT_UNIQUE_DATA = 0` |
| Gaia | APPROVE_DELETION | 0 | Desktop-only 32 rows are one obsolete incomplete simulation; physical and logical preservation and PG17 restore passed |

`PROJECT_APPROVAL_GATE = PASS (3/3)`

## B. Updated 82-Asset Matrix Counts

The complete row-level matrix is `DesktopVhdAssetMatrix.json`, SHA-256
`d8af442de94e37789d51e1bdd927f5783b5b5ac2ee6694436b07669b8cb4f512`.

| Type | Count |
|---|---:|
| Containers | 2 |
| Images | 44 |
| Volumes | 12 |
| Networks | 10 |
| Build cache | 14 |
| Total | 82 |

| Final classification | Count |
|---|---:|
| SAFE_TO_DELETE_WITH_DESKTOP | 76 |
| EXTERNALLY_PRESERVED_THEN_SAFE_TO_DELETE | 6 |
| KEEP_OUTSIDE_DESKTOP | 0 |
| VETO_DELETE | 0 |
| UNKNOWN | 0 |

The `KEEP_OUTSIDE_DESKTOP` artifacts listed below are external preservation
assets and therefore are not members of the 82 Desktop asset rows.

## C. Six Preserved Assets And Evidence

| Owner | Desktop asset | Preservation artifact | External path | SHA-256 | Restore/verification |
|---|---|---|---|---|---|
| bTest | `btest_consolidated_postgres_data` | PostgreSQL custom logical archive | `X:\Docker\Forensic\btest-desktop-elliott-forward-run-manifests-20260815.dump` | `077e368c...23e335` | PASS; 69,837 rows restored, including all 4,709 Desktop-only keys |
| Gaia | `gaia_postgres-data` | PostgreSQL 17 custom logical archive | `D:\Gaia-forensics\20260815-desktop-native\logical-preservation\desktop-gaia-pg17.dump` | `8dc69461...90abe6` | PASS; 62 public tables and core row counts matched |
| unknown | `0a5ed0...734b1` | physical PG16 volume archive | `X:\Docker\Forensics\global-anonymous-volumes\0a5ed0c20c2e61e5a9f004f92a63d986e30257faa85bb50aa2f8540b042734b1-pgdata-20260815.tar` | `5601c2cf...af5eaf` | SHA verified; disposable clone completed crash recovery and reached ready state |
| unknown | `957fc7...b399` | physical PG16 volume archive | `X:\Docker\Forensics\global-anonymous-volumes\957fc7c02fbc4c1b659db9ad2b2edd90e6b964e77c6f5d0816e123457e93b399-pgdata-20260815.tar` | `1b2530e1...bb2f8` | SHA verified; disposable clone completed crash recovery and reached ready state |
| DeveloperOS | `46277a...2bc02` | full read-only VHD forensic copy | `X:\Docker\Forensics\vhd\docker_data-20260815T044434Z-forensic-copy.vhdx` | `e3ceb00f...a3161` | source/copy size and SHA-256 match |
| DeveloperOS | `7ccf98...96742` | full read-only VHD forensic copy | same as above | `e3ceb00f...a3161` | source/copy size and SHA-256 match |

The bTest evidence manifest is
`X:\Docker\Forensic\btest-desktop-db-forensic-manifest-20260815.json`
(SHA-256 `a098a646...451bf`). It records equal database/table/migration sets,
679 compared user tables, and only
`learning.elliott_forward_run_manifests` differing. The classification is
`HAS_UNIQUE_MEANINGFUL_DATA` plus `EXTERNALLY_PRESERVED_AND_VERIFIED`.

The Gaia evidence manifest is
`D:\Gaia-forensics\20260815-desktop-native\logical-preservation\desktop-gaia-forensic-manifest.json`
(SHA-256 `f84600af...53f2d`). It also seals the physical archive, roles dump,
logical comparison, and restored row counts.

## D. Temp Volume Final Dispositions

Both anonymous volumes were created within 78 seconds on 2026-08-05, have no
Compose/project labels, no remaining Desktop container relation, and contain an
isolated database lifecycle rather than an application database. OA absence was
independently confirmed. Existing physical archives were checksum-verified and
their disposable native clones completed PostgreSQL recovery.

They are classified `DISPOSABLE_FORENSIC_OR_TEST_ARTIFACT`, not meaningful
canonical data. Separate logical preservation is not required. The per-volume
archives plus the hash-identical full VHD copy are sufficient preservation.
Both final rows are `EXTERNALLY_PRESERVED_THEN_SAFE_TO_DELETE`.

## E. devos_verify Volume Dispositions

`46277a...2bc02` and `7ccf98...96742` contain `devos_verify`, the temporary
database created by `deployment/console/verify-postgres-backup.sh` for isolated
backup restore verification. The script recreates the database from canonical
project backup files and removes its temporary verification container.

These volumes are disposable verification residue, not canonical DeveloperOS
data. The full VHD copy preserves them. Both final rows are
`EXTERNALLY_PRESERVED_THEN_SAFE_TO_DELETE`.

## F. Build-Cache Disposition

All 14 build-cache records contain reproducible build inputs/layers and no
persistent project data. Unknown project ownership does not block removal.
All remain `SAFE_TO_DELETE_WITH_DESKTOP`.

## G. VETO_DELETE Count

`VETO_DELETE = 0`

## H. UNKNOWN Count

`UNKNOWN = 0`

Unknown ownership on generic build cache or disposable temp volumes is not an
unknown data disposition and does not reopen the gate.

## I. KEEP_OUTSIDE_DESKTOP Assets

Never include these in the Docker Desktop deletion path:

- `X:\Docker\Forensics\vhd\docker_data-20260815T044434Z-forensic-copy.vhdx`
- its VHD and final-gate manifests under `X:\Docker\Forensics\vhd`
- `X:\Docker\Forensic\btest-desktop-elliott-forward-run-manifests-20260815.dump`
- `X:\Docker\Forensic\btest-desktop-db-forensic-manifest-20260815.json`
- `X:\Docker\Forensics\btest\btest-desktop-postgres-20260815T004028Z.tar`
- both anonymous-volume archives under `X:\Docker\Forensics\global-anonymous-volumes`
- all files under `D:\Gaia-forensics\20260815-desktop-native`
- project/repository backup and recovery contracts

The 51,538,558,976-byte forensic VHD copy is rollback evidence, not runtime
storage. Retain it until Docker Desktop removal, native runtime verification,
and bTest/OA/Gaia restore acceptance are complete. Deleting it later requires a
separate explicit retention decision.

## J. External Preservation Checksum Verification

The bTest logical dump, both anonymous archives, and all five Gaia manifest-
listed evidence files were rehashed and match their manifests. The read-only
VHD copy remains unchanged in size and attributes; its sealed source/copy hash
is `e3ceb00f8eabc02b5b80664da6c1e6ea2e1f8084791b34c80356a985ce1a3161`.

The final preservation gate manifest is
`X:\Docker\Forensics\vhd\final-global-asset-gate-manifest-20260815.json`.

## K. Native Pre-Removal Baseline

Current canonical native boundary:

- Ubuntu WSL2
- Docker Engine `29.7.2`
- daemon ID `f81bb277-08d7-4618-8fa6-ac154eb424b3`
- Docker root `/var/lib/docker-wsl`
- socket `/run/docker-wsl.sock`
- Compose `/usr/libexec/docker/cli-plugins/docker-compose` `5.4.0`
- running project services: bTest, bTest DB, OA, OA DB, Gaia dev/sim/DB
- native named project volumes include bTest consolidated/sealed/rehearsal,
  `oa_postgres_data`, `gaia_postgres-data`, and project caches

Native forensic clone containers and volumes currently present are also outside
the Desktop deletion boundary. Do not delete them as part of Desktop removal;
clean them only through a separate forensic-retention decision.

## L. Exact Destructive Cleanup Sequence

Execute only after a separate `AUTHORIZE_GLOBAL_DOCKER_DESKTOP_REMOVAL`:

1. Rehash every `KEEP_OUTSIDE_DESKTOP` artifact and recapture the native
   container, image, volume, network, daemon ID, root, socket, and service
   baseline. Abort on drift or missing preservation evidence.
2. Confirm project vote 3/3, `VETO_DELETE=0`, `UNKNOWN=0`, and healthy native
   bTest/OA/Gaia services and databases.
3. Remove the `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\Docker Desktop`
   login entry first, so removal/reboot cannot relaunch Desktop.
4. Stop Docker Desktop processes, `com.docker.service`, and only the
   `docker-desktop` WSL distribution. Confirm the original VHD is quiescent.
5. Run the official Docker Desktop uninstaller. Do not use recursive deletion
   against any WSL, Docker, project, or forensic parent directory.
6. If the uninstaller leaves it registered, unregister only the exact
   `docker-desktop` distribution. Never unregister `Ubuntu`.
7. Remove only the original Desktop storage path
   `X:\Docker\DockerDesktopWSL` after confirming the forensic copy is outside
   that tree and still hash-valid.
8. Remove residual Docker Desktop Windows service/application entries and
   Desktop-only named pipe/integration state.
9. Remove only `desktop-linux` context, `credsStore=desktop` or
   `desktop.exe` references, Desktop helper/plugin remnants, and obsolete
   Desktop PATH/environment entries. Preserve `/home/devops/.docker-native`.
10. Reboot or sign out/in, then run the post-removal sequence below. Do not
    prune or delete native Docker assets at any step.

Absolute native KEEP list:

- Ubuntu WSL
- `/usr/bin/docker`
- `/usr/libexec/docker/cli-plugins/docker-compose`
- `docker-wsl.service`
- `/run/docker-wsl.sock`
- `/var/lib/docker-wsl`
- every native bTest/OA/Gaia container, image, volume, and network
- DeveloperOS shared launcher and `/home/devops/.docker-native`
- all `KEEP_OUTSIDE_DESKTOP` artifacts above

Desktop deletion list only:

- Docker Desktop application and Windows service/components
- `docker-desktop` WSL distribution
- original `X:\Docker\DockerDesktopWSL` storage and VHD
- the 82 Desktop containers/images/volumes/networks/cache records
- Desktop-only contexts, configs, helpers, startup entry, PATH, and environment
  references

## M. Post-Removal Verification Sequence

1. Confirm `docker-desktop` is absent and Ubuntu remains WSL2 and starts.
2. Confirm no Docker Desktop process, service, startup Run entry, context,
   helper, PATH, or environment reference remains.
3. Confirm `docker-wsl.service` is active and the shared launcher reports
   Docker `29.7.2`, `/var/lib/docker-wsl`, and `/run/docker-wsl.sock`.
4. Confirm native Compose `5.4.0` and native credential-helper discovery.
5. Compare native container/image/volume/network identities with the sealed
   pre-removal baseline; any missing project volume is an immediate STOP.
6. Verify bTest/OA/Gaia container health, API access, database connectivity,
   schema/migration state, and project-owned backup status without rebuilding.
7. Rehash the bTest, Gaia, anonymous-volume, and forensic-VHD preservation
   artifacts and confirm no path under `KEEP_OUTSIDE_DESKTOP` changed.
8. Reboot/sign in once more and confirm Docker Desktop does not return and no
   dead startup error appears.

## N. Residual Risk

- The destructive phase remains vulnerable to an overly broad installer or
  filesystem path selection; exact-path checks are mandatory.
- The forensic VHD copy consumes about 48 GB and must not be mistaken for stale
  Docker Desktop runtime storage.
- Native disposable forensic clones remain; they are not a Desktop-removal
  blocker but need a later retention cleanup decision.
- A future Docker/WSL update could alter native service behavior, so the
  baseline must be recaptured immediately before removal.

## O. Global Asset Gate

`GLOBAL_ASSET_GATE = PASS`

## P. Authorization Readiness

`READY_FOR_GLOBAL_AUTHORIZATION = YES`

`AUTHORIZE_GLOBAL_DOCKER_DESKTOP_REMOVAL` has not been issued. No destructive
cleanup was performed.
