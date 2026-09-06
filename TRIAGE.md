# Marketplace update triage, 2026-09-06

A review of every open auto-bump PR against each app's deployment contract and
the real upstream changelog. The question asked was narrow: **what can move
without breaking how the platform integrates the app, or how customers log in?**

Nothing in the queue turned out to be contract-breaking. One item is blocked for
a different reason (release channel), and the review surfaced three live defects
that have nothing to do with any version bump.

## Verdicts

| App        | Bump                              | Auto-bump PR | Integration / login | Verdict                        |
| ---------- | --------------------------------- | ------------ | ------------------- | ------------------------------ |
| Ghost      | 6.59.0 to 6.62.0                  | #183         | unchanged           | Safe. Ship first, critical CVE |
| Crafty     | 4.10.7 to 4.10.8                  | #113         | unchanged           | Safe. Ship first, CVSS 9.1     |
| NocoDB     | 2026.08.1 to 2026.08.2            | #186         | unchanged           | Safe                           |
| Hermes     | v2026.6.19 to v2026.7.20          | #94          | auth hardened       | Safe, one caveat below         |
| n8n        | 2.35.7 to 2.38.3                  | #187         | unchanged           | **Do not merge.** Beta channel |
| Vaultwarden| already on 1.37.2                 | #160         | n/a                 | Obsolete, close                |

Replacement PRs opened by this triage: **#190** (Ghost), **#191** (Crafty),
**#192** (n8n on stable).

## Per-app detail

### Ghost 6.62.0: safe, and urgent

6.59.0 is exposed to five advisories disclosed 2026-09-03, after the releases
shipped, which is why the public release notes look cosmetic.

| Advisory             | Severity | Patched | Summary                                            |
| -------------------- | -------- | ------- | -------------------------------------------------- |
| GHSA-q734-xjgc-vpj9  | critical | 6.62.0  | Suspended staff could reactivate via password reset |
| GHSA-qppx-rw6v-xjqf  | high     | 6.62.0  | Unauthenticated checkout allowed member changes     |
| GHSA-xcgh-2828-cvmx  | medium   | 6.62.0  | Staff could accept invite with any email            |
| GHSA-rv92-9vfp-2826  | medium   | 6.62.0  | Missing authz on gated comments and excerpts        |
| GHSA-x3mg-q38v-m562  | medium   | 6.60.0  | Author role could delete any post                   |

SQLite is not deprecated in this range: `sanitizeDatabaseProperties()` is
byte-identical, and 6.61.0 actually fixes a SQLite crash. The docker-library
diff between the two builds is two lines, both `ENV GHOST_VERSION`.

### Crafty 4.10.8: safe, and urgent

Fixes CVE-2026-13716 (CVSS 9.1), a path traversal in the upload handler letting
an authenticated user write to arbitrary paths. Ports 8443/https and 25565, the
`/crafty/*` layout, and the image env are all unchanged. No migrations.

### NocoDB 2026.08.2: safe

`NC_AUTH_JWT_SECRET` handling is byte-identical (`NcConfig.ts` unchanged), so no
customer gets logged out. `NC_PUBLIC_URL` still works but is now an undocumented
legacy alias for `NC_SITE_URL`; worth switching at a later bump, not this one.
Three new migrations, all additive or widening, all with a working `down()`.
No CVE. One real fix: permissions no longer leak across duplicated bases.

Watch item: 08.2 enables Interfaces and Workflows on Community Edition, which is
new runtime load against the 1 GiB limit.

### Hermes v2026.7.20: safe, with a precedence caveat

Auth gets stronger, not weaker. `should_require_auth` was rewritten so the
legacy `--insecure` escape hatch no longer disables the gate: a non-loopback
bind always requires an auth provider, enforced with a hard `SystemExit`. The
container refuses to boot rather than serve the dashboard unauthenticated.
`_is_accepted_host` still returns `True` under a `0.0.0.0` bind, so arbitrary
`*.suji.fr` subdomains keep working. `gateway run`, port 9119 and `/opt/data`
are unchanged.

**Caveat.** v2026.7.20 adds `get_env_value_prefer_dotenv` (`hermes_cli/config.py`),
which does not exist at v2026.6.19. Provider keys now resolve from
`/opt/data/.env` **first**, falling back to `os.environ`
(`hermes_cli/auth.py:497,591`). Consequences:

- Fresh installs are unaffected; no `.env` key, so the compose var wins.
- On an existing install where the customer ever saved a key in the Hermes
  dashboard, that stored key now shadows ours, so rotating it through the Suji
  install form silently does nothing.
- The empty-string trick for disabling the two unselected providers is weaker,
  because an empty compose var no longer masks a `.env`-stored key.

Decide how to handle that before rolling out.

