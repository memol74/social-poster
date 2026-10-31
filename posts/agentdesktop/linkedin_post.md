🖱️ How does your AI agent know what it's actually clicking on?

Most computer-use agents guess from screenshots, matching pixels and hoping the button didn't move.

Vercel Labs just open-sourced Agent Desktop, and it takes a completely different approach:

✅ Reads the OS accessibility tree instead of matching pixels
✅ One snapshot returns JSON with a ref for every actionable element
✅ Agent clicks the ref, then snapshots again to verify the result
✅ UI changed? It returns STALE_REF or AMBIGUOUS_TARGET instead of clicking the wrong thing
✅ Headless by default, actions go through the accessibility API without moving your pointer or stealing focus
✅ CLI and C library, native binaries for macOS, Windows and Linux, x64 and ARM64

4,152 stars, 293 forks, Rust, Apache-2.0 licensed.

Install: npm install -g agent-desktop

Would you trust an agent to operate your desktop apps without taking your mouse? 👇
