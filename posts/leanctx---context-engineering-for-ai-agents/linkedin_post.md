🚨 Your AI coding agent just read the same utility file for the twelfth time today.

Each read: 2,000 tokens.
Your context window: bleeding out.
Your bill: climbing.

Most developers think context waste is just the cost of using AI agents. It's not. LeanCTX is a single Rust binary that sits between your agent (Cursor, Claude Code, Copilot, Windsurf) and your codebase—and it decides what your agent actually sees.

✅ Cached re-reads cost ~13 tokens instead of 2,000
✅ Shell output (git status, npm logs) compresses 95% smaller
✅ Session memory persists across chats so you stop re-explaining your codebase

It cuts 60–90% of your tokens without breaking prompt caching or discarding content. Raw git status normally costs 800 tokens. LeanCTX compresses it to 120. And when your agent asks for a file again, it pulls from cache instead of re-tokenizing the whole thing.

One command: `lean-ctx setup`. Zero config. Works with every major AI coding tool. Local-first, model-agnostic, and yours—not locked in a vendor's memory black box.

Over 1,000 stars on GitHub. Developers are using it to keep context windows open twice as long and cut API bills in half.

🔍 Search "LeanCTX" on GitHub and check the benchmarks yourself.

Are you still paying full price for repeat reads?
