import os
from dotenv import load_dotenv

load_dotenv()

# NR has to go before Flask. It monkey-patches stdlib at import time,
# so if Flask loads first you lose most of the request tracing.
_NEWRELIC_ENABLED = bool(os.environ.get("NEW_RELIC_LICENSE_KEY"))
if _NEWRELIC_ENABLED:
    import newrelic.agent

    newrelic.agent.initialize(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "newrelic.ini")
    )

import time
import ldclient
from ldclient.config import Config
import ldobserve
from ldobserve import ObservabilityConfig, ObservabilityPlugin
from ldai import LDAIClient, AICompletionConfigDefault
from ldai.tracker import TokenUsage, FeedbackKind, LDAIConfigTracker
from flask import Flask, render_template, request, jsonify
import anthropic
from tickets import TICKETS

if _NEWRELIC_ENABLED:
    import newrelic.agent as nr

FLAG_POLL_INTERVAL_MS = int(os.environ.get("FLAG_POLL_INTERVAL_MS", "2000"))

app = Flask(__name__)

# SDK key is in .env as LAUNCHDARKLY_SDK_KEY
# LD dashboard > Settings cog > SDK keys
_observability_plugin = ObservabilityPlugin(
    ObservabilityConfig(
        service_name="supportiq-demo",
        service_version=os.environ.get("GIT_SHA", "dev"),
    )
)

ldclient.set_config(
    Config(
        sdk_key=os.environ.get("LAUNCHDARKLY_SDK_KEY", "sdk-key-placeholder"),
        plugins=[_observability_plugin],
    )
)
ld = ldclient.get()
aiclient = LDAIClient(ld)

# Three personas covering the three targeting scenarios:
#   Alice:   individually targeted (beta tester, pro tier)
#   Bob:     hits the enterprise plan rule, no individual entry needed
#   Charlie: no match, flag stays off
DEMO_USERS = {
    "alice": {
        "key": "alice@acmecorp.com",
        "display": "Alice - Pro, beta tester (individual target)",
        "plan_tier": "pro",
        "beta_tester": True,
        "region": "us-east",
        "account_id": "acme-corp-001",
    },
    "bob": {
        "key": "bob@globex.com",
        "display": "Bob - Enterprise tier (rule-based target)",
        "plan_tier": "enterprise",
        "beta_tester": False,
        "region": "us-west",
        "account_id": "globex-ind-042",
    },
    "charlie": {
        "key": "charlie@techstart.com",
        "display": "Charlie - Free tier (no match, flag off)",
        "plan_tier": "free",
        "beta_tester": False,
        "region": "eu-west",
        "account_id": "techstart-007",
    },
}


def build_context(user_data: dict) -> ldclient.Context:
    # Attribute names match what you'd pull from an auth token in a real app:
    # plan_tier, account_id, region. LD targeting runs against your existing user model,
    # not a parallel schema you have to build and keep in sync.
    return (
        ldclient.Context.builder(user_data["key"])
        .kind("user")
        .name(user_data["display"])
        .set("plan_tier", user_data["plan_tier"])
        .set("beta_tester", user_data["beta_tester"])
        .set("region", user_data["region"])
        .set("account_id", user_data["account_id"])
        .build()
    )


@app.route("/")
def index():
    return render_template(
        "index.html",
        tickets=TICKETS,
        users=DEMO_USERS,
        flag_poll_interval_ms=FLAG_POLL_INTERVAL_MS,
        ld_client_id=os.environ.get("LAUNCHDARKLY_CLIENT_ID", ""),
    )


