#!/usr/bin/env python3
"""Runnable SEC-8K-2.02 I0 acquisition/audit driver for issue #83.

Examples (the historical acquisition is intentionally not started on import):

  uv run invest-sec8k-i0 acquire \
    --start-year 2004 --end-year 2025 \
    --listings pit-listings.json --sessions xnys-sessions.json \
    --power-basis sec8k-power-basis.json --cache-dir sec8k_index_cache \
    --submissions-zip submissions-2026-07-22.zip \
    --submissions-sha256 177ad76e6ca6cd4f5f39e19cccea76c289e7f19ca20846666225ec6604a85799 \
    --manifest-output sec8k-i0-manifest.json \
    --user-agent 'invest-research contact@example.com' \
    --snapshot-id sec-edgar-through-2025 --generated-at 2026-01-01T00:00:00Z

  uv run invest-sec8k-i0 audit \
    --manifest sec8k-i0-manifest.json --output sec8k-i0-artifact.json

Compressed index acquisition is resumable through the immutable content-hash
cache. The SEC bulk archive is hash-pinned and processed without extraction. This
driver contains no outcome, reaction, candle, price, forward-return, or P&L path.
"""

from __future__ import annotations

import sys

from invest.adapters.sec8k_i0_cli import main


if __name__ == "__main__":
    sys.exit(main())
