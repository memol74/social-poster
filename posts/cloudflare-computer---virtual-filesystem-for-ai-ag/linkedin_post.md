🚨 You're still spinning up containers just to let your agent write one file.

Cloudflare Computer solves this with a virtual filesystem backed by SQLite inside a Durable Object. Your agent mounts it as a real FUSE filesystem, writes files, runs shell commands, and the state survives across every run.

No container rebuild. No ephemeral storage headaches. No reinventing persistence.

✅ Real filesystem that agents can mount anywhere
✅ Faster than local disk on metadata-heavy operations
✅ State persists across runs in a Durable Object

The repo already has 5,382 stars and runs three execution backends: container, isolate shell, and isolate JavaScript. MIT licensed, TypeScript implementation, and designed specifically for agent workflows.

Next time your agent needs to remember anything between runs, just mount a Computer workspace.

Search GitHub for "cloudflare computer" and clone the repo.

How are you currently handling persistent state for your agents? 🤔
