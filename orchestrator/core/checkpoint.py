import json
from pathlib import Path
from typing import Any

class CheckpointManager:
    """
    Manages JSON checkpoints and event streams under .orchestrator/runs/<run_id>/.
    """

    def __init__(self, runs_dir: Path | str, run_id: str):
        self.run_dir = (Path(runs_dir) / run_id).resolve()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.run_dir / "state.json"
        self.history_file = self.run_dir / "history.jsonl"

    def save_state(self, state_dict: dict[str, Any]) -> None:
        self.state_file.write_text(json.dumps(state_dict, indent=2, default=str), encoding="utf-8")

    def load_state(self) -> dict[str, Any] | None:
        if not self.state_file.exists():
            return None
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def log_event(self, event_type: str, data: dict[str, Any]) -> None:
        record = {
            "event": event_type,
            "data": data,
        }
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
