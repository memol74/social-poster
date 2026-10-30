🖥️ Tired of paying per token?

Token APIs are like a restaurant: convenient, but you pay per dish every single time. A rented GPU is your own kitchen: you pay per hour, and at high volume or with private data, that math can flip in your favor.

This video walks through self-hosting an open-source LLM end to end:

✅ Pick an open model: Qwen/Qwen3-8B (Apache-2.0, ~8.2B params) or OpenAI's gpt-oss
✅ Do the VRAM math: BF16 = 2 bytes/param (~16.4GB for Qwen3-8B), then shrink with FP8 (9.44GB) or AWQ 4-bit (6.10GB)
✅ Rent a GPU VM (RunPod, Lambda, AWS/GCP/Azure) and check it with nvidia-smi -L
✅ Serve it with vLLM in Docker, an OpenAI-compatible server with /v1/chat/completions
✅ Call it with the OpenAI SDK, pointing base_url at your server
✅ Lock it down behind TLS and --api-key, keep port 8000 private
✅ Watch Prometheus metrics like vllm:num_requests_waiting to know when to scale

vLLM Docker command from the docs:
docker run --gpus all --ipc=host -p 8000:8000 vllm/vllm-openai:latest --model Qwen/Qwen3-8B

Pro tip: an idle rented GPU still bills by the hour, scale to zero with serverless GPUs like Modal or RunPod Serverless.

Would you self-host your next LLM or stay on a token API? 👇
