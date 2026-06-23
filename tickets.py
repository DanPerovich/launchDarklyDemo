"""
Demo support tickets for SupportIQ.

These are the sample tickets displayed in the UI. Add, remove, or edit tickets
here without touching any application logic in app.py.
"""

TICKETS = [
    {
        "id": "TKT-001",
        "subject": "Cannot export data to CSV",
        "customer": "Priya Mehta",
        "account": "Acme Corp",
        "priority": "High",
        "body": (
            "Hi, I've been trying to export our support ticket data to CSV for the last two hours. "
            "The button appears to do nothing. We have a board presentation tomorrow and urgently "
            "need this data. Please help."
        ),
    },
    {
        "id": "TKT-002",
        "subject": "SSO login failing for new users",
        "customer": "Marcus Webb",
        "account": "Globex Industries",
        "priority": "Critical",
        "body": (
            "New hires added to our Okta instance this week are unable to log in via SSO. "
            "They get a 'user not provisioned' error. Existing users are unaffected. "
            "This is blocking onboarding for 12 people."
        ),
    },
    {
        "id": "TKT-003",
        "subject": "API rate limit questions",
        "customer": "Lisa Zhang",
        "account": "TechStart Inc",
        "priority": "Low",
        "body": (
            "Could you clarify the rate limits on your REST API? Specifically, what's the limit "
            "per minute on the /tickets endpoint? We're building an integration and want to make "
            "sure we stay within limits."
        ),
    },
    {
        "id": "TKT-004",
        "subject": "Dashboard charts not loading after latest update",
        "customer": "Jordan Okafor",
        "account": "Meridian Analytics",
        "priority": "High",
        "body": (
            "Since this morning's update our analytics dashboard is completely blank. "
            "The charts were working fine yesterday. We're seeing JavaScript console errors "
            "mentioning a 'failed to fetch' on /api/metrics. Our whole ops team relies on "
            "this view to start their day — please investigate urgently."
        ),
    },
    {
        "id": "TKT-005",
        "subject": "Billing invoice shows incorrect seat count",
        "customer": "Sofia Reyes",
        "account": "Bluewave Financial",
        "priority": "Medium",
        "body": (
            "Our June invoice lists 47 seats but we only have 31 active users. "
            "I've checked the admin panel and confirmed the correct headcount. "
            "We were charged $384 too much. Can you issue a corrected invoice and credit "
            "the difference before our finance team closes the month?"
        ),
    },
    {
        "id": "TKT-006",
        "subject": "Webhook payloads arriving out of order",
        "customer": "Tariq Hassan",
        "account": "Nexus Logistics",
        "priority": "Medium",
        "body": (
            "We're receiving ticket.updated webhooks that arrive before the corresponding "
            "ticket.created events about 20% of the time. This is causing our downstream "
            "pipeline to drop updates. Is there a guaranteed ordering mechanism, or a "
            "sequence number we can use to reorder events on our end?"
        ),
    },
    {
        "id": "TKT-007",
        "subject": "2FA enrollment page crashes on Safari",
        "customer": "Emily Hartmann",
        "account": "ClearPath Health",
        "priority": "Critical",
        "body": (
            "Our security policy now requires all staff to enroll in two-factor authentication, "
            "but the enrollment page crashes immediately on Safari 17. The page loads, the QR "
            "code appears briefly, then the tab goes blank. Chrome works fine. "
            "We have a compliance deadline in 48 hours — this is blocking roughly 60 users."
        ),
    },
    {
        "id": "TKT-008",
        "subject": "Search returning stale results after ticket close",
        "customer": "Ravi Sundaram",
        "account": "Orbit Commerce",
        "priority": "Low",
        "body": (
            "When I search for tickets by keyword, closed tickets that match the query keep "
            "appearing in results even after I filter for 'Open only'. This started happening "
            "about a week ago. It's not a showstopper but it's making it hard to triage "
            "the queue accurately."
        ),
    },
    {
        "id": "TKT-009",
        "subject": "Custom fields missing from ticket export",
        "customer": "Nadia Kowalski",
        "account": "Stratos SaaS",
        "priority": "Medium",
        "body": (
            "We have eight custom fields configured on our ticket form — things like 'Product Area' "
            "and 'Customer Severity'. None of them appear in the CSV export. The standard fields "
            "all export correctly. We need the custom fields for a quarterly report due Friday."
        ),
    },
    {
        "id": "TKT-010",
        "subject": "Agent collision alerts not firing",
        "customer": "Derek Lau",
        "account": "Pinnacle Retail",
        "priority": "High",
        "body": (
            "Two of our agents responded to the same ticket simultaneously last week and sent "
            "contradictory answers to the customer. I thought the system was supposed to show "
            "a warning when another agent is viewing a ticket. The collision detection feature "
            "doesn't seem to be working. Can you check if it's enabled on our account?"
        ),
    },
]
