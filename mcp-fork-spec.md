# ha-mcp-server fork — spec

Purpose: a curated, **read-only-first** Home Assistant MCP server that supplies the *HA-side
facts* the `home-assistant-update` skill needs, replacing the skill's current fragile prose
("check the config dir", "ask the user", "grep the sparse container stderr").

Upstream: `https://github.com/but3k4/ha-mcp-server` (MIT, 77 tools, stdio/sse/streamable-http).
We run HA as a **Container** install (plain Docker, no Supervisor) — this drives most trimming.

## Design rules

1. **The server owns HA facts. The skill owns judgment + Nomad.**
   - Server: version, loaded integrations, repairs issues, HA log, config validation, restart.
   - Skill (unchanged): GitHub release list, blog/release-notes triage, breaking-change gate,
     `nomad job plan` / `nomad_run_job` / wakeups / alloc health. None of that is HA state.
2. **Read-only by default.** Token is full-scope; every write tool is opt-in behind a flag.
3. **Supervisor tools are opt-in, not deleted.** They hit `/api/hassio/*`, absent on Container.
   The write ops `HomeAssistantError` outright; the read ops may work. Gate the whole group
   behind `HA_ENABLE_SUPERVISOR` (default off) and test the reads against our live instance
   before relying on them — nothing is removed from the fork.

## Configuration

Keep upstream's env-driven config, add three toggles:

| Var | Default | Meaning |
| --- | --- | --- |
| `HA_URL` | — | HA base URL, no trailing slash (we use `https://hass.glono.us`) |
| `HA_TOKEN` | — | Long-lived access token (secret — store in Nomad Variables, see below) |
| `TRANSPORT` | `stdio` | `stdio` for local MCP client |
| `HA_READONLY` | `true` | When true, register **no** write/destructive tools |
| `HA_ENABLE_RESTART` | `false` | Exposes `restart_core` (write) only when explicitly true |
| `HA_ENABLE_SUPERVISOR` | `false` | Registers Supervisor-backed tools (add-ons, OS/supervisor/core/host, backups). Reads may work on Container; writes fail. Default off. |

### Token handling

- **Never commit the token.** Add to repo's `.gitignore` (it already ignores `.env`).
- Store as a Nomad Variable under `nomad/jobs/home-assistant` (`ha_mcp_token`). The MCP server
  process reads it from `HA_TOKEN`; loading it is a human-approved `nomad var get`. Document the
  key in `jobs/home-assistant/README.md`; never print its value.
- Token creation (human, one-time): HA profile → Security → Long-lived access tokens → Create.

## Supervisor tools — gate behind `HA_ENABLE_SUPERVISOR` (default false)

These call `/api/hassio/*`, which a Container install does not expose. We do **not** delete
them: the write ops `HomeAssistantError` outright, so keep them off by default, while the read
ops may work and can be useful — register the whole group behind the opt-in flag and verify the
reads against our live instance before relying on them.

Reads (keep behind the flag; verify on Container before use): `list_addons`, `get_addon_info`,
`get_addon_logs`, `list_addon_repositories`, `get_supervisor_logs`, `get_core_logs`,
`get_host_logs`, `get_multicast_logs`, `get_supervisor_info`, `get_core_info`, `get_host_info`,
`get_os_info`, `list_backups`.

Writes (behind the flag; expected to fail on Container): `install_addon`, `uninstall_addon`,
`update_addon`, `start_addon`, `stop_addon`, `restart_addon`, `add_addon_repository`,
`set_addon_options`, `update_core`, `update_supervisor`, `update_os`, `create_backup`.

> Keep `get_ha_config` (it reads `/api/config`, not Supervisor) and `get_error_log`
> (`/api/log`, Core-backed, works on Container) **outside** this gate — they stay always-on.

## Tools to KEEP from upstream

`list_entities`, `get_entity`, `search_entities`, `list_services`, `list_areas`, `list_devices`,
`list_entity_registry`, `get_entity_history`, `get_logbook`, `get_error_log`,
`list_automations`, `list_scripts`, `list_scenes`, `get_ha_config`, `check_config`,
`list_users`, `list_input_helpers`, `get_device_registry`, `list_config_entries`,
`get_system_health`.

All write tools from upstream (`set_entity_state`, `call_service`, `fire_event`, dashboard
create/update/delete, `trigger_automation`, enable/disable, `run_script`, `activate_scene`,
`set_input_*`, `*_timer`, `reload_config_entry`) are **gated behind `HA_READONLY=false`**
(default off). `restart_core` is gated behind `HA_ENABLE_RESTART=true`.

## Tools to ADD (new in the fork)

Each is a thin wrapper over an existing HA REST endpoint. Signatures below follow upstream's
style (async, return parsed JSON, raise `HomeAssistantError` on non-2xx).

### 1. `get_repairs_issues`  — *the headline tool*

- Endpoint: `GET /api/repairs/issues`
- Returns: list of open issues. Per item surface: `issue_id`, `domain`,
  `translation_key`, `severity`, **`breaks_in_ha_version`**, `entity_id` (if scoped),
  `data`.
