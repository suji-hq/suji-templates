# Suji Templates

The catalog of apps you can install on [Suji](https://suji.fr) in one click.

Each folder is one app: a compose file, a short manifest, and a logo. Browse them, install them on your VM, or add new ones.

## Add an app

1. Pick an app whose docker image is publicly available on Docker Hub or GHCR.
2. Copy any folder here as a starting point — `n8n/` is a good simple example.
3. Rename it to your app's slug (lowercase, hyphenated).
4. Edit the three files, open a PR.

A folder needs:

```
your-app/
├── compose.yaml    # docker compose, with a pinned image tag
├── manifest.yaml   # name, description, install form
└── icon.svg        # square, ideally 256×256
```

### `compose.yaml`

A normal docker-compose file with two rules:

- **Pin the image tag.** No `:latest` — installs need to be reproducible.
- **Join `suji-net`** — the bridge Suji wires up at provision time:

  ```yaml
  networks: [suji-net]
  ...
  networks:
    suji-net:
      external: true
  ```

Use `${VAR}` for anything the user fills in. Those variables come from `manifest.yaml`'s `form_schema`.

### `manifest.yaml`

The fields that matter most:

- `slug` — must match the folder name.
- `name`, `description` — what shows up in the marketplace.
- `version` — must match the image tag.
- `categories` — pick from: `automation`, `productivity`, `developer-tools`, `analytics`, `monitoring`, `database`, `cms`, `communication`, `security`, `storage`.
- `exposure.exposable` — whether the app gets a public subdomain.
- `form_schema` — the form users fill in before deploying. Field types: `text`, `select`, `multiselect`, `secret`. Use `auto_generate: true` on a secret to have Suji fill it in.

`openclaw/manifest.yaml` shows the full shape.

### `icon.svg`

Square SVG, no padding, transparent background. Tools like [tabler.io/icons](https://tabler.io/icons) or [simpleicons.org](https://simpleicons.org) work great as starting points if your app doesn't have its own logo handy.

## Open a PR

We review for:

- The image actually exists and pulls anonymously.
- The compose file is sane (no host-mounted secrets, no `privileged: true`, no `network_mode: host`).
- The manifest's form makes sense — secrets are marked as secrets, required fields are required.

Once merged, the marketplace updates within seconds (push webhook), or at most 6 hours later (fallback cron).

## Automated checks

CI lives in `.github/workflows/` and is driven by `scripts/marketplace_ci.py`
(pure Python + the `docker` CLI — no dependency on the Suji platform repo).

- **Validate templates** runs on every PR that touches a `manifest.yaml` /
  `compose.yaml`. It lints the contract (slug, version↔tag match, `${VAR}`
  coverage, `exposure.port` published, form-field shape), diffs the **form &
  exposure contract** against the base branch (a renamed/removed form key or a
  moved `exposure.port` breaks existing installs → fails the check), diffs the
  **image contract** (user / workdir / entrypoint / exposed ports) against the
  pinned image, and **boots the app** to confirm the exposed port serves. The
  verdict (`SAFE` / `NEEDS_REVIEW` / `BREAKING`) is posted as a PR comment;
  `BREAKING` fails the check.

- **Upstream release analysis** answers "can we move to the new version without
  impact?" Trigger it three ways:
  - **Webhook** — `POST` a `repository_dispatch`:
    `{"event_type":"upstream-release","client_payload":{"app":"openclaw","version":"2026.3.1"}}`
    (omit `version` to take the newest stable registry tag).
  - **Manually** — Actions → *Upstream release analysis* → Run workflow (app + optional version).
  - **Nightly** — a cron polls every app for a newer stable tag.

  It bumps a copy of the template to the candidate tag, runs the same analysis,
  then: **SAFE** → opens an auto-bump PR (which re-runs the validate gate);
  **NEEDS_REVIEW / BREAKING** → opens an issue with the report. It never bumps a
  live template on its own.

### Reading the image's code (the part `curl` can't see)

`curl 200` proves the app serves, but not that an in-code browser-origin / CORS /
trusted-host check will accept the per-install `https://<sub>.suji.fr` (such a
check returns 200 to curl but rejects the real browser — this is what bit
OpenClaw at upstream v2026.2.26). So the analyzer also **reads the image's
filesystem**: it diffs both versions for security/behavior identifiers
(`allowedOrigins`, `ALLOWED_HOSTS`, `CORS`, `dangerouslyAllow`, …) and flags ones
newly present in the new image, and it extracts the image's `CHANGELOG.md` section
between the two versions.

An optional **LLM pass** then judges that diff + changelog against our deployment
shape (reverse-proxied, one subdomain per install, behind token auth) and returns
a `safe` / `needs_review` / `breaking` verdict with reasons. It runs via OpenRouter
(`deepseek/deepseek-v4-flash` by default; override with `CI_LLM_MODEL`) using a
plain HTTPS call — no SDK, still pure stdlib. Add an **`OPENROUTER_API_KEY`** repo
secret to enable it; without the secret the LLM pass is skipped and the code-signal
diff alone gates as `NEEDS_REVIEW`. When the LLM judges a flagged change `safe` in
context, the code-signal findings are demoted to non-blocking notes. A `breaking`
verdict escalates to `BREAKING`; the analyzer never auto-clears a hard finding
(form/exposure regression, boot failure) on the LLM's say-so.

The poll is a best-effort detector and doesn't track per-app tag variants
(e.g. `-alpine`); always sanity-check the candidate tag in the PR/issue.

  The pipeline works as-is: it pushes the auto-bump branch and, if the org
  disallows Actions-created PRs, posts an issue with a one-click compare link.
  For *fully* automatic PRs (no human click), an org owner enables
  Settings → Actions → General → "Allow GitHub Actions to create and approve
  pull requests" (org-level here), or add a PAT secret for the PR step.

## License

Manifests in this repo are MIT. Each app keeps its own license — we just describe how to install it.