@app.route("/api/flag-state")
def flag_state():
    # Polled every FLAG_POLL_INTERVAL_MS (set in .env).
    # When the flag flips in LD, the UI updates on the next cycle with no page reload.
    # This is the live-rollback moment in the demo.
    user_key = request.args.get("user", "alice")
    user_data = DEMO_USERS.get(user_key, DEMO_USERS["alice"])
    context = build_context(user_data)

    ai_enabled = ld.variation("ai-response-suggestions", context, False)

    ai_cfg = aiclient.completion_config(
        "supportiq-ai-config-v2",
        context,
        AICompletionConfigDefault(enabled=False),
    )

    # also evaluate shortcuts on every poll, not just /suggest
    # LD needs these exposures to assign users to experiment variants correctly
    shortcuts_enabled = ld.variation("smart-reply-shortcuts", context, False)

    model_name = ai_cfg.model.name if ai_cfg.model else "claude-haiku-4-5-20251001"
    variant_name = (
        ai_cfg.model.get_custom("variant_name") if ai_cfg.model else None
    ) or "default"

    if _NEWRELIC_ENABLED:
        nr.add_custom_attributes(
            [
                ("ld.user", user_key),
                ("ld.plan_tier", user_data["plan_tier"]),
                ("ld.ai_suggestions_enabled", ai_enabled),
                ("ld.shortcuts_enabled", shortcuts_enabled),
            ]
        )

    return jsonify(
        {
            "ai_suggestions_enabled": ai_enabled,
            "shortcuts_enabled": shortcuts_enabled,
            "user": user_key,
            "plan_tier": user_data["plan_tier"],
            "beta_tester": user_data["beta_tester"],
            "model": model_name,
            "variant_name": variant_name,
        }
    )


@app.route("/api/suggest", methods=["POST"])
def suggest():
    # Model and system prompt live in the LD AI Config (key: supportiq-ai-config-v2).
    # Change the prompt live in the LD dashboard mid-walkthrough.
    # No restart, no redeploy.
    data = request.get_json()
    ticket_body = data.get("ticket_body", "")
    user_key = data.get("user", "alice")
    user_data = DEMO_USERS.get(user_key, DEMO_USERS["alice"])
    context = build_context(user_data)

    ai_cfg = aiclient.completion_config(
        "supportiq-ai-config-v2",
        context,
        AICompletionConfigDefault(enabled=False),
    )
    tracker = ai_cfg.create_tracker()

    model_name = ai_cfg.model.name if ai_cfg.model else "claude-haiku-4-5-20251001"
    variant_name = (
        ai_cfg.model.get_custom("variant_name") if ai_cfg.model else None
    ) or "default"

    try:
        suggestion = _call_llm(ticket_body, ai_cfg, tracker)
    except Exception as exc:
        app.logger.exception("AI suggestion request failed")
        tracker.track_error()
        if _NEWRELIC_ENABLED:
            transaction = nr.current_transaction()
            if transaction is not None:
                transaction.notice_error(
                    error=exc,
                    attributes={
                        "ld.user": user_key,
                        "ld.model": model_name,
                        "ld.flag": "supportiq-ai-config-v2",
                    },
                    status_code=500,
                )
            else:
                nr.notice_error(
                    error=exc,
                    attributes={
                        "ld.user": user_key,
                        "ld.model": model_name,
                        "ld.flag": "supportiq-ai-config-v2",
                    },
                    status_code=500,
                )
        return jsonify({"error": str(exc)}), 500

    if _NEWRELIC_ENABLED:
        nr.add_custom_attributes(
            [
                ("ld.user", user_key),
                ("ld.plan_tier", user_data["plan_tier"]),
                ("ld.model", model_name),
                ("ld.variant_name", variant_name),
                ("ld.flag", "supportiq-ai-config-v2"),
            ]
        )

    return jsonify(
        {
            "suggestion": suggestion,
            "model_used": model_name,
            "variant_name": variant_name,
            "tracker_token": tracker.resumption_token,
        }
    )


def _call_llm(ticket_body: str, config, tracker) -> str:
    anthropic_client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY")
    )

    model = config.model.name if config.model else "claude-haiku-4-5-20251001"
    max_tokens = (
        config.model.get_parameter("max_tokens") or 1024 if config.model else 1024
    )

    # Anthropic needs the system prompt outside the messages array; pull it out
    # before building the user turns.
    # TODO: drop the hardcoded fallback and require it to come from the LD config
    ld_messages = [
        {"role": m.role, "content": m.content}
        for m in (config.messages or [])
    ]
    system = next(
        (m["content"] for m in ld_messages if m["role"] == "system"),
        "You are a senior customer support agent at SupportIQ. "
        "Write a brief, empathetic response to the customer's ticket. "
        "Be concise (2-3 sentences), acknowledge their issue, and provide a clear next step.",
    )
    user_messages = [m for m in ld_messages if m["role"] != "system"]
    user_messages.append({"role": "user", "content": f"Customer ticket:\n\n{ticket_body}"})

    start_ms = time.time() * 1000
    response = anthropic_client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=user_messages,
    )
    duration_ms = time.time() * 1000 - start_ms

    tracker.track_tokens(TokenUsage(
        total=response.usage.input_tokens + response.usage.output_tokens,
        input=response.usage.input_tokens,
        output=response.usage.output_tokens,
    ))
    tracker.track_duration(int(duration_ms))
    tracker.track_success()
    return response.content[0].text