**Do not follow the queue past 7.20.** Every `v2026.8.x` is breaking: the image
`ENTRYPOINT` changed from `['/init', '/opt/hermes/docker/main-wrapper.sh']` to
`['/opt/hermes/docker/entrypoint-dispatch.sh']`, and upstream added an
`ALLOWED_HOSTS` check plus a `trusted_proxies` requirement that would reject the
per-install subdomain. There is correctly no PR for those, only "don't update"
issues.

### n8n: blocked on release channel, not compatibility

2.38.x is n8n's **beta** line.

| Tag                  | `prerelease` (GitHub API) |
| -------------------- | ------------------------- |
| 2.35.7 (old pin)     | `false`                   |
| 2.37.10              | `false`, current stable   |
| 2.38.1               | `true`                    |
| 2.38.3 (PR #187)     | `true`                    |

The contract itself is clean: `auth.config.ts` and `push/origin-validator.ts`
are byte-identical to 2.35.7, so cookie auth and the editor WebSocket origin
check behave identically through the tunnel. Nothing renamed, removed, or newly
required. PR #192 retargets to stable 2.37.10.

One caution for any n8n bump: it runs about 16 migrations on first start, one of
them explicitly `IrreversibleMigration`, and one rebuilds `scheduled_job` on
SQLite. A tag rollback alone will not restore a working database.

## Three defects unrelated to any bump

1. **Ghost owners were locked out on their second sign-in.** `session.js` skips
   device verification only on a user's first-ever login
   (`if (user && !user.hasLoggedIn())`); every later login emails a one-time
   code, and this template configures no SMTP. Reproduced on the live pin: three
   consecutive logins after the initial one all returned
   `500 EmailError`. Fixed in #190 with
   `security__staffDeviceVerification: "false"`, verified to return `201`.

2. **The Minecraft admin password was never in the logs.** The description told
   customers to read it from the app logs. Crafty writes it only to
   `app/config/default-creds.txt` (mode 0600) and never prints it, confirmed in
   upstream `main.py` at the pinned v4.10.7. Fixed in #191.

3. **The poller pinned prereleases and shipped stale release notes.** Both fixed
   in this PR, see below.

## Tooling fixes in this PR

**Prerelease detection.** `parse_stable()` decided stability by string-matching
`beta|rc|alpha` in the tag. n8n publishes betas as plain semver, so nothing in
the string marks them, and the prerelease flag lives in GitHub release metadata
the poller never reads. `latest_stable()` now resolves the repo's own channel
tag (`stable`, else `latest`) to a digest and returns the newest semver tag
sharing it, falling back to the old behaviour when no channel tag exists.
Probing walks newest-first and stops at the first match, capped at
`MAX_CHANNEL_PROBES`, so a repo with thousands of tags costs a few requests.

Measured effect, naive versus channel-aware:

| App         | Naive highest semver | Channel-aware  |
| ----------- | -------------------- | -------------- |
| n8n         | 2.38.3 (beta)        | **2.37.10**    |
| ghost       | 6.62.0               | 6.62.0         |
| nocodb      | 2026.08.2            | 2026.08.2      |
| vaultwarden | 1.37.2               | 1.37.2         |
| crafty      | 4.10.8               | 4.10.8         |
| hermes      | v2026.8.31           | v2026.8.31     |
| wikijs      | 2.5.314              | 2.5.314        |

Only n8n changes, which is the bug.

**Stale release notes.** `bump` rewrote `version` but left `release_notes`
alone, so PR #187 set `version: 2.38.3` while the notes still read "Update n8n
to 2.27.3 (from 2.22.2)". That text is what the upgrade dialog shows customers,
and the already-merged #163 shipped the same defect, so the live catalog is
serving wrong notes for ghost, n8n and nocodb today. `bump` now regenerates an
accurate note via `rewrite_release_notes()`.

## Queue hygiene

57 open PRs, but only six were current; the rest bump from a base main has long
passed (#151 still starts at n8n 2.27.3), which is why several are
`CONFLICTING`. Merging an old one would downgrade the pin. Recommend closing the
superseded auto-bump PRs in bulk once the replacements land.

## Limits of this review

- Nothing here was tested against a real tenant VM through the Cloudflare
  tunnel. Ghost, n8n and Crafty were boot-tested locally under the same memory
  and CPU limits; a passing local curl does not prove the browser path.
- Install counts per app version were not checked, so the blast radius of each
  bump on existing installs is unquantified.
- Hermes and NocoDB were reviewed from source and changelog only, not booted.

## Reminder

Catalog sync is `onConflictDoNothing` on `(slug, version)`. Editing a template
without bumping `manifest.version` does nothing in production.

## Sync verification, 2026-09-06

After merging, prod catalog picked up ghost 6.62.0 and minecraft-server 4.10.8
(2 new, 2 pruned at 00:07:52) but **not** n8n 2.37.10, which stayed on 2.35.7-1
despite `main` carrying the new pin. The webhook fired and returned 200 each
time, and the run logged `0 skipped`, so the template parsed cleanly; the sync
simply saw stale repo content for that app. If this recurs, check
`app_template_versions` after a bump rather than trusting the webhook's 200.
