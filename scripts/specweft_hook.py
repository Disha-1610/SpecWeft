"""Entry point for Claude Code hook configs: works from any cwd (adds the SpecWeft checkout to sys.path)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from specweft.hook import main  # noqa: E402

sys.exit(main())
