"""`python -m arena_node <config.json>` : lance un node."""

import json
import sys
from pathlib import Path

from arena_node.runner import run_node

if __name__ == "__main__":
    run_node(json.loads(Path(sys.argv[1]).read_text()))
