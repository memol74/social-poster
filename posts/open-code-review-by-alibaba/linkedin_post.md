🚨 Your AI code reviewer is missing entire files on large changesets.

You've probably seen it: Claude Code or similar agents breeze through the first few files, then quietly skip others. Line numbers drift. Comments land on the wrong code. Review quality swings wildly with minor prompt tweaks.

The root problem? A purely language-driven architecture has no hard constraints on the review process.

🛠️ Alibaba solved this after reviewing millions of defects at scale.

Open Code Review is a hybrid CLI tool that combines deterministic engineering with agent intelligence. The engineering layer handles what must never go wrong:

✅ Precise file selection — every changed file is reviewed, guaranteed
✅ Smart file bundling — related files are grouped and reviewed together
✅ Fine-grained rule matching — review rules are matched to each file's characteristics, eliminating information noise

The agent handles dynamic decision-making: scenario-tuned prompts, purpose-built tool calls, and deep context retrieval. It catches null pointer exceptions, thread-safety bugs, XSS, and SQL injection using proven fine-tuned rules.

The result? Higher precision, higher F1, and one-ninth the token cost of general-purpose agents like Claude Code. 16,445 stars and battle-tested at Alibaba scale.

Next time you open a pull request, just run `ocr review` and catch real defects before merge.

⭐ Search **alibaba/open-code-review** on GitHub to try it.

Have you ever had an AI reviewer miss critical files or land comments on the wrong lines?