- Optional arg: `include_dismissed: bool = false` (endpoint supports ignoring/dismissed
  via `ignore_issues` filter on the UI side; default = all open).
- Skill use: filter `breaks_in_ha_version != null`, compare against the upgrade path →
  the "integrations that need a manual touch, release by release" list. Replaces skill §4's
  guesswork.
- Companion (optional): `get_repairs_issue_detail(issue_id)` → `GET /api/repairs/issue_registry/{issue_id}`
  for the full translation text.

### 2. `get_core_version`

- Endpoint: `GET /api/config` → return `version` (e.g. `2026.4.1`) + `ha_url`.
- Skill use: §1 — the **running** core version, for repo-vs-live drift detection
  (image tag `2026.4` vs actual `2026.4.1`). One call, authoritative.

### 3. `list_loaded_integrations`

- Endpoint: `GET /api/config/config_entries/entry` (upstream's `list_config_entries`
  is the same call) → return `[{domain, title, state, source}]`, de-duplicated and sorted
  by `domain`.
- Skill use: §4 — the authoritative "integrations in use" set that breaking-change triage
  is checked against. Replaces "check the config dir / ask the user."
- (Fold into existing `list_config_entries` if preferred; keep as a thin alias for clarity.)

### 4. `get_ha_log`

- Endpoint: `GET /api/log` (HA's own `home-assistant.log`, richer than container stderr).
- Args: `tail: int = 100`, `min_level: Literal["DEBUG","INFO","WARNING","ERROR"] = "WARNING"`.
- Returns: filtered log lines.
- Skill use: §6 — detect "Failed migration", exceptions, integration setup failures
  **precisely**, instead of grepping the sparse container stdout/stderr. (Complements,
  does not replace, the Nomad `DeploymentStatus.Healthy` signal.)

### 5. `validate_config`

- Endpoint: `POST /api/config/check` (empty payload → validates current config).
- Returns: `{result: "valid" | "invalid", errors: [...]}`.
- Skill use: pre-deploy gate the skill has today (optional, recommended before each cutover).

### 6. `restart_core`  *(write — gated)*

- Endpoint: `POST /api/services/homeassistant/restart`.
- Gated behind `HA_ENABLE_RESTART=true` (default off) and requires `HA_READONLY=false`.
- Skill use: apply config fixes the breaking-change gates require (e.g. MQTT `object_id`
  removal, mireds→kelvin) without a full Nomad redeploy.

## Tool-surface summary

| Group | Upstream | Fork (default read-only) |
| --- | --- | --- |
| Repairs / upgrade readiness | 0 | **4** (`get_repairs_issues`, `get_repairs_issue_detail`, `get_core_version`, `get_ha_log`) |
| Integration inventory | 2 | 2 (`list_config_entries`, `list_loaded_integrations`) |
| Config validate | 1 | 1 (`validate_config`) |
| HA log | 1 (`get_error_log`) | keep + `get_ha_log` |
| Entities / areas / devices / history / logbook | ~12 | keep |
| Automations / scripts / scenes (read) | 3 | keep |
| Input helpers (read) | 1 | keep |
| Device registry | 1 | keep |
| Write tools | ~25 | **0** (gated behind `HA_READONLY=false`) |
| Supervisor tools | ~25 | gated behind `HA_ENABLE_SUPERVISOR` (reads may work; writes fail on Container) |

## Skill integration (what changes in `home-assistant-update`)

- **§1 current version** → `get_core_version` (drop the config-dir read; keep the live
  `nomad_get_job` image-tag drift check in the skill).
- **§4 integration triage set** → `list_loaded_integrations`.
- **§4 manual-touch gate** → `get_repairs_issues`, filtered on `breaks_in_ha_version`.
- **§6 verify** → `get_ha_log(min_level="WARNING")` + the existing Nomad healthy signal.
- **New §3.5 pre-deploy** → `validate_config` before cutting over (optional).
- GitHub release list (step 2) and blog/release-notes fetch (step 4) stay as `webfetch` in the
  skill — not HA state, the server must not own them.

## Wiring into Kilo

- Add the fork as an MCP server in `kilo.json` alongside the existing `nomad` server, e.g.
  a stdio server launched with `uv run --project <fork-path> ha`, env `HA_URL` + `HA_TOKEN`
  (token loaded from the Nomad Variable by the human). `HA_READONLY` defaults true.
- In the skill, register the server's tool names the same way the `nomad` MCP tools are named,
  and reference them at the §-steps above.

## Out of scope

- Supervisor **writes** (add-on install/update, OS/supervisor/core updates, backups) — not used;
  expected to `HomeAssistantError` on Container, gated off by `HA_ENABLE_SUPERVISOR`. Supervisor
  *reads* are kept behind that flag and tested on the live instance before the skill uses them.
- Write/control features (state, services, dashboards, automations triggers) — available only
  if `HA_READONLY=false`, not used by the update skill.

## Gotchas

- `breaks_in_ha_version` is per-issue; an integration with no open repair issue has no
  guaranteed automated signal — the skill's release-note triage remains the backstop.
- The token grants full API access; default read-only + gated writes are mandatory, and the
  token must never appear in the repo.
