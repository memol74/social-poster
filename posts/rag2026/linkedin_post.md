🧠 Why does your RAG app confidently answer with the wrong document?

Most teams ship RAG as naive chunk-and-embed, then wonder why retrieval quietly fails in production.

A chunk like "The company's revenue grew by 3% over the previous quarter" says nothing about which company or which quarter. Strip the context, and even a perfect LLM can't save you.

Here's the 5-step stack that fixes it:

✅ Contextual chunks: prepend 50-100 tokens of LLM-generated context (Claude Haiku + prompt caching) before embedding and before building the BM25 index
✅ Hybrid search: combine dense vectors with BM25 keyword matching so exact strings like "Error code TS-999" don't get missed
✅ Fuse rankings with RRF (Reciprocal Rank Fusion), summing 1 / (k + rank) across both result sets
✅ Rerank: retrieve top 150 candidates, rerank with Cohere or Voyage, keep the top 20
✅ Filter by permissions: payload filters (Qdrant) or row-level security (Postgres) before results ever reach the prompt
✅ Evals gate every deploy: Ragas metrics (Faithfulness, Context Recall, Context Precision, Response Relevancy) run in CI

The payoff: top-20 retrieval failure rate goes from 5.7% baseline down to 1.9% with contextual chunks, contextual BM25, and reranking combined.

Small corpus under 200K tokens? Skip retrieval entirely and put the whole knowledge base in the prompt with caching.

pip install ragas

Which of these 5 steps is missing from your RAG pipeline today? 👇
