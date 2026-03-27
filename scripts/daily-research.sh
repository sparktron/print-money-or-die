#!/usr/bin/env bash
# PMOD Daily Research — runs via cron at 6:30 AM ET
# Calls Claude Code CLI to produce a pre-market briefing

set -euo pipefail

PROJECT_DIR="/home/mythos/repos/print-money-or-die"
OUTPUT_DIR="${PROJECT_DIR}/research-outputs"
TODAY=$(date +%Y-%m-%d)
OUTPUT_FILE="${OUTPUT_DIR}/briefing-${TODAY}.md"

mkdir -p "${OUTPUT_DIR}"

# Fetch latest congressional trade disclosures
echo "[pmod-research] Fetching congressional trade disclosures..."
pmod politicians fetch >> "${OUTPUT_DIR}/cron.log" 2>&1 \
    && echo "[pmod-research] Congressional trades updated." \
    || echo "[pmod-research] WARNING: politicians fetch failed (non-fatal)" >&2

# Skip if today's briefing already exists
if [[ -f "${OUTPUT_FILE}" ]]; then
    echo "[pmod-research] Briefing already exists: ${OUTPUT_FILE}"
    exit 0
fi

echo "[pmod-research] Generating briefing for ${TODAY}..."

claude --print --allowedTools "WebSearch,WebFetch,Write,Bash(read-only)" \
"You are the research analyst for the PrintMoneyOrDie (PMOD) portfolio.

Produce a daily pre-market intelligence briefing. Do the following:

1. **Market Overview**: Search the web for today's market conditions — US futures, overnight moves in Asia/Europe, key economic data releases scheduled today, and any Fed/macro news.

2. **Sector Trends**: Identify the top 3 trending sectors and the top 3 lagging sectors over the past week. Note any sector rotation signals.

3. **Major Movers**: Find the biggest pre-market movers (top 5 gainers, top 5 losers) and briefly explain why each is moving.

4. **News & Catalysts**: Summarize the 5 most market-moving headlines from the last 24 hours — earnings surprises, geopolitical events, regulatory changes, or macro data.

5. **Portfolio-Relevant Insights**: Given a growth-oriented strategy focused on tech, AI/ML, semiconductors, and high-momentum names, provide:
   - 3 actionable ideas (buy/watch/trim) with brief reasoning
   - Any risk flags or warnings for current watchlist names (NVDA, PLTR, AVGO, META, LLY, COIN)
   - Sentiment summary: bullish / neutral / bearish with a one-line rationale

6. **Output**: Write the full briefing as a markdown file saved to:
   ${OUTPUT_FILE}

Keep the briefing concise but information-dense — aim for a 2-minute read. Use clear headers, bullet points, and bold key takeaways. End with a one-line Bottom Line summary." \
> /dev/null 2>&1

if [[ -f "${OUTPUT_FILE}" ]]; then
    echo "[pmod-research] Briefing saved: ${OUTPUT_FILE}"
else
    echo "[pmod-research] ERROR: Briefing was not generated" >&2
    exit 1
fi
