📈 What if a Transformer could read candlestick charts the way it reads text?

Most forecasting tools are either black-box trading bots or academic models you can't actually run.

Kronos is an open-source foundation model built specifically for K-line data:

✅ First open-source foundation model for financial candlesticks, trained on data from over 45 global exchanges
✅ Two-stage design: a tokenizer quantizes OHLCV data into hierarchical discrete tokens
✅ A decoder-only autoregressive Transformer pre-trained on those tokens to predict what comes next
✅ Three open sizes on Hugging Face: Kronos-mini (4.1M params), Kronos-small (24.7M), Kronos-base (102.3M)
✅ Fine-tuning scripts released so you can adapt it to your own data
✅ Live demo forecasting BTC/USDT 24h candles

44,652 stars. MIT licensed. Paper accepted at AAAI 2026.

Install: pip install -r requirements.txt

Then load with KronosTokenizer.from_pretrained() and Kronos.from_pretrained(), and forecast with KronosPredictor().predict().

Not financial advice, just a genuinely open model for a closed field.

Would you trust a Transformer to forecast a chart? 👇
