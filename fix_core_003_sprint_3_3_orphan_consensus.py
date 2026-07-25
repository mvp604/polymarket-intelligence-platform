from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

root = Path.cwd().resolve()
target = root / "src" / "snapshots" / "service.py"

if not target.exists():
    raise SystemExit(
        "Run this script from the project root. "
        "Missing src/snapshots/service.py"
    )

backup_dir = (
    root
    / "backups"
    / (
        "core_003_sprint_3_3_orphan_consensus_fix_"
        + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )
)
backup_file = backup_dir / "src" / "snapshots" / "service.py"
backup_file.parent.mkdir(parents=True, exist_ok=False)
shutil.copy2(target, backup_file)

text = target.read_text(encoding="utf-8")

if "from .models import SnapshotMarket" not in text:
    import_lines = list(re.finditer(r"^from \.models import .*?$", text, re.MULTILINE))
    if import_lines:
        match = import_lines[0]
        line = match.group(0)
        if "(" not in line:
            text = text[:match.start()] + line + ", SnapshotMarket" + text[match.end():]
        else:
            raise SystemExit(
                "service.py has a multiline .models import that this safe patch "
                "will not guess. Please share src/snapshots/service.py."
            )
    else:
        anchor = "from __future__ import annotations\n"
        if anchor not in text:
            raise SystemExit("Could not locate a safe import insertion point.")
        text = text.replace(
            anchor,
            anchor + "\nfrom .models import SnapshotMarket\n",
            1,
        )

marker = "        snapshot = self.loader.build(\n"
if marker not in text:
    raise SystemExit(
        "Could not locate the snapshot build call in service.py. "
        "Please share src/snapshots/service.py."
    )

normalization = """        known_market_ids = {str(item.market_id) for item in markets}
        consensus_only_markets = []
        for item in consensus:
            market_id = str(item.market_id)
            if market_id not in known_market_ids:
                consensus_only_markets.append(
                    SnapshotMarket(
                        market_id=item.market_id,
                        title=f"Market {market_id}",
                        category="unknown",
                        status="active",
                        yes_price=None,
                        no_price=None,
                    )
                )
                known_market_ids.add(market_id)

        if consensus_only_markets:
            markets = tuple(markets) + tuple(consensus_only_markets)

"""

if "consensus_only_markets = []" not in text:
    text = text.replace(marker, normalization + marker, 1)

required = [
    "SnapshotMarket",
    "consensus_only_markets = []",
    "markets = tuple(markets) + tuple(consensus_only_markets)",
]
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit(
        "Patch verification failed. Missing: " + ", ".join(missing)
    )

compile(text, str(target), "exec")
target.write_text(text, encoding="utf-8", newline="\n")

print(f"Backup created: {backup_dir}")
print("Patched src/snapshots/service.py")
print("Python syntax validation passed")
print()
print("Run:")
print("  python manage.py test")
print("  python -m pytest tests/snapshots -q")
print("  python snapshot_manage.py create")
print("  python snapshot_manage.py list")