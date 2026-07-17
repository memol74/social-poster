🚨 You're losing hours every week tracking AI agents across terminal windows.

You run Aider in one tab, Claude Code in another, some custom agent script in a third. You switch back and forth checking if something's stuck. A session crashes and you manually restart everything.

There's a better workflow: **herdr**—an open-source agent multiplexer built in Rust.

🛠️ What it does:
✅ Shows every agent in split panes with real-time status (blocked, working, done)
✅ Detach sessions and reattach from any terminal or over SSH—sessions survive restarts
✅ Agents can control herdr through a socket API (spawn panes, read output, coordinate tasks)

It's one Rust binary with no Electron bloat. You get tmux-style keyboard shortcuts AND full mouse support. There's a plugin marketplace to extend workflows.

Install with one curl command and you're running agents in persistent split panes immediately.

⭐ Over 1.6k stars on GitHub and actively developed full-time.

Search **herdr on GitHub** if you're managing multiple AI agents or long-running terminal tasks.

What's your current setup for juggling agents?
