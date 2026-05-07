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

Once merged, the app appears in the marketplace within a few minutes.

## License

Manifests in this repo are MIT. Each app keeps its own license — we just describe how to install it.
