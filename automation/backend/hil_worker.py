"""Write the GUI configuration and delegate execution to the existing HIL runner."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from automation.HIL.run import cli
from .capture_worker import main as watched_main


def main():
    config = json.loads(sys.argv[1])
    extra = sys.argv[2:]
    with TemporaryDirectory(prefix="stlink_hil_config_") as directory:
        path = Path(directory) / "config.json"
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        sys.argv = ["stlink-hil", "--config", str(path), *extra]
        return watched_main(cli)


if __name__ == "__main__":
    sys.exit(main())
