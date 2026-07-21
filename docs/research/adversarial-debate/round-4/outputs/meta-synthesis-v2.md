# Meta-Synthesis v2 — Round 4 (after pi seats)

**Date:** 2026-07-21  
**Seats completed:**

| Seat | Path | Artifact |
| --- | --- | --- |
| Grok 4.5 High | grok subagent | `proposal-grok-45-high.md` |
| Codex / Claude Fable | grok subagents (R4 first pass) | in-session; Codex order ≈ PEAD∥Form-4 |
| **Kimi K3** | **pi** `opencode-go/kimi-k3` | `proposal-kimi-k3.md` ✅ |
| **DeepSeek V4 Pro** | **pi** `deepseek/deepseek-v4-pro` | `proposal-deepseek-v4-pro.md` ✅ |
| Gemini | pi google / openrouter | **auth fail** (invalid key / 401) |
| Claude Fable (pi) | openrouter | **401 Missing Authentication** |
| Codex GPT-5.6 Sol (pi) | openai-codex | hung / relaunched |

## What the new seats changed

### Consensus still holds

1. Inventory first (I0). Only SEP → Full-Stop re-seal.  
2. Residual / R2-1 stay dead.  
3. PEAD F0 was **data absence**, not returns null.  
4. Dual-exit kill / re-seal = success.  
5. LLM-on-prices / fine-tune as first dollar = **reject**.  
6. Entitlement ≠ edge.

### New disagreements (useful)

| Axis | Meta v1 (Codex/Claude) | Kimi K3 (pi) | DeepSeek (pi) | Grok seat |
| --- | --- | --- | --- | --- |
| After inventory | PEAD F0 ∥ Form-4 density | **Serialize: Form-4 density memo first**, then SF1 integrity | **SF3 first**, SF2 second, PEAD third | Form-4 (CFOB) first |
| Parallel tracks | Yes A∥B | **No** (16GB law + option value of cheap kill) | SF2∥SF3 F0 OK; PEAD not vanguard | Sequential |
| Promote conf. | 25–35% | **12%** | ~20% any line | ~28% PEAD, higher process |
| SF3 rank | Last | Reject as first dollar | **Highest novelty** | Low |

### Meta v2 ordered program (hardened)

```
L0  Inventory probe (I0 fail → re-seal)
L1  Form-4 / SF2 density memo only (histogram + CMP feasibility; no returns)
    → kill in memo if sparse / year-mass high
L2  SF1 AR reader + PEAD D0–D7 *measured* (integrity debt; still no E1)
    → hard D-fail = measured kill
L3  Exactly ONE E1 of the better surviving line (Form-4 F0→E1 or PEAD E1)
L4  Contingent: GP/quality or accruals on sealed SF1 if E1 path dies once
L5  SF3 / 13F only if SF3 entitled AND L1–L4 not both dead — lag-honest F0 first
STOP Two sequential honest kills → Full-Stop re-seal (precommitted)
```

**Why not DeepSeek’s SF3-first:** lag (~45d) is first-class; copycat literature is unkind; “highest novelty” ≠ implementable density. SF3 stays in queue but **after** a cheap Form-4 density falsifier and SF1 integrity debt — unless inventory shows SF2 absent and SF3 present.

**Why not PEAD∥Form-4 parallel forever:** Kimi is right that parallel forfeits the option value of a 3–5 day density kill before a 1–2 week SF1 reader. 16GB sequential law already written into this repo’s research drivers.

**Why PEAD still in queue early:** data-absence debt; helpers exist; Martineau prior means E1 is dual-exit ready — but PEAD is **integrity second**, not alpha vanguard.

## Auth / tooling notes

- `pi --provider opencode-go --model kimi-k3` works.  
- `pi --provider deepseek --model deepseek-v4-pro` works.  
- Google Gemini key invalid in this environment.  
- OpenRouter returns 401 (no auth header).  
- Ollama kimi models require ollama.com subscription upgrade.

## Immediate next engineering (if human approves)

1. `inventory_probe.py` → SF1/SF2/SF3 live rows under `NASDAQ_DATA_LINK_API_KEY`  
2. Artifact `inventory-probe.json` + short entitlement memo  
3. Gate on I0 before any SF* adapter PRD  
