#!/usr/bin/env python3
"""Marketplace template CI — breaking-change analysis for app version bumps.

Each app folder here is a contract: the `manifest.yaml` form-field keys are the
`${VAR}` substitution names in `compose.yaml`, `exposure.port` is the tunnel
route, and the image tag must match `manifest.version`. The Suji platform
ingests these with a strict validator and renders them onto customer VMs.

A version bump that only changes the image tag is "safe" only if the NEW image
still satisfies our UNCHANGED compose/manifest contract. So the core analysis is
an **image-contract diff + a real boot test**, plus a manifest/compose lint and
(for human-edited PRs) a form/exposure contract diff against the base branch.

Subcommands:
  poll      For each app, find the newest stable upstream tag and print a JSON
            matrix of the apps whose pinned version is behind. (schedule trigger)
  analyze   Decide whether an app can move to a candidate version:
            SAFE | NEEDS_REVIEW | BREAKING. Writes a markdown report and a
            machine-readable verdict. (release-webhook + PR triggers)

Pure stdlib + the `docker` CLI. No dependency on the private Suji monorepo.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── tiny YAML reader ─────────────────────────────────────────────────────────
# The CI runner may not have PyYAML. Try it; fall back to a minimal loader that
# covers the subset our manifests/compose use (maps, lists, scalars, inline
# {k: v} / [a, b]). The full strict parse happens server-side in the platform;
# here we only need enough structure to lint the contract.
try:
    import yaml  # type: ignore

    def load_yaml(text: str):
        return yaml.safe_load(text)
except Exception:  # pragma: no cover - fallback path
    def load_yaml(text: str):
        return _mini_yaml(text)


def _coerce_scalar(s: str):
    s = s.strip()
    if s == "" or s in ("null", "~"):
        return None
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if (s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'"):
        return s[1:-1]
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    return s


def _parse_inline(s: str):
    s = s.strip()
    if s.startswith("{") and s.endswith("}"):
        out = {}
        body = s[1:-1].strip()
        if body:
            for part in _split_top(body):
                k, _, v = part.partition(":")
                out[k.strip()] = _coerce_scalar(v)
        return out
    if s.startswith("[") and s.endswith("]"):
        body = s[1:-1].strip()
        return [_coerce_scalar(p) for p in _split_top(body)] if body else []
    return _coerce_scalar(s)


def _split_top(body: str):
    parts, depth, cur = [], 0, ""
    for ch in body:
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def _mini_yaml(text: str):
    """Indentation-based loader for the manifest/compose subset."""
    lines = [ln.rstrip() for ln in text.splitlines()
             if ln.strip() and not ln.lstrip().startswith("#")]
    root: dict = {}
    # stack of (indent, container)
    stack = [(-1, root)]

    def container_for(indent):
        while stack and stack[-1][0] >= indent:
            stack.pop()
        return stack[-1][1]

    i = 0
    while i < len(lines):
        raw = lines[i]
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        parent = container_for(indent)
        if line.startswith("- "):
            item = line[2:].strip()
            if not isinstance(parent, list):
                # shouldn't happen given well-formed input
                i += 1
                continue
            if ":" in item and not (item.startswith("{") or item.startswith("[")):
                # list of maps spread over following lines starting here
                d = {}
                k, _, v = item.partition(":")
                d[k.strip()] = _parse_inline(v) if v.strip() else None
                parent.append(d)
                stack.append((indent, d))
            else:
                parent.append(_parse_inline(item))
        else:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val == "":
                # could be a map or a list; peek next line
                nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
                child = [] if nxt.startswith("- ") else {}
                if isinstance(parent, dict):
                    parent[key] = child
                stack.append((indent, child))
            else:
                if isinstance(parent, dict):
                    parent[key] = _parse_inline(val)
        i += 1
    return root


# ── data model ───────────────────────────────────────────────────────────────
@dataclass
class Finding:
    level: str   # "error" (breaking) | "warn" (needs review) | "info"
    code: str
    message: str


@dataclass
class Report:
    app: str
    current_version: str | None = None
    candidate_version: str | None = None
    findings: list[Finding] = field(default_factory=list)
    contract_diff: list[str] = field(default_factory=list)
    boot: dict | None = None

    def add(self, level, code, message):
        self.findings.append(Finding(level, code, message))

    @property
    def verdict(self) -> str:
        if any(f.level == "error" for f in self.findings):
            return "BREAKING"
        if any(f.level == "warn" for f in self.findings):
            return "NEEDS_REVIEW"
        return "SAFE"


# ── template loading ─────────────────────────────────────────────────────────
SEMVER_RE = re.compile(r"^v?\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?$")
FORM_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
VAR_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")
# Names the platform injects at deploy time (only when exposed) — not form keys.
PLATFORM_VARS = {"SUJI_PUBLIC_HOST", "SUJI_PUBLIC_URL", "SUJI_PUBLIC_PROTOCOL"}


def app_dir(app: str) -> Path:
    return REPO_ROOT / app


def load_template(app: str, *, manifest_text=None, compose_text=None):
    d = app_dir(app)
    if manifest_text is None:
        manifest_text = (d / "manifest.yaml").read_text()
    if compose_text is None:
        compose_text = (d / "compose.yaml").read_text()
    manifest = load_yaml(manifest_text) or {}
    compose = load_yaml(compose_text) or {}
    return manifest, compose, compose_text


def git_show(ref: str, path: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"{ref}:{path}"], cwd=REPO_ROOT, text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None


def primary_service(manifest: dict, compose: dict):
    """The service that publishes exposure.port (the one the tunnel routes to).
    Falls back to the service whose name matches the slug, else the first."""
    services = (compose or {}).get("services", {}) or {}
    port = (manifest.get("exposure") or {}).get("port")
    if port is not None:
        for name, svc in services.items():
            for p in (svc or {}).get("ports", []) or []:
                if str(p).split(":")[-1].strip().strip('"') == str(port):
                    return name, svc
    if manifest.get("slug") in services:
        return manifest["slug"], services[manifest["slug"]]
    if services:
        n = next(iter(services))
        return n, services[n]
    return None, None


def image_ref_parts(image: str):
    """('ghcr.io/openclaw/openclaw', '2026.3.1') from a pinned image string."""
    repo, _, tag = image.partition(":")
    return repo, (tag or None)


# ── registry tag listing ─────────────────────────────────────────────────────
def _http_json(url: str, headers: dict | None = None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def registry_tags(repo: str) -> list[str]:
    """List tags for ghcr.io/<ns>/<img> or docker.io/<ns>/<img> anonymously."""
    if repo.startswith("ghcr.io/"):
        name = repo[len("ghcr.io/"):]
        tok = _http_json(
            f"https://ghcr.io/token?scope=repository:{name}:pull&service=ghcr.io"
        )["token"]
        data = _http_json(
            f"https://ghcr.io/v2/{name}/tags/list",
            {"Authorization": f"Bearer {tok}"},
        )
        return data.get("tags", []) or []
    if repo.startswith("docker.io/"):
        name = repo[len("docker.io/"):]
        if "/" not in name:
            name = "library/" + name
        tok = _http_json(
            "https://auth.docker.io/token?service=registry.docker.io"
            f"&scope=repository:{name}:pull"
        )["token"]
        data = _http_json(
            f"https://registry-1.docker.io/v2/{name}/tags/list",
            {"Authorization": f"Bearer {tok}"},
        )
        return data.get("tags", []) or []
    raise ValueError(f"unsupported registry for {repo}")


def parse_stable(tag: str):
    """Return a sort key for a stable release tag, or None if it's not one
    (arch-suffixed, prerelease, or non-semver)."""
    if tag.endswith(("-amd64", "-arm64")) or re.search(r"(beta|rc|alpha)", tag):
        return None
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:-(\d+))?", tag)
    if not m:
        return None
    return tuple(int(x) for x in (m.group(1), m.group(2), m.group(3), m.group(4) or 0))


def latest_stable(tags: list[str]) -> str | None:
    ranked = [(parse_stable(t), t) for t in tags]
    ranked = [(k, t) for k, t in ranked if k is not None]
    if not ranked:
        return None
    ranked.sort(key=lambda kt: kt[0])
    return ranked[-1][1]


# ── docker image contract ─────────────────────────────────────────────────────
CONTRACT_FMT = (
    "{{json .Config.User}}|{{json .Config.WorkingDir}}|{{json .Config.Entrypoint}}"
    "|{{json .Config.Cmd}}|{{json .Config.ExposedPorts}}|{{json .Config.Volumes}}"
    "|{{json .Config.Healthcheck}}"
)


def docker(*args, timeout=600, check=True):
    return subprocess.run(["docker", *args], text=True, capture_output=True,
                          timeout=timeout, check=check)


def image_contract(image: str) -> dict:
    docker("pull", "-q", image, timeout=600)
    out = docker("image", "inspect", image, "--format", CONTRACT_FMT).stdout.strip()
    user, wd, ep, cmd, ports, vols, hc = out.split("|")
    j = lambda s: json.loads(s) if s and s != "null" else None
    return {
        "user": j(user), "workdir": j(wd), "entrypoint": j(ep), "cmd": j(cmd),
        "exposed_ports": sorted((j(ports) or {}).keys()),
        "volumes": sorted((j(vols) or {}).keys()),
        "healthcheck": bool(j(hc)),
    }


def diff_contract(old: dict, new: dict, report: Report):
    """Compare two image contracts; high-risk drift → error, else warn/info."""
    def entry_file(c):
        # The script/subcommand a compose `command:` override or init step would
        # reference. Skip the interpreter (cmd[0]) and any leading flags so a
        # benign added flag (e.g. node --no-deprecation) isn't mistaken for an
        # entry change; the entry is the first non-flag argument.
        cmd = c.get("cmd") or []
        for tok in cmd[1:]:
            if isinstance(tok, str) and not tok.startswith("-"):
                return tok
        return None

    if old["user"] != new["user"]:
        report.add("error", "image.user",
                   f"image User changed {old['user']!r} → {new['user']!r}: a uid "
                   "change breaks ownership of existing named volumes.")
        report.contract_diff.append(f"User: {old['user']} → {new['user']}")
    if old["workdir"] != new["workdir"]:
        report.add("warn", "image.workdir",
                   f"WorkingDir changed {old['workdir']!r} → {new['workdir']!r}: "
                   "any compose command using a relative path may break.")
        report.contract_diff.append(f"WorkingDir: {old['workdir']} → {new['workdir']}")
    if entry_file(old) != entry_file(new):
        report.add("warn", "image.entry",
                   f"default entry file changed {entry_file(old)!r} → "
                   f"{entry_file(new)!r}: verify any `command:` overrides / init "
                   "steps still reference a path that exists in the new image.")
        report.contract_diff.append(
            f"entry: {entry_file(old)} → {entry_file(new)}")
    removed_ports = set(old["exposed_ports"]) - set(new["exposed_ports"])
    if removed_ports:
        report.add("error", "image.ports",
                   f"image stopped EXPOSEing {sorted(removed_ports)}: if exposure."
                   "port relied on it the tunnel route breaks.")
        report.contract_diff.append(
            f"exposed_ports: {old['exposed_ports']} → {new['exposed_ports']}")
    if old["entrypoint"] != new["entrypoint"]:
        report.add("warn", "image.entrypoint",
                   f"ENTRYPOINT changed {old['entrypoint']!r} → "
                   f"{new['entrypoint']!r}.")
        report.contract_diff.append(
            f"entrypoint: {old['entrypoint']} → {new['entrypoint']}")
    if not report.contract_diff:
        report.contract_diff.append("no contract drift in user/workdir/cmd/ports")


# ── manifest / compose lint (the skill's invariants) ──────────────────────────
def lint_template(manifest: dict, compose: dict, compose_text: str,
                  app: str, report: Report):
    slug = manifest.get("slug")
    if slug != app:
        report.add("error", "slug", f"slug {slug!r} != folder name {app!r}")

    version = manifest.get("version")
    if not version or not SEMVER_RE.match(str(version)):
        report.add("error", "version", f"version {version!r} is not vX.Y.Z[-rev]")

    _, svc = primary_service(manifest, compose)
    pinned_tag = None
    if svc:
        _, pinned_tag = image_ref_parts(str(svc.get("image", "")))
        if pinned_tag in (None, "latest", "main"):
            report.add("error", "image.tag",
                       f"primary image must pin an immutable tag, got {pinned_tag!r}")
        elif version and pinned_tag != str(version):
            report.add("error", "version.match",
                       f"manifest.version {version!r} != image tag {pinned_tag!r}")

    # form field shape
    form = manifest.get("form_schema") or []
    keys = []
    for fld in form:
        if not isinstance(fld, dict):
            continue
        k = fld.get("key")
        keys.append(k)
        if not (isinstance(k, str) and FORM_KEY_RE.match(k)):
            report.add("error", "form.key", f"form key {k!r} must match [A-Z][A-Z0-9_]*")
        if fld.get("type") in ("select", "multiselect"):
            opts = {o.get("value") for o in (fld.get("options") or []) if isinstance(o, dict)}
            dflt = fld.get("default")
            if dflt is not None:
                bad = ([dflt] if not isinstance(dflt, list) else dflt)
                missing = [d for d in bad if d not in opts]
                if missing:
                    report.add("error", "form.default",
                               f"{k}: default {missing} not in options {sorted(opts)}")
    if len(keys) != len(set(keys)):
        report.add("error", "form.dup", "duplicate form field keys")

    # every ${VAR} in compose must be a form key, a platform var, or an
    # auto_generate secret.
    auto_keys = {f.get("key") for f in form if isinstance(f, dict) and f.get("auto_generate")}
    declared = set(keys) | PLATFORM_VARS | auto_keys
    refs = set(VAR_RE.findall(compose_text))
    undeclared = sorted(refs - declared)
    if undeclared:
        report.add("error", "compose.var",
                   f"compose references undeclared vars {undeclared} "
                   "(add a form field, or give it a default)")

    # exposure.port must be published by a compose service
    exposure = manifest.get("exposure") or {}
    if exposure.get("exposable"):
        port = exposure.get("port")
        published = set()
        for s in (compose.get("services") or {}).values():
            for p in (s or {}).get("ports", []) or []:
                published.add(str(p).split(":")[-1].strip().strip('"'))
        if str(port) not in published:
            report.add("error", "exposure.port",
                       f"exposure.port {port} is not published by any service "
                       f"(published: {sorted(published)})")

    # registry allowlist must cover every image
    allow = manifest.get("registry") or []
    for sname, s in (compose.get("services") or {}).items():
        img = str((s or {}).get("image", ""))
        if img and not any(img == a or img.startswith(a + "/") or
                           img.startswith(a.split("/")[0] + "/") for a in allow):
            # loose check: registry domain must appear in an allow entry
            dom = img.split("/")[0]
            if not any(a == dom or a.startswith(dom) for a in allow):
                report.add("warn", "registry",
                           f"service {sname} image {img!r} registry not in "
                           f"allowlist {allow}")


def diff_form_contract(base_manifest: dict, head_manifest: dict, report: Report):
    """Catch the changes that break EXISTING installs (their stored config is
    keyed by field key; their host port is allocated against exposure.port)."""
    def by_key(m):
        return {f["key"]: f for f in (m.get("form_schema") or [])
                if isinstance(f, dict) and "key" in f}

    base, head = by_key(base_manifest), by_key(head_manifest)
    for k, bf in base.items():
        if k not in head:
            report.add("error", "form.removed",
                       f"form key {k!r} was removed/renamed — existing installs "
                       "store config under this key and will fail to re-render")
            continue
        hf = head[k]
        if bf.get("type") != hf.get("type"):
            report.add("error", "form.type",
                       f"form key {k!r} type changed {bf.get('type')} → "
                       f"{hf.get('type')} — breaks installs that saved the old type")
        if hf.get("required") and not bf.get("required") and hf.get("default") is None:
            report.add("error", "form.required",
                       f"form key {k!r} became required with no default — existing "
                       "installs without it fail validation")

    be = (base_manifest.get("exposure") or {})
    he = (head_manifest.get("exposure") or {})
    if be.get("port") is not None and be.get("port") != he.get("port"):
        report.add("error", "exposure.port.changed",
                   f"exposure.port changed {be.get('port')} → {he.get('port')} — "
                   "existing installs allocated a host port against the old value")
    if be.get("scheme", "http") != he.get("scheme", "http"):
        report.add("warn", "exposure.scheme",
                   f"exposure.scheme changed {be.get('scheme','http')} → "
                   f"{he.get('scheme','http')} — tunnel origin (noTLSVerify) flips")


# ── boot test ─────────────────────────────────────────────────────────────────
def render_for_boot(manifest: dict, compose_text: str):
    """Fill form vars with defaults/dummies + map the exposed port to the host."""
    env = {}
    for f in manifest.get("form_schema") or []:
        if not isinstance(f, dict):
            continue
        k, t = f.get("key"), f.get("type")
        if "default" in f and f["default"] is not None:
            v = f["default"]
            env[k] = ",".join(v) if isinstance(v, list) else str(v)
        elif t == "select":
            opts = f.get("options") or [{}]
            env[k] = str((opts[0] or {}).get("value", "x"))
        elif t == "multiselect":
            opts = f.get("options") or [{}]
            env[k] = str((opts[0] or {}).get("value", "x"))
        elif t == "number":
            env[k] = "1"
        else:  # text / secret
            env[k] = f"citest-{(k or 'v').lower()}"
    port = (manifest.get("exposure") or {}).get("port")
    rendered = compose_text
    if port is not None:
        rendered = re.sub(rf'(- )"{port}"', rf'\1"{port}:{port}"', rendered)
    return rendered, env, port


def boot_test(app: str, manifest: dict, compose_text: str, report: Report):
    rendered, env, port = render_for_boot(manifest, compose_text)
    work = Path("/tmp") / f"ci-boot-{app}"
    subprocess.run(["rm", "-rf", str(work)], check=False)
    work.mkdir(parents=True, exist_ok=True)
    (work / "compose.yaml").write_text(rendered)
    (work / ".env").write_text("".join(f"{k}={v}\n" for k, v in env.items()))
    proj = f"ciboot{app}".replace("-", "")

    def compose_cmd(*a):
        return ["docker", "compose", "-p", proj, "--env-file", str(work / ".env"),
                "-f", str(work / "compose.yaml"), *a]

    subprocess.run(["docker", "network", "create", "suji-net"],
                   capture_output=True, check=False)
    try:
        up = subprocess.run(compose_cmd("up", "-d"), capture_output=True,
                            text=True, timeout=600)
        if up.returncode != 0:
            report.add("error", "boot.up",
                       "`docker compose up` failed:\n" + (up.stderr or "")[-800:])
            report.boot = {"ok": False, "stage": "up"}
            return
        code = None
        if port is not None:
            for _ in range(90):
                r = subprocess.run(
                    ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                     "--max-time", "3", f"http://localhost:{port}/"],
                    capture_output=True, text=True)
                code = r.stdout.strip()
                if code and code[0] in "23" or code == "401":
                    break
                time.sleep(1)
            ok = bool(code) and (code[0] in "23" or code == "401")
            report.boot = {"ok": ok, "http_code": code, "port": port}
            if not ok:
                logs = subprocess.run(compose_cmd("logs", "--tail", "30"),
                                      capture_output=True, text=True).stdout[-1200:]
                report.add("error", "boot.serve",
                           f"exposed port {port} never returned a usable response "
                           f"(last={code!r}). Logs:\n{logs}")
            else:
                report.add("info", "boot.serve",
                           f"exposed port {port} returned HTTP {code}")
                if manifest.get("exposure", {}).get("exposable"):
                    # Non-gating NOTE, not a warn: a clean bump doesn't *introduce*
                    # an origin problem, and gating here would make every web app
                    # permanently NEEDS_REVIEW (the SAFE auto-bump could never fire).
                    # The reminder still rides in the PR/issue so a human confirms
                    # at merge time. (Real origin regressions usually also move the
                    # image contract — e.g. OpenClaw 2026.3.1 — which IS gated.)
                    report.add("note", "boot.origin",
                               "This app has a public web UI: curl 200 confirms it "
                               "serves, but not that a browser-origin/CORS check will "
                               "accept the per-install https://<sub>.suji.fr. Before "
                               "merging, confirm the new version didn't change its "
                               "origin policy (see OpenClaw 2026.3.1 init-config).")
        else:
            report.boot = {"ok": True, "http_code": None}
            report.add("info", "boot.serve", "no exposed port; container came up")
    finally:
        subprocess.run(compose_cmd("down", "-v"), capture_output=True, check=False)


# ── report rendering ──────────────────────────────────────────────────────────
EMOJI = {"SAFE": "✅", "NEEDS_REVIEW": "⚠️", "BREAKING": "🛑"}


def render_markdown(r: Report) -> str:
    out = [f"## {EMOJI[r.verdict]} `{r.app}` — **{r.verdict}**", ""]
    if r.current_version or r.candidate_version:
        out.append(f"`{r.current_version}` → `{r.candidate_version}`\n")
    errs = [f for f in r.findings if f.level == "error"]
    warns = [f for f in r.findings if f.level == "warn"]
    notes = [f for f in r.findings if f.level == "note"]
    infos = [f for f in r.findings if f.level == "info"]
    if errs:
        out.append("### 🛑 Breaking")
        out += [f"- **{f.code}** — {f.message}" for f in errs] + [""]
    if warns:
        out.append("### ⚠️ Needs review")
        out += [f"- **{f.code}** — {f.message}" for f in warns] + [""]
    if notes:
        out.append("### 📌 Before merging (non-blocking)")
        out += [f"- {f.message}" for f in notes] + [""]
    if r.contract_diff:
        out.append("### Image contract diff")
        out += [f"- {d}" for d in r.contract_diff] + [""]
    if r.boot:
        b = r.boot
        out.append(f"### Boot test\n- result: {'pass' if b.get('ok') else 'FAIL'}"
                   f" (HTTP {b.get('http_code')})\n")
    if infos:
        out += ["<details><summary>info</summary>", ""]
        out += [f"- {f.code}: {f.message}" for f in infos] + ["", "</details>"]
    return "\n".join(out)


def emit_outputs(r: Report, markdown: str):
    """Write GitHub Actions outputs + step summary when running in CI."""
    gho = os.environ.get("GITHUB_OUTPUT")
    if gho:
        with open(gho, "a") as fh:
            fh.write(f"verdict={r.verdict}\n")
            fh.write(f"app={r.app}\n")
            fh.write(f"candidate={r.candidate_version or ''}\n")
            fh.write(f"current={r.current_version or ''}\n")
    gss = os.environ.get("GITHUB_STEP_SUMMARY")
    if gss:
        with open(gss, "a") as fh:
            fh.write(markdown + "\n")
    rep_path = os.environ.get("CI_REPORT_PATH")
    if rep_path:
        Path(rep_path).write_text(markdown)


# ── subcommands ───────────────────────────────────────────────────────────────
def cmd_poll(args):
    """Emit a JSON matrix of apps whose pinned version is behind upstream."""
    apps = args.apps or [p.name for p in REPO_ROOT.iterdir()
                         if (p / "manifest.yaml").exists()]
    behind = []
    for app in sorted(apps):
        try:
            manifest, compose, _ = load_template(app)
            _, svc = primary_service(manifest, compose)
            repo, tag = image_ref_parts(str((svc or {}).get("image", "")))
            latest = latest_stable(registry_tags(repo))
            if latest and tag and parse_stable(latest) and (
                not parse_stable(tag) or parse_stable(latest) > parse_stable(tag)
            ):
                behind.append({"app": app, "current": tag, "candidate": latest})
                print(f"  {app}: {tag} → {latest} (behind)", file=sys.stderr)
            else:
                print(f"  {app}: {tag} (up to date; latest={latest})", file=sys.stderr)
        except Exception as e:  # don't let one app break the poll
            print(f"  {app}: poll error: {e}", file=sys.stderr)
    matrix = {"include": behind}
    print(json.dumps(matrix))
    gho = os.environ.get("GITHUB_OUTPUT")
    if gho:
        with open(gho, "a") as fh:
            fh.write(f"matrix={json.dumps(matrix)}\n")
            fh.write(f"any={'true' if behind else 'false'}\n")
    return 0


def cmd_analyze(args):
    app = args.app
    base_ref = args.base  # branch to diff the form/exposure contract against

    if args.from_worktree:
        # PR mode: analyze the working-tree template as-is.
        manifest, compose, compose_text = load_template(app)
        report = Report(app=app)
        report.candidate_version = str(manifest.get("version"))
        # form/exposure contract diff vs base branch (catches human edits)
        if base_ref:
            bm = git_show(base_ref, f"{app}/manifest.yaml")
            if bm:
                base_manifest = load_yaml(bm) or {}
                report.current_version = str(base_manifest.get("version"))
                diff_form_contract(base_manifest, manifest, report)
    else:
        # Release mode: propose bumping the on-`main` template's image tag to the
        # candidate version, then analyze the proposed result.
        base_ref = base_ref or "HEAD"
        mtext = git_show(base_ref, f"{app}/manifest.yaml")
        ctext = git_show(base_ref, f"{app}/compose.yaml")
        if mtext is None or ctext is None:
            mtext = (app_dir(app) / "manifest.yaml").read_text()
            ctext = (app_dir(app) / "compose.yaml").read_text()
        base_manifest = load_yaml(mtext) or {}
        base_compose = load_yaml(ctext) or {}
        _, svc = primary_service(base_manifest, base_compose)
        repo, cur_tag = image_ref_parts(str((svc or {}).get("image", "")))
        candidate = args.version or latest_stable(registry_tags(repo))
        report = Report(app=app, current_version=cur_tag, candidate_version=candidate)
        if not candidate:
            report.add("error", "no.candidate", "could not resolve a candidate version")
            _finish(report); return 0
        if cur_tag and parse_stable(candidate) and parse_stable(cur_tag) and \
                parse_stable(candidate) <= parse_stable(cur_tag):
            report.add("warn", "not.newer",
                       f"candidate {candidate} is not newer than pinned {cur_tag}")
        # Build the proposed template: bump every ref to the primary repo + version.
        compose_text = re.sub(re.escape(repo) + r":[^\s\"']+", f"{repo}:{candidate}", ctext)
        manifest = base_manifest
        manifest["version"] = candidate
        compose = load_yaml(compose_text) or {}

    # Common: lint + image-contract diff + boot test on the (proposed) template.
    lint_template(manifest, compose, compose_text, app, report)

    try:
        _, svc = primary_service(manifest, compose)
        new_repo, new_tag = image_ref_parts(str((svc or {}).get("image", "")))
        new_contract = image_contract(f"{new_repo}:{new_tag}")
        if report.current_version and report.current_version != new_tag:
            old_contract = image_contract(f"{new_repo}:{report.current_version}")
            diff_contract(old_contract, new_contract, report)
    except Exception as e:
        report.add("warn", "contract.skip", f"image contract diff skipped: {e}")

    if not args.no_boot:
        try:
            boot_test(app, manifest, compose_text, report)
        except Exception as e:
            report.add("warn", "boot.skip", f"boot test skipped: {e}")

    _finish(report)
    # Non-zero exit on BREAKING so a PR check fails loudly.
    return 1 if (args.fail_on_breaking and report.verdict == "BREAKING") else 0


def _finish(report: Report):
    md = render_markdown(report)
    print(md)
    emit_outputs(report, md)


def cmd_bump(args):
    """Rewrite an app's compose image tags + manifest.version to a new version.
    Used by the auto-bump PR job after a SAFE verdict."""
    app = args.app
    d = app_dir(app)
    manifest, compose, compose_text = load_template(app)
    _, svc = primary_service(manifest, compose)
    repo, old_tag = image_ref_parts(str((svc or {}).get("image", "")))
    new = args.version
    # Bump every reference to the primary image repo (covers init + main services).
    new_compose = re.sub(re.escape(repo) + r":[^\s\"']+", f"{repo}:{new}", compose_text)
    (d / "compose.yaml").write_text(new_compose)
    mtext = (d / "manifest.yaml").read_text()
    mtext = re.sub(r"^version:\s*.*$", f"version: {new}", mtext, count=1, flags=re.M)
    (d / "manifest.yaml").write_text(mtext)
    print(f"bumped {app}: {old_tag} -> {new}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("poll", help="find apps behind their upstream latest")
    p.add_argument("--apps", nargs="*", help="limit to these app slugs")
    p.set_defaults(func=cmd_poll)

    a = sub.add_parser("analyze", help="SAFE/NEEDS_REVIEW/BREAKING for a bump")
    a.add_argument("app", help="app slug (folder name)")
    a.add_argument("--version", help="candidate version (default: upstream latest)")
    a.add_argument("--base", help="git ref to diff the contract against (default HEAD)")
    a.add_argument("--from-worktree", action="store_true",
                   help="PR mode: analyze the working-tree template as edited")
    a.add_argument("--no-boot", action="store_true", help="skip the docker boot test")
    a.add_argument("--fail-on-breaking", action="store_true",
                   help="exit non-zero when the verdict is BREAKING")
    a.set_defaults(func=cmd_analyze)

    b = sub.add_parser("bump", help="rewrite an app's image tags + manifest version")
    b.add_argument("app", help="app slug (folder name)")
    b.add_argument("--version", required=True, help="new version / image tag")
    b.set_defaults(func=cmd_bump)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
