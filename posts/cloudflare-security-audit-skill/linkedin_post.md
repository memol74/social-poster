🔐 Your AI agent ships code all day. Who is auditing it?

Most "AI security scans" are one model reading your code once and flagging everything that looks scary. You get noise, false positives, and real bugs buried in the pile.

Cloudflare open sourced the skill that started its internal vulnerability-hunting harness, and the design is worth studying:

✅ Recon first: it maps architecture, trust boundaries, and every input surface
✅ Isolated hunter agents sweep the code one attack class at a time, tracked in a coverage ledger
✅ Adversarial validation: the agent that checks a finding is never the agent that found it
✅ Findings land as confirmed, needs_validation, or rejected in schema-validated JSON, then get re-verified before the report

My favorite principle: severity requires impact. A missing defense layer is a hardening note, not a vulnerability.

41K GitHub stars. MIT licensed. Installs with one npx command into your coding agent.

Search "cloudflare security-audit-skill GitHub" and run it on your own repo.

Would you trust an AI auditor more if a second agent had to try to prove it wrong? 👇
