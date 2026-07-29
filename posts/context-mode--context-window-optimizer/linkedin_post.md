🚨 Your AI coding agent just forgot what file it was editing.

After 30 minutes, 40% of your context window is gone. One Playwright snapshot costs 56 KB. Twenty GitHub issues? 59 KB. A single access log? 45 KB. The agent compacts the conversation to free space — and loses your active file list, task history, and the question you asked five minutes ago.

Most context optimization stops at prompt compression. Context Mode fixes the other half: **where tool output goes**.

✅ **98% context reduction** — sandboxes raw tool data; a 315 KB dump becomes 5.4 KB  
✅ **Session continuity** — SQLite + BM25 search persists file edits, git ops, and task state across compactions  
✅ **Think in code** — the LLM writes scripts that compute results, not token-burning data processors

⭐ **19,438 stars.** Used across teams at Microsoft, Google, Meta, Amazon, NVIDIA, and Stripe. Hooks for 17 platforms: Claude Code, Cursor, Gemini CLI, VS Code Copilot, JetBrains, and more.

Search GitHub for "mksglu/context-mode" and reclaim your context budget.

Have you hit a context limit mid-refactor this week?
