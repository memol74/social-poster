🚨 Your AI coding agent just spent 50,000 tokens reading one Stack Overflow page.

That's $0.15 per search. Every single time it needs docs.

The usual fix? Build scrapers for every site. Write adapters. Pray the HTML stays stable.

Meet **only-cli** — one npm package that turns any website into a numbered CLI for AI agents.

✅ Distills pages from 50k tokens to 500
✅ Works on any static site with zero per-site config
✅ Ships shortcuts for 20+ dev sites (GitHub, AWS, Stack Overflow, MDN)

⭐ 400+ stars

You run `oc open news.ycombinator.com` and your agent gets:
```
[1] Show HN: I built a tiny CSV toolkit
[2] 312 comments
actions: do <n> | read <n> | next
```

Instead of tens of thousands of tokens of markup.

Next time Claude needs AWS docs, you type `oc aws guide s3` instead of burning tokens on raw HTML. The agent follows numbered links with `oc do 3` and never touches a URL.

🔍 Search GitHub for "only-cli/oc" and install it in 30 seconds.

How much are you spending on agent browsing tokens right now?
