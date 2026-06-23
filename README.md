# SupportIQ — LaunchDarkly SE Technical Exercise

**Candidate:** Dan Perovich  
**Stack:** Python 3.11+, Flask, LaunchDarkly Python SDK v9, Anthropic API, New Relic Python Agent (optional)

---

## What This Demos

Putting AI directly into a support agent's workflow means touching every ticket, every shift, every customer interaction. If the AI starts returning unhelpful or off-brand responses, the support team notices before your monitoring does. The engineering team needs to be able to kill it in seconds, not in the time it takes to get a deploy approved or find someone with pipeline access at 2am.

SupportIQ is a fictional enterprise support SaaS. The demo covers four things that actually matter in that release:

1. **Release safely:** flag wraps the feature end-to-end, rollback in seconds, no redeployment, no page reload.
2. **Target deliberately:** beta testers by user key first, enterprise accounts by attribute rule, no separate builds.
3. **Control the AI at runtime:** model and system prompt live in an LD flag. Product team tunes tone or swaps models from the dashboard. No PR, no deploy, no downtime.
4. **Observe with context:** every request carries LD flag state into New Relic as custom attributes. Slice LLM latency, errors, and traffic by user, plan tier, model, and active flag variation.

---

## Project Structure

```
supportiq/
├── app.py               Flask application — routes, LD flag evaluations, LLM calls
├── newrelic.ini         New Relic agent configuration (license key via env var)
├── templates/
│   └── index.html       Ticket dashboard UI (Jinja2)
├── static/
│   ├── style.css        Dashboard styling
│   └── main.js          Flag state polling, UI updates, trigger modal
├── requirements.txt
├── .env.example         Required environment variables
├── tickets.py           Support tickets loaded in the dashboard at startup
└── README.md
```

---

## Before You Run This

