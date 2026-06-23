/**
 * SupportIQ frontend
 *
 * Three things this page actually does:
 *   1. Poll /api/flag-state on a short interval. When the flag flips in the
 *      LD dashboard, the AI panel appears or disappears within one poll cycle,
 *      no reload required.
 *
 *   2. On ticket selection (or flag flip), hit /api/suggest to get an AI
 *      response using whatever model + prompt LD is currently serving.
 *
 *   3. The "Simulate incident" button shows the curl command to kill the flag
 *      via an LD trigger
 */

"use strict";

let currentUser = "alice";
let currentTicket = null;
let aiEnabled = false;
let shortcutsEnabled = false;
let currentTrackerToken = null;
const FLAG_POLL_INTERVAL_MS = window.FLAG_POLL_INTERVAL_MS ?? 2000;

const flagBadge = document.getElementById("flag-badge");
const badgeText = document.getElementById("badge-text");
const ticketDetail = document.getElementById("ticket-detail");

// ---- context strip ----
function updateContextStrip(userKey) {
    const container = document.getElementById("context-strip-attrs");
    const user = window.DEMO_USERS && window.DEMO_USERS[userKey];
    if (!container || !user) return;

    const attrs = [
        { k: "plan_tier",   v: user.plan_tier,          hi: user.plan_tier !== "free" },
        { k: "beta_tester", v: String(user.beta_tester), hi: user.beta_tester === true },
        { k: "region",      v: user.region,              hi: false },
        { k: "account_id",  v: user.account_id,          hi: false },
    ];

    container.innerHTML = attrs.map(({ k, v, hi }) =>
        `<span class="ctx-attr"><span class="ctx-attr-key">${k}:</span>\u00a0<span class="ctx-attr-val${hi ? " hi" : ""}">${v}</span></span>`
    ).join("");
}

// ---- user switching (avatar chips) ----
document.querySelectorAll(".avatar-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
        document.querySelectorAll(".avatar-chip").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        currentUser = chip.dataset.user;
        updateContextStrip(currentUser);
        if (window.ldObsClient) {
            var u = window.DEMO_USERS && window.DEMO_USERS[currentUser];
            if (u) {
                // Re-identify so LD routes AI Config evaluations and analytics
                // to the new context. Without this the SDK keeps evaluating as
                // whoever loaded the page.
                window.ldObsClient.identify({
                    kind: 'user', key: u.key, name: u.display,
                    plan_tier: u.plan_tier, beta_tester: u.beta_tester,
                });
            }
        }
        checkFlagState();
        if (currentTicket) renderTicket(currentTicket);
    });
});

document.querySelectorAll(".ticket-item").forEach((item) => {
    item.addEventListener("click", () => {
        document.querySelectorAll(".ticket-item").forEach((i) =>
            i.classList.remove("selected")
        );
        item.classList.add("selected");
        currentTicket = {
            id: item.dataset.id,
            subject: item.dataset.subject,
            body: item.dataset.body,
            customer: item.dataset.customer,
            account: item.dataset.account,
            priority: item.dataset.priority,
        };
        renderTicket(currentTicket);
    });
});

