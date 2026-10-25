💬 Comment-to-DM is one feature. Why is it always a monthly subscription?

OpenReply is an open-source, MIT-licensed alternative to ManyChat for Instagram comment-to-DM automation. You self-host it, so there are no seat limits or plan caps (hosting costs are your own).

How it works:
✅ Someone comments a keyword on your post or reel (or DMs you, or replies to your Story)
✅ OpenReply matches it against your campaigns and queues a job
✅ A background worker sends the private reply through the official Meta API, no scraping, no browser automation, no Instagram password

What stands out:
✅ Tracked links with clicks and CTR per campaign
✅ Optional follow gate before the link is sent
✅ Per-account rate limiting under Meta's 750 private replies/hour cap, overflow is queued instead of dropped
✅ Next.js 16, Prisma + PostgreSQL, BullMQ on Redis

2.8K GitHub stars. Search "diwenne openreply GitHub" to deploy your own copy.

Would you self-host your DM automation to drop a subscription? 👇