- Python 3.11+
- A LaunchDarkly trial account -- [start one here](https://launchdarkly.com/start-trial/)
- An Anthropic API key -- [console.anthropic.com](https://console.anthropic.com)
- A New Relic account (optional) -- [sign up](https://newrelic.com/signup) for APM, distributed tracing, and error tracking

---

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/supportiq-ld-demo.git
cd supportiq-ld-demo

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and fill in your keys (see "Environment variables" below)
```

### Environment variables

| Variable | Where to get it |
|---|---|
| `LAUNCHDARKLY_SDK_KEY` | LD dashboard > Settings cog > SDKs > Server-side SDK key |
| `LAUNCHDARKLY_CLIENT_ID` | LD dashboard > Settings cog > SDKs > Client-side ID |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) > API keys |
| `LD_TRIGGER_URL` | LD dashboard > Flags > `ai-response-suggestions` > Configuration in environment > Add trigger (optional -- see Remediate demo below) |
| `NEW_RELIC_LICENSE_KEY` | New Relic One > API keys > Ingest - License (optional -- enables APM) |
| `NEW_RELIC_APP_NAME` | Display name in New Relic UI (optional, default: `SupportIQ Demo`) |

`LAUNCHDARKLY_SDK_KEY` and `LAUNCHDARKLY_CLIENT_ID` are both required and live on the same page in the LD dashboard. They are not interchangeable.

---

## Flag Setup

Create these two flags in your LD project before running the app.

### `ai-response-suggestions` (Part 1 and Part 2)

| Setting | Value |
|---|---|
| Flag key | `ai-response-suggestions` |
| Type | Boolean |
| Default variation | `false` (off) |

**Targeting rules to configure for Part 2:**

1. **Individual target:** Add `alice@acmecorp.com` -> serve `true`
   *(demonstrates individual targeting)*

2. **Rule:** `plan_tier` is one of `enterprise` -> serve `true`
   *(demonstrates rule-based targeting -- Bob matches this rule)*

3. **Default:** `false`
   *(Charlie, a free-tier user, gets nothing)*

**Trigger setup (for Part 1 Remediate):**

Go to Flags > `ai-response-suggestions` > Configuration in environment > Add trigger. Copy the generated trigger URL into `LD_TRIGGER_URL` in your `.env`.

### `supportiq-ai-config-v2` (Extra credit -- AI Configs)

This flag uses LD's AI Configs feature via `launchdarkly-server-sdk-ai` rather than a plain JSON flag. The dashboard gives you a prompt editor with model picker and versioning. The SDK returns a typed object with built-in telemetry tracking.

**Create the AI Config:**

1. In the LD dashboard, click **Create** and choose **AI Config**.
2. Set the key to `supportiq-ai-config-v2` and click **Create**.

**Variation A -- "concise" (set as default):**

| Setting | Value |
|---|---|
| Variation name | concise |
| Model | `claude-haiku-4-5-20251001` |
| Model parameter: `max_tokens` | `256` |
| Model custom parameter: `variant_name` | `concise` |
| System message | `You are a senior customer support agent at SupportIQ. Write a brief, empathetic response to the customer's ticket. Be concise (2-3 sentences), acknowledge their issue, and provide a clear next step.` |

**Variation B -- "detailed":**

| Setting | Value |
|---|---|
| Variation name | detailed |
| Model | `claude-sonnet-4-6` |
| Model parameter: `max_tokens` | `1024` |
| Model custom parameter: `variant_name` | `detailed` |
| System message | `You are an expert customer support agent at SupportIQ. Write a thorough, empathetic response. Acknowledge the customer's frustration, explain what likely caused the issue, and provide specific troubleshooting steps they can follow immediately.` |

The `variant_name` custom parameter is read via `ai_cfg.model.get_custom("variant_name")` and shown in the green badge in the AI panel. `max_tokens` is read via `ai_cfg.model.get_parameter("max_tokens")` and passed directly to the Anthropic API call.

Set variation A as the default. During the demo, switch to variation B in the LD dashboard to show the model and response style change in real time. No redeployment required.

---

## Running the Demo

```bash
python app.py
```

Open [http://localhost:5001](http://localhost:5001).

### Observability with New Relic (optional)

Set `NEW_RELIC_LICENSE_KEY` in `.env` and restart. Without a key the app runs normally with no agent overhead. Flask's auto-reloader is disabled when New Relic is active to avoid double-registering the agent.

**What the agent captures automatically:**

| Capability | What you see in New Relic |
|---|---|
| **APM transactions** | Flask web transactions for `/`, `/api/flag-state`, `/api/suggest`, `/api/trigger-info`, etc. |
| **External services** | Anthropic `POST /v1/messages` calls as external spans nested under `/api/suggest` |
| **Distributed tracing** | End-to-end trace waterfall (enabled in `newrelic.ini`) |
| **Error tracking** | Handled exceptions on `/api/suggest` reported via `transaction.notice_error()` with LaunchDarkly context attached |

**LaunchDarkly custom attributes** (explicitly attached per request so you can filter and group in NRQL):

| Attribute | Endpoint | Description |
|---|---|---|
| `ld.user` | `/api/flag-state`, `/api/suggest` | Active demo persona (`alice`, `bob`, `charlie`) |
| `ld.plan_tier` | `/api/flag-state`, `/api/suggest` | User's plan tier from LD context (`pro`, `enterprise`, `free`) |
| `ld.ai_suggestions_enabled` | `/api/flag-state` | Boolean result of `ai-response-suggestions` flag evaluation |
| `ld.model` | `/api/suggest` | Anthropic model served by the AI Config (e.g. `claude-haiku-4-5-20251001`, `claude-sonnet-4-6`) |
| `ld.variant_name` | `/api/suggest` | Model name of the active AI Config variation (mirrors `ld.model`) |
| `ld.flag` | `/api/suggest` | AI Config key evaluated for the LLM call (`supportiq-ai-config-v2`) |

On LLM failures (e.g. invalid `ANTHROPIC_API_KEY`), the exception is attached to the active transaction with `ld.user`, `ld.model`, and `ld.flag` before the handled 500 is returned. Errors appear in **Errors inbox** with the same AI Config context as successful requests. The AI Configs SDK also calls `tracker.track_error()` automatically, surfacing the failure in the LD AI Config analytics dashboard.

**Setup:**

1. In New Relic One, go to **API keys** and copy your **Ingest - License** key.
2. Add it to `.env`:

   ```
   NEW_RELIC_LICENSE_KEY=your-license-key-here
   # NEW_RELIC_APP_NAME=SupportIQ Demo   # optional — defaults to SupportIQ Demo
   ```

3. Restart the app: `python app.py`
4. Generate traffic: load tickets, switch users, regenerate suggestions, toggle flags in LD.
5. Open **APM & Services** -> **SupportIQ Demo** (or your `NEW_RELIC_APP_NAME`).

Data usually appears within one to two minutes of first traffic. If you're demoing the New Relic section live, generate traffic before the walkthrough starts.

**Where to look:**

- **Transactions** -> `/api/suggest`: total latency broken down by Anthropic external call; expand a trace to see `ld.*` custom attributes on the transaction.
- **Distributed tracing**: waterfall view showing Flask handler -> Anthropic API span.
- **Errors**: `anthropic.AuthenticationError` and other LLM failures with `ld.model` and `ld.user` attached.
- **Query your data** (NRQL example):

  ```sql
  SELECT count(*) FROM Transaction
  WHERE appName = 'SupportIQ Demo' AND name = 'WebTransaction/Flask/Function/suggest'
  FACET ld.model, ld.variant_name SINCE 30 minutes ago
  ```

---

## Demo walkthrough

---

### Part 1: Release and Remediate

**Setup first:** `ai-response-suggestions` OFF globally, no targeting rules active.

**The flag is off — show the absence.** Open the app, select any ticket. No AI panel, red badge in the header. This is the baseline. The point isn't "here's what off looks like", it's that the UI responds to the flag state without a code change or reload.

**Flip it on live.** Toggle `ai-response-suggestions` ON in the LD dashboard. Don't touch the app. Within 3 seconds the AI panel appears and the badge goes green. **Say it explicitly**: no redeploy, no config file edit, no engineer woke up.

**Showcase kill switch.** Click "Simulate incident," copy the curl command. This is the runbook one-liner, what an on-call engineer pastes at 2am from PagerDuty. Run it. The panel disappears. Remediation doesn't require touching code, opening a PR, or finding someone with deploy access.

---

### Part 2: Target

**Setup first:** Global flag ON, both targeting rules enabled (individual target for Alice, `plan_tier = enterprise` rule for Bob).

**Alice proves individual targeting.** Select Alice, open a ticket. AI panel is visible, green badge. She's targeted by user key.

**Charlie proves the default.** Switch to Charlie. Panel gone. They match nothing, no individual target, no rule, so they get the default: off.

**Bob shows attribute targeting** Switch to Bob. Panel is back. He was never individually listed, but the enterprise rule caught him automatically. Every new enterprise account that signs up gets the feature without anyone adding them to a list.

---

### Extra credit: AI Configs

**Order dependency:** AI panel in demo webapp must be visible (use Alice or Bob from Part 2).

**The current state is intentional.** Note the model badge: `claude-haiku-4-5-20251001`. Note the response is concise. It's the "concise" variation of the `supportiq-ai-config-v2` AI Config.

**Swap the variation, don't redeploy.** In the LD dashboard, flip the default from "concise" to "detailed." Click Regenerate in the app. Badge flips to `claude-sonnet-4-6`, response is noticeably more thorough. Prompt iteration and model swaps don't require an engineering ticket. The LD dashboard is their runtime control plane for AI behavior.

---

### Observability: LaunchDarkly context in New Relic

**Prerequisite:** `NEW_RELIC_LICENSE_KEY` in `.env`, app restarted.

**Flags show up in your APM traces.** With Alice selected, regenerate a suggestion, then pull up the `/api/suggest` transaction in New Relic. The custom attributes — `ld.user=alice`, `ld.plan_tier=pro`, `ld.model`, `ld.variant_name` — are all stamped at evaluation time from the flag, not hardcoded. Switch to Bob, regenerate, facet by `ld.plan_tier`. Enterprise users and beta testers are now distinguishable in the same APM dashboard without any additional instrumentation.

**Config changes are visible in telemetry immediately.** Flip the AI Config variation from "concise" to "detailed," regenerate, check the next trace. `ld.model` flips to `claude-sonnet-4-6` — no redeploy, but the observability layer reflects the live config. The AI Config analytics dashboard also records the `track_success()` event with the new variation.

---

## Design Notes

**Why polling instead of a streaming SDK connection for the flag listener?**

The LD server-side Python SDK maintains a persistent streaming connection and evaluates flags in memory, so evaluation speed is unaffected by the polling interval. The 3-second frontend poll is deliberate: easy to inspect in the browser's Network tab during a demo, no WebSocket complexity, and the latency is barely perceptible in a live walkthrough.

**Why attach LaunchDarkly state to New Relic custom attributes?**

Feature flags change runtime behavior, but production incidents surface in observability tools, not the LD dashboard. Stamping `ld.user`, `ld.plan_tier`, `ld.model`, and `ld.variant_name` onto every APM transaction means an on-call engineer can answer "why is latency spiking for enterprise users on the detailed prompt?" directly in New Relic without cross-referencing two consoles. The attributes are set at flag evaluation time on each request, so they always reflect the config that was actually active when the LLM call ran.
