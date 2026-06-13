# OpenClaw on Suji

Multi-channel messaging bot with AI-powered responses. OpenClaw connects to
Telegram, Discord, WhatsApp, and Slack, and replies to incoming
messages using your choice of AI provider — Anthropic, OpenAI, Google
(Gemini), Mistral, Groq, OpenRouter, xAI, Moonshot AI, or any
OpenAI-compatible endpoint (vLLM, Ollama, LM Studio, LiteLLM, …).

This page covers everything you need to run OpenClaw on Suji: what to prepare,
how to install, how to actually connect to the Control UI for the first time,
how to wire up channels, and how to recover from the most common errors.

OpenClaw itself is maintained by [openclaw/openclaw](https://github.com/openclaw/openclaw).
Suji only publishes the marketplace packaging (compose + manifest + icon).

---

## 1. Before you install

You'll need:

- **An AI provider API key**, from one of:
  - Anthropic — [console.anthropic.com](https://console.anthropic.com)
  - OpenAI — [platform.openai.com](https://platform.openai.com)
  - Google (Gemini) — [aistudio.google.com](https://aistudio.google.com)
  - Mistral — [console.mistral.ai](https://console.mistral.ai)
  - Groq — [console.groq.com](https://console.groq.com)
  - OpenRouter — [openrouter.ai](https://openrouter.ai/keys)
  - xAI — [console.x.ai](https://console.x.ai)
  - Moonshot AI — [platform.moonshot.ai](https://platform.moonshot.ai)

  …or an **OpenAI-compatible endpoint URL** (vLLM, Ollama, LM Studio,
  LiteLLM, a gateway you run yourself, …). For those, the API key is
  optional — only set it if your endpoint requires authentication.
- **At least one channel** to respond on. **Telegram** and **Discord** are set
  up right in the install form — paste a bot token and that channel turns on.
  **WhatsApp** (QR pairing) and **Slack** (bot + app token) are connected after
  install from the Control UI / terminal (section 4). You can add channels
  incrementally.

| Channel | Set up | Where to get the credential |
|---|---|---|
| Telegram | install form | [@BotFather](https://t.me/BotFather) |
| Discord | install form | [Discord developer portal](https://discord.com/developers/applications) |
| WhatsApp | after install (QR) | scan a QR with your phone — no token |
| Slack | after install | Slack app config (bot `xoxb-…` + app `xapp-…`) |

---

## 2. Installing

In the Suji dashboard:

1. **Apps** → pick **OpenClaw** → **Install**.
2. Fill in the install form:

   | Field | Required | Notes |
   |---|---|---|
   | AI provider | yes | One of the providers above, or OpenAI-compatible for a custom endpoint. |
   | Custom endpoint base URL | only for OpenAI-compatible | e.g. `https://llm.example.com/v1`. Leave blank otherwise. |
   | AI API key | for cloud providers | Your key for the chosen provider. Stored encrypted at rest. Optional for OpenAI-compatible endpoints without auth. |
   | Model | only for OpenAI-compatible / OpenRouter / Moonshot | Model to reply with, e.g. `gpt-5.5` or `claude-sonnet-4-6`. **Leave blank to use a sensible default for your provider.** |
   | Gateway password | no | Auto-generated if you leave it blank. |
   | Telegram bot token | no | Paste it to enable Telegram; leave blank to skip. |
   | Discord bot token | no | Paste it to enable Discord; leave blank to skip. |

   The chosen provider **and a matching model** are wired into the gateway at
   install, so the bot replies as soon as it connects. (Picking a provider
   without a matching model is what used to leave installs mute.) Want a
   different model later? Change it in the Control UI (section 3) or by editing
   the install.

3. **Recommended VM size: Small (2 vCPU / 2 GB RAM / 5 GB).** Mini (1 GB) is
   borderline at idle and will OOM under any real load.
4. Click **Deploy**. The dashboard will reach "running" status in 1–2 minutes.

Once running, the dashboard shows the install with a public hostname like
`<your-subdomain>.suji.fr`. **That's your Control UI URL — but it needs two
extra setup steps the first time.** Keep reading.

---

## 3. First connection: token + device pairing

OpenClaw's gateway has two layers of access control:

- A **token** that authenticates the connecting browser.
- A **device pairing** approval that grants the browser access to operate.

Both run automatically when you access from `localhost`, but Suji exposes
OpenClaw over a Cloudflare Tunnel — so the gateway sees you as a remote
device and asks for explicit setup.

### Step A — open the tokenized URL

The gateway generates its own access token on first boot and stores it in
its config file (`openclaw.json`, under `gateway.auth.token`). To find it:

1. Dashboard → your instance → **Files**.
2. Switch the file root to the **OpenClaw install's volume** (selector at the
   top of the Files tab).
3. Open `openclaw.json`.
4. Copy the value of `gateway.auth.token`.

Then open the Control UI with the token appended:

```
https://<your-subdomain>.suji.fr/#token=<paste-token-here>
```

You should see the Control UI start to load. It will almost certainly drop
to error code 1008 — that's the next step.

### Step B — approve the device pairing (1008)

When you see this in the browser:

> `disconnected (1008): pairing required`

It means OpenClaw's gateway has created a pending pairing request for
your browser and is waiting for you to approve it.

**Leave the browser tab open**, then in the Suji dashboard:

1. **Terminal** tab → choose the **OpenClaw install** from the selector.
2. Run:

   ```bash
   openclaw devices list
   ```

   You'll see a "Pending (1)" section with a request ID like
   `e7c1d26c-3a42-413e-bf1f-0afb8d77fd9d`.
3. Approve it:

   ```bash
   openclaw devices approve <requestId>
   ```

4. Refresh the browser tab. The Control UI will now connect cleanly.

That browser is now paired permanently — you only do this once per
browser/device.

---

## 4. Connecting channels

**Telegram and Discord** turn on from the install form — paste a bot token and
OpenClaw's gateway enables that channel the moment it boots. To add or change
one later, edit the install, paste (or clear) the token, and save; OpenClaw
redeploys with the new value.

- **Telegram**: paste the [@BotFather](https://t.me/BotFather) token. Message
  your bot to confirm it replies.
- **Discord**: paste the bot token, then invite the bot to a server with the
  right scopes. The Control UI logs incoming events.

**WhatsApp and Slack** are connected after install — they don't fit a single
install-time token (WhatsApp links a phone by QR; Slack needs both a bot and an
app token). Use the **Terminal** tab (pick the OpenClaw install):

```bash
# WhatsApp — scan the printed QR with WhatsApp → Linked devices
openclaw channels login --channel whatsapp

# Slack — needs an xoxb- bot token and an xapp- app token
openclaw channels add --channel slack --bot-token xoxb-... --app-token xapp-...
```

Run `openclaw channels --help` for every supported channel and its flags. (A
first-class install-form experience for WhatsApp and Slack is planned.)

---

## 5. Managing your install

| What | Where | How |
|---|---|---|
| **View live logs** | Dashboard → Logs tab | Pick OpenClaw from the install selector |
| **Open a shell** | Dashboard → Terminal tab | Pick OpenClaw — lands as the `node` user |
| **Browse data files** | Dashboard → Files tab | Pick the OpenClaw volume — sqlite, sessions, config |
| **Edit config** | Dashboard → Files tab | Open `openclaw.json`, save (⌘+S) |
| **Restart** | Install detail page | "Restart" button |
| **Upgrade** | Install detail page | "Upgrade" appears when a new version is in the catalog |
| **Uninstall** | Install detail page | "Uninstall" — removes the container and its volume |

After editing `openclaw.json` directly, **restart the install** from the
dashboard for the change to take effect.

---

## 6. Troubleshooting

### `disconnected (1008): unauthorized: gateway token missing`

You opened the Control UI without the `#token=…` fragment in the URL.
Go back to [step A above](#step-a--open-the-tokenized-url) and rebuild the
URL with the token from `openclaw.json`.

### `disconnected (1008): pairing required`

Your browser/device isn't paired yet. Follow [step B above](#step-b--approve-the-device-pairing-1008).
Note: pairing requests are short-lived (~30 s) — list and approve while the
browser tab is still showing the error, not after closing it.

### `Bad gateway` (Cloudflare 502)

OpenClaw isn't reachable through the tunnel. Most common causes:

- **The container is still starting** — wait 30 s and retry, especially right
  after an upgrade.
- **The container has crashed** — Logs tab will show why. If it shows
  `Permission denied` on `/home/node/.openclaw`, file a Suji support ticket
  (the volume's ownership has drifted and we need to fix it server-side).

### `Permission denied` on `/home/node/.openclaw/…`

OpenClaw runs as the `node` user. If the data volume's ownership is wrong
(e.g., after some kinds of restore or manual mount changes), OpenClaw can't
write its config. Fix from the host terminal:

```bash
docker exec --user 0 $(docker ps -q -f label=com.docker.compose.project=<install-id>) \
  chown -R node:node /home/node/.openclaw
docker compose -f /etc/suji/installs/<install-id>/compose.yaml restart openclaw
```

(Fresh installs after May 2026 have this handled automatically by an
init-permissions container in the compose.)

### Mail not sending

Outbound SMTP on ports **25 and 465 is blocked by the cloud provider** at
the network layer. Allowing those ports in your Suji firewall settings
won't help — the block sits before the firewall.

Use either:
- **Port 587** with STARTTLS (which is open), or
- An HTTP-based mail relay: Resend, Postmark, SendGrid, Mailgun.

### The Control UI is fine in one browser but `1008: pairing required` in another

That's expected. Pairing is per-device. Open the new browser, hit the
tokenized URL, run `openclaw devices approve <newId>` from the terminal,
refresh.

---

## 7. Where things live

| What | Inside the container | On the host |
|---|---|---|
| State (sqlite, sessions, gateway config) | `/home/node/.openclaw` | Named volume `<install-id>_openclaw-data` |
| Logs | stdout/stderr (visible in `docker logs`) | — |
| Compose file | — | `/etc/suji/installs/<install-id>/compose.yaml` |
| Env file (rendered secrets) | injected as env vars | `/etc/suji/installs/<install-id>/.env` (`0600`) |

Volumes survive container restarts, version upgrades, and VM snapshots.
Uninstalling the app deletes the volume.

---

## 8. Recommended size and limits

- **Small VM (2 vCPU / 2 GB / 5 GB)** is the floor for stable operation.
- Memory is capped at **2048 MiB** in the compose `deploy.resources.limits`.
  Reaching that ceiling triggers an OOM kill — the container restarts but
  in-flight conversations may drop.
- CPU is capped at **1.0 vCPU**. Bursty AI inference may queue at peak load
  but won't starve the rest of the VM.

If you're running OpenClaw alongside other apps on the same VM, factor those
in — the platform caps each install independently, but they share the VM's
overall CPU/memory.

---

## 9. Getting help

| Problem area | Where to report |
|---|---|
| OpenClaw itself (bugs in the bot, wrong AI replies, channel logic) | [openclaw/openclaw issues](https://github.com/openclaw/openclaw/issues) |
| Marketplace packaging (compose / manifest / install form) | [suji-hq/suji-templates issues](https://github.com/suji-hq/suji-templates/issues) |
| Suji platform (provisioning, dashboard, billing, network) | Support ticket from your Suji dashboard |
