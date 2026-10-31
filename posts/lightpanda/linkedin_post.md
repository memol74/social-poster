🐼 What if your headless browser didn't need 2GB of RAM just to load 100 pages?

Most automation setups run headless Chrome, and it's heavy: slow boot times, bloated memory, fans spinning on your CI runners.

Lightpanda is an open-source browser written in Zig, built from scratch for AI agents and automation:

✅ Not a Chromium fork, not a WebKit patch, JavaScript runs via V8
✅ 9x faster execution: 5s vs 46s on a 100-page benchmark (AWS EC2 m5.large)
✅ 16x less memory: 123MB peak vs 2GB for headless Chrome
✅ Works with your existing Puppeteer or Playwright scripts via CDP server
✅ Also supports WebDriver BiDi
✅ Ships its own MCP server (JSON-RPC 2.0 over stdio and HTTP)

39,186 stars, 1,905 forks, AGPL-3.0 licensed.

Install: brew install lightpanda-io/browser/lightpanda

Would swapping your Chrome instance for this change your automation costs? 👇
