import json
from pathlib import Path

from data_pipeline.crawling.schema import ProductObservation


class JsonlProductExporter:
    """Write product observations as UTF-8 JSONL."""

    def export(
        self,
        observations: list[ProductObservation],
        path: str | Path,
        append: bool = False,
    ) -> dict[str, object]:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"

        with output_path.open(mode, encoding="utf-8") as handle:
            for item in observations:
                handle.write(json.dumps(item.to_jsonl_dict(), ensure_ascii=False) + "\n")

        return {
            "path": str(output_path),
            "count": len(observations),
        }
