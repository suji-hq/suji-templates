# OpenClaw

Multi-channel messaging bot with AI-powered responses. Connects to Telegram,
Discord, WhatsApp Cloud API, and Slack, and replies to incoming messages using
your choice of AI provider (Anthropic Claude or OpenAI GPT).

This is the Suji marketplace packaging for the upstream
[openclaw/openclaw](https://github.com/openclaw/openclaw) image. The Suji
team does not maintain OpenClaw itself — we publish the manifest and
compose stitching only.

## What you'll need before installing

- **An AI provider API key**, from one of:
  - Anthropic ([console.anthropic.com](https://console.anthropic.com))
  - OpenAI ([platform.openai.com](https://platform.openai.com))
- **At least one channel token** for each platform you want OpenClaw to
  respond on. You can wire up channels incrementally — leave the others
  blank and add them later by editing the install.

## Configuration fields

| Field | Required | Notes |
|---|---|---|
| AI provider | yes | Which AI service replies — Anthropic (Claude) or OpenAI (GPT). |
| AI API key | yes | Your key for the chosen provider. Stored encrypted. |
| Gateway password | no | Auto-generated if blank. Used internally to authenticate the bot's webhook callbacks. |
| Channels | yes | Pick one or more of Telegram, Discord, WhatsApp, Slack. |
| Telegram bot token | only if Telegram selected | Get from [@BotFather](https://t.me/BotFather). |
| Discord bot token | only if Discord selected | Get from the [Discord developer portal](https://discord.com/developers/applications). |
| WhatsApp Cloud API token | only if WhatsApp selected | Get from Meta Business. |
| Slack bot token | only if Slack selected | Get from your Slack app's config page. |

## Recommended VM size

OpenClaw is comfortable on a **Small** VM (2 vCPU / 2 GB RAM / 5 GB storage).
A Mini (1 GB) VM works only at very low traffic and risks an OOM kill under
load — we recommend Small or larger.

## Where state is stored

State (sqlite database, session data, gateway config) lives in a named
Docker volume mounted at `/home/node/.openclaw` inside the container. The
volume survives container restarts, version upgrades, and VM snapshots.

## Notes

- **Reach OpenClaw via your tunnel hostname** — `https://<your-subdomain>.suji.fr/`.
  The public IPv4 address of the VM is not the right way to reach it.
- **Outbound mail is not supported on the standard plan.** Hetzner blocks
  outbound SMTP on ports 25 and 465 (anti-spam policy). If OpenClaw is
  configured for email notifications, use a relay service over port 587
  or an HTTP-based provider (SendGrid / Postmark / Mailgun / Resend).
- **Upgrades are flagged for review.** OpenClaw's version policy is
  `breaking-changes-flagged`: when a new version is released, the
  dashboard will surface a diff for you to acknowledge before upgrading
  rather than auto-upgrading in place.

## Reporting issues

- **OpenClaw bugs**: open an issue on
  [openclaw/openclaw](https://github.com/openclaw/openclaw/issues).
- **Marketplace packaging bugs** (compose / manifest / install flow):
  open an issue on [suji-hq/suji-templates](https://github.com/suji-hq/suji-templates/issues).
- **Suji platform bugs** (provisioning, billing, dashboard): open a
  support ticket from the Suji dashboard.
