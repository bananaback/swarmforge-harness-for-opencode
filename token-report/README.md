# Token Usage Report

Reports token consumption from the OpenCode SQLite database.

## Formulas

```
Total Input   = tokens_input + tokens_cache_read
Output        = tokens_output + tokens_reasoning
Cache Hit %   = tokens_cache_read / Total Input
Output Ratio  = Output / Total Input
```

## Files

- `calc.py` — CLI tool for quick token calculations
- `report.html` — Token usage report (14-15 Sep)
- `deepseek-report.html` — DeepSeek-only report (5-15 Sep)
- `README.md` — This file

## Quick Start

```bash
# Default: 14-15 Sep 2026
python3 token-report/calc.py

# Single date
python3 token-report/calc.py --date 2026-09-14

# Date range
python3 token-report/calc.py --from 2026-09-14 --to 2026-09-16

# Single session
python3 token-report/calc.py --session ses_xxx

# Custom DB path
python3 token-report/calc.py --db /path/to/opencode.db
```

## Database Location

Default: `~/.local/share/opencode/opencode.db`

Override with `--db` flag or set `SWARM_CONFIG` env var.
