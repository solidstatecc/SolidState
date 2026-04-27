# Solid State agent

The runtime side of solidstate.cc.

The marketplace is the storefront. This is the staff.

## What it does

```
Buyer → solidstate.cc (Vercel)
     → Stripe / x402 confirms payment
     → POST /webhook/payment to this agent (Hostinger)
     → Agent fetches skill from Supabase Storage
     → Spawns NemoClaw sandbox
     → Skill runs, JSON in, JSON out
     → Result returned, run logged
     ↓
Telegram ← Admin commands and run reports
```

## Layout

```
agent/
├── api/          FastAPI app — webhook + run endpoints
├── runner/       Skill loader + NemoClaw sandbox runner
├── admin/        Telegram bot — /approve, /reject, /status, /featured
├── db/           Supabase REST client
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Webhook contract

`POST /webhook/payment`

Headers:
- `X-Signature` — `hex(hmac_sha256(WEBHOOK_SECRET, f"{ts}.{body}"))`
- `X-Timestamp` — Unix seconds, ±300s drift allowed

Body:
```json
{
  "skill_id": "uuid",
  "buyer_id": "uuid-or-wallet-or-email",
  "payment_proof": "ch_xxx | x402-receipt-hash",
  "input_payload": { "...": "skill-specific" },
  "callback_url": "https://solidstate.cc/api/runs/RUN_ID/done"
}
```

Returns `{ "run_id": "...", "status": "queued" }`. The actual result is delivered to `callback_url`, or polled from `/runs/{run_id}` (todo: add this read endpoint as needed).

## Skill bundle contract

A skill is a tarball stored in Supabase Storage. Required:

- `SKILL.md` — name, description, input schema, pricing
- `entry.py` — reads JSON from stdin, writes JSON to stdout, exits 0

That's it. Anything else (scripts, references, prompts) lives alongside.

## Deploy on Hostinger

```bash
git clone git@github.com:solidstatecc/solidstate.cc.git ~/solidstate
cd ~/solidstate/agent
cp .env.example .env
nano .env   # fill in all four sections

docker compose up -d --build
docker compose logs -f api
```

Open port 8000 to the public, behind a reverse proxy with TLS (Caddy or nginx).

## Wire it to Vercel

In your Next.js API route (Stripe webhook or x402 success handler):

```ts
import crypto from "crypto";

const ts = Math.floor(Date.now() / 1000).toString();
const body = JSON.stringify({
  skill_id: skillId,
  buyer_id: buyerId,
  payment_proof: charge.id,
  input_payload: input,
  callback_url: `${process.env.SITE_URL}/api/runs/${runId}/done`,
});
const sig = crypto
  .createHmac("sha256", process.env.WEBHOOK_SECRET!)
  .update(`${ts}.${body}`)
  .digest("hex");

await fetch(`${process.env.AGENT_URL}/webhook/payment`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-Signature": sig,
    "X-Timestamp": ts,
  },
  body,
});
```

## Telegram admin

DM your bot. Commands:

```
/status
/approve <skill_id>
/reject <skill_id> <reason>
/featured <skill_id>
/payouts
/help
```

Set `TELEGRAM_ADMIN_CHAT_ID` to lock the bot to your chat. Anyone else gets ignored.

## Supabase tables (minimum)

```sql
create table skills (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  title text not null,
  status text not null default 'pending',
  bundle_url text not null,
  sha256 text,
  seller_id uuid,
  featured boolean default false,
  rejection_reason text,
  created_at timestamptz default now()
);

create table runs (
  id uuid primary key,
  skill_id uuid references skills(id),
  buyer_id text,
  payment_proof text,
  status text not null,
  result jsonb,
  error text,
  created_at timestamptz default now()
);

create table payouts (
  id uuid primary key default gen_random_uuid(),
  seller_id uuid not null,
  amount_usd numeric not null,
  status text default 'pending',
  created_at timestamptz default now()
);
```

## Test it locally

```bash
ALLOW_INTERNAL_RUN=1 SANDBOX_RUNTIME=docker uvicorn agent.api.main:app --reload

curl -X POST localhost:8000/run \
  -H 'content-type: application/json' \
  -d '{"skill_id":"<id>","buyer_id":"test","input_payload":{"hello":"world"}}'
```

## What's not here yet

- Per-call payout accounting (build on top of `runs` table)
- Read endpoint for run status polling
- Admin web UI (Telegram is enough for now)
- Skill bundle signing (only sha256 verification today)

Ship the rough version. Iterate on what buyers actually use.
