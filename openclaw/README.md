# OpenClaw on Suji

Multi-channel messaging bot with AI-powered responses. OpenClaw connects to
Telegram, Discord, WhatsApp Cloud API, and Slack, and replies to incoming
messages using your choice of AI provider (Anthropic Claude or OpenAI GPT).

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
- **At least one channel token** for the messaging platforms you want OpenClaw
  to respond on. You can wire up channels incrementally — start with one and
  add the rest later by editing the install.

| Channel | Where to get the token |
|---|---|
| Telegram | [@BotFather](https://t.me/BotFather) |
| Discord | [Discord developer portal](https://discord.com/developers/applications) |
| WhatsApp | Meta Business (Cloud API) |
| Slack | Your Slack app's config page |

---

## 2. Installing

In the Suji dashboard:

1. **Apps** → pick **OpenClaw** → **Install**.
2. Fill in the install form:

   | Field | Required | Notes |
   |---|---|---|
   | AI provider | yes | Anthropic (Claude) or OpenAI (GPT). |
   | AI API key | yes | Your key for the chosen provider. Stored encrypted at rest. |
   | Gateway password | no | Auto-generated if you leave it blank. |
   | Channels | yes | Pick one or more of Telegram / Discord / WhatsApp / Slack. |
   | Per-channel tokens | only for the channels you select | See the table above. |

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

After the Control UI is up:

- **Telegram**: paste the bot token from BotFather into the channel form on
  install. OpenClaw connects to Telegram automatically; talk to your bot to
  confirm.
- **Discord**: invite the bot to a server with the right scopes. The OpenClaw
  Control UI logs incoming events.
- **WhatsApp**: the Meta Cloud API requires a webhook callback URL. Use
  `https://<your-subdomain>.suji.fr/webhooks/whatsapp` in the Meta Business
  console.
- **Slack**: configure event subscriptions in your Slack app and point them at
  `https://<your-subdomain>.suji.fr/webhooks/slack`.

To add a channel after the initial install, edit the install in the dashboard,
toggle the channel on, paste its token, and save — OpenClaw redeploys
automatically with the new env.

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
