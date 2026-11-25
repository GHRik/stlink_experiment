"""Desktop settings kept outside the operator interface."""
import json
from pathlib import Path


def load_settings():
    return json.loads(Path(__file__).with_name("config.json").read_text(encoding="utf-8-sig"))