@app.route("/api/track", methods=["POST"])
def track():
    # Two events:
    #   suggestion-accepted: agent clicked "Use this response" on the AI panel
    #   reply-sent:          agent sent any reply, whether AI or shortcut
    #
    # Both paths fire reply-sent on purpose. The experiment measures whether shortcuts
    # improve overall reply rate, not just whether agents use the AI panel.
    #
    # tracker_token reconstructs the original AI config evaluation so thumbs-up/down
    # feedback gets attributed to the right model+prompt in LD's AI Config Monitoring tab.
    data = request.get_json()
    user_key = data.get("user", "alice")
    event_name = data.get("event", "")
    metric_value = data.get("metric_value", 1.0)
    tracker_token = data.get("tracker_token")
    feedback_kind = data.get("feedback_kind")

    if not event_name and not tracker_token:
        return jsonify({"error": "event name required"}), 400

    user_data = DEMO_USERS.get(user_key, DEMO_USERS["alice"])
    context = build_context(user_data)

    if tracker_token and feedback_kind:
        result = LDAIConfigTracker.from_resumption_token(tracker_token, ld, context)
        if result.is_success():
            kind = FeedbackKind.Positive if feedback_kind == "positive" else FeedbackKind.Negative
            result.value.track_feedback({"kind": kind})
        else:
            app.logger.warning("Failed to reconstruct tracker for feedback: %s", result.error)

    if event_name:
        ld.track(event_name, context, metric_value=metric_value)

    return jsonify({"tracked": event_name or "feedback", "user": user_key})


@app.route("/api/simulate-traffic", methods=["POST"])
def simulate_traffic():
    # Seeds the smart-reply-shortcuts experiment with synthetic traffic.
    # Numbers are hardcoded to show a clear win: ~58% reply rate with shortcuts vs ~41% without.
    # Run this before the demo so the experiment dashboard isn't empty mid-walkthrough.
    # TODO: run this more than once and the sample size blows up; sim users are random UUIDs
    # so there's no deduplication.
    import random
    import uuid

    reply_events = 0

    for _ in range(250):
        sim_key = f"sim-user-{uuid.uuid4().hex[:8]}"
        plan = random.choice(["enterprise", "enterprise", "pro", "free"])

        context = (
            ldclient.Context.builder(sim_key)
            .kind("user")
            .set("plan_tier", plan)
            .set("beta_tester", False)
            .build()
        )

        shortcuts_on = ld.variation("smart-reply-shortcuts", context, False)

        reply_rate = 0.58 if shortcuts_on else 0.41
        if random.random() < reply_rate:
            ld.track("reply-sent", context, metric_value=1.0)
            reply_events += 1

    return jsonify({
        "reply_sent_events": reply_events,
    })


@app.route("/api/trigger-info")
def trigger_info():
    # Returns the curl command for the LD flag trigger so the demoer can run it live.
    # In a real incident this POST comes from PagerDuty or a Datadog monitor.
    # Setup: Flags > ai-response-suggestions > Configuration in environment > Add trigger,
    # then paste the URL into LD_TRIGGER_URL in .env.
    trigger_url = os.environ.get("LD_TRIGGER_URL", "")
    curl_cmd = (
        f'curl -X POST "{trigger_url}"'
        if trigger_url
        else "Set LD_TRIGGER_URL in .env (Flags > your flag > Settings > Add trigger)"
    )
    return jsonify({"curl_command": curl_cmd, "trigger_url": trigger_url})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    # Flask's reloader spawns a child process that double-registers the NR agent
    # and drops telemetry. Disable it when NR is active.
    app.run(debug=True, port=port, use_reloader=not _NEWRELIC_ENABLED)
