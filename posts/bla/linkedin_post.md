🛡️ What if the AI trying to crack your app went bankrupt instead?

AI reverse-engineering agents (REA) can now pick apart shipped software fast, and most defenses just slow them down a little.

BLA (Blind LLM Agents) takes a different approach: it protects your OWN build by making analysis expensive, not impossible.

✅ Poison layer: format-valid canaries, honey metadata, decoy control flow
✅ Exhaust layer: pushes artifacts past REA's documented resource budgets
✅ Hallucinate layer: truncated inventories, redaction failures, rabbit holes
✅ Runtime stays identical for real users
✅ Auto-discovers dist/, build/, .asar, .wasm, .sqlite, models and runs audit → protect → verify
✅ Works as an MCP server + skill with Claude Code, Cursor, Codex, Gemini CLI, Windsurf and more

In one empirical test, an Electron ASAR file grew from 607 B to 16.9 MiB and tripped the REA's 16 MiB header capacity limit outright.

Created just 5 days ago. Already at 1,187 GitHub stars and 160 forks. MIT licensed.

npx bla-agents harden .

Would you rather patch vulnerabilities or make attackers pay for every attempt? 👇