function renderTicket(ticket) {
    const priorityClass = "priority priority-" + ticket.priority.toLowerCase();

    const shortcutsHtml = (shortcutsEnabled && aiEnabled)? `
        <div class="shortcuts-panel" id="shortcuts-panel">
            <div class="shortcuts-label">Quick reply</div>
            <div class="shortcuts-row">
                <button class="btn-shortcut" data-reply="acknowledge">Acknowledge issue</button>
                <button class="btn-shortcut" data-reply="escalate">Escalate to tier 2</button>
                <button class="btn-shortcut" data-reply="more-info">Request more info</button>
            </div>
        </div>
    ` : "";

    ticketDetail.innerHTML = `
        <div class="ticket-header">
            <h1>${ticket.subject}</h1>
            <div class="meta">
                <span>${ticket.id}</span>
                <span>${ticket.customer}</span>
                <span>${ticket.account}</span>
                <span class="${priorityClass}">${ticket.priority}</span>
            </div>
        </div>
        <div class="ticket-body">${ticket.body}</div>
        ${shortcutsHtml}
        <div class="ai-panel ${aiEnabled ? "fade-in" : "hidden"}" id="ai-panel">
            <div class="ai-panel-header">
                <span class="ai-label">AI response suggestion</span>
                <span class="model-badge" id="model-badge">loading</span>
                <span class="variant-badge" id="variant-badge" style="display:none"></span>
            </div>
            <div class="ai-panel-body">
                <div class="ai-suggestion loading" id="ai-suggestion">
                    Generating suggestion...
                </div>
                <div class="ai-actions">
                    <button class="btn btn-primary" id="btn-use-response">Use this response</button>
                    <button class="btn btn-secondary" onclick="loadSuggestion()">
                        Regenerate
                    </button>
                </div>
            </div>
        </div>
        <div class="off-state" id="off-state" style="display:${aiEnabled ? "none" : "block"}">
            AI suggestions are not enabled for this account.
        </div>
    `;
    if (aiEnabled) loadSuggestion();
    wireReplyButtons();
}

async function loadSuggestion() {
    if (!currentTicket || !aiEnabled) return;

    const el = document.getElementById("ai-suggestion");
    const modelBadge = document.getElementById("model-badge");
    const variantBadge = document.getElementById("variant-badge");
    if (!el) return;

    currentTrackerToken = null;
    el.innerHTML = `<div class="shimmer-wrap">
        <div class="shimmer-bar shimmer-bar--wide"></div>
        <div class="shimmer-bar shimmer-bar--medium"></div>
        <div class="shimmer-bar shimmer-bar--narrow"></div>
    </div>`;
    el.classList.add("loading");

    // flag-state is cheap; fire it first so the model/variant badges show up
    // before the LLM call resolves. /api/suggest will overwrite them if the
    // flag happened to flip between the two requests.
    const flagFetch = fetch(`/api/flag-state?user=${currentUser}`)
        .then((r) => r.json())
        .then((flagData) => {
            if (modelBadge && flagData.model) modelBadge.textContent = flagData.model;
            if (variantBadge) {
                if (flagData.variant_name && flagData.variant_name !== "default") {
                    variantBadge.textContent = "variant: " + flagData.variant_name;
                    variantBadge.style.display = "inline";
                } else {
                    variantBadge.style.display = "none";
                }
            }
        })
        .catch(() => {});

    const suggestFetch = fetch("/api/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            ticket_body: currentTicket.body,
            user: currentUser,
        }),
    })
        .then((r) => r.json())
        .then((data) => {
            el.innerHTML = "";
            el.classList.remove("loading");
            el.textContent = data.suggestion;
            currentTrackerToken = data.tracker_token || null;

            // correct the badges with what the backend actually used. Rare but
            // possible if a flag flipped between the two fetches
            if (modelBadge) modelBadge.textContent = data.model_used;
            if (variantBadge) {
                if (data.variant_name && data.variant_name !== "default") {
                    variantBadge.textContent = "variant: " + data.variant_name;
                    variantBadge.style.display = "inline";
                } else {
                    variantBadge.style.display = "none";
                }
            }
        })
        .catch(() => {
            el.innerHTML = "";
            el.classList.remove("loading");
            el.textContent = "Could not load suggestion. Check your API keys and flag setup.";
        });

    await Promise.all([flagFetch, suggestFetch]);
}

// ---- reply button wiring ----
function wireReplyButtons() {
    const btnUse = document.getElementById("btn-use-response");
    if (btnUse) {
        btnUse.addEventListener("click", async () => {
            await trackReply("ai-suggestion");
            if (currentTrackerToken) {
                // positive-feedback event is fire-and-forget; don't block the UI on it
                fetch("/api/track", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        user: currentUser,
                        tracker_token: currentTrackerToken,
                        feedback_kind: "positive",
                    }),
                }).catch(() => {});
            }
            btnUse.textContent = "Response applied";
            btnUse.disabled = true;
        });
    }

    document.querySelectorAll(".btn-shortcut").forEach((btn) => {
        btn.addEventListener("click", async () => {
            await trackReply(btn.dataset.reply);
            document.querySelectorAll(".btn-shortcut").forEach((b) => (b.disabled = true));
            btn.textContent = "Sent";
        });
    });
}

async function trackReply(replyType) {
    // both paths fire reply-sent so the shortcuts experiment has a common
    // conversion event regardless of whether the user clicked AI or a shortcut
    await fetch("/api/track", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            user: currentUser,
            event: "reply-sent",
            metadata: { reply_type: replyType },
        }),
    });
}

// ---- flag state polling ----
// polling instead of SSE.  SSE probably would be cleaner for go-live
// 3s default feels instant to a live audience; tune FLAG_POLL_INTERVAL_MS in .env if needed.
async function checkFlagState() {
    try {
        const res = await fetch(`/api/flag-state?user=${currentUser}`);
        const data = await res.json();

        const prevAi = aiEnabled;
        const prevShortcuts = shortcutsEnabled;

        aiEnabled = data.ai_suggestions_enabled;
        shortcutsEnabled = data.shortcuts_enabled;

        // badge only reflects the AI suggestions flag; shortcuts don't get their own indicator
        if (aiEnabled) {
            flagBadge.className = "flag-badge on";
            badgeText.textContent = "AI suggestions: on";
        } else {
            flagBadge.className = "flag-badge off";
            badgeText.textContent = "AI suggestions: off";
        }

        // Re-render on any flag change so the AI panel and shortcuts stay in sync.
        if ((prevAi !== aiEnabled || prevShortcuts !== shortcutsEnabled) && currentTicket) {
            renderTicket(currentTicket);
        }
    } catch {
        flagBadge.className = "flag-badge";
        badgeText.textContent = "LD: unreachable";
    }
}

updateContextStrip(currentUser);
checkFlagState();
setInterval(checkFlagState, FLAG_POLL_INTERVAL_MS);

// ---- trigger modal ----
const copyBtn = document.getElementById("btn-copy-curl");
let copyResetTimer = null;

function setCopyButtonState(enabled, label = "Copy") {
    if (!copyBtn) return;
    copyBtn.disabled = !enabled;
    copyBtn.textContent = label;
    copyBtn.classList.toggle("copied", label === "Copied!");
}

async function copyCurlCommand() {
    const display = document.getElementById("curl-display");
    const text = display?.textContent?.trim();
    if (!text || text === "Loading..." || text.startsWith("Could not")) return;

    try {
        await navigator.clipboard.writeText(text);
    } catch {
        // clipboard API requires HTTPS or localhost; this fallback covers anyone
        // running the demo over plain HTTP on a local network
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.setAttribute("readonly", "");
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
    }

    setCopyButtonState(true, "Copied!");
    clearTimeout(copyResetTimer);
    copyResetTimer = setTimeout(() => setCopyButtonState(true), 2000);
}

async function showTrigger() {
    document.getElementById("trigger-modal").classList.remove("hidden");
    const display = document.getElementById("curl-display");
    display.textContent = "Loading...";
    setCopyButtonState(false);
    try {
        const res = await fetch("/api/trigger-info");
        const data = await res.json();
        display.textContent = data.curl_command;
        setCopyButtonState(true);
    } catch {
        display.textContent = "Could not load trigger info.";
        setCopyButtonState(false);
    }
}

function hideTrigger() {
    document.getElementById("trigger-modal").classList.add("hidden");
    clearTimeout(copyResetTimer);
    setCopyButtonState(false);
}
