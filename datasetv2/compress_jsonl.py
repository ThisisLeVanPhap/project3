import json
import sys
from pathlib import Path

def parse_multiple_json_objects(text: str):
    """Parse concatenated JSON objects (possibly multi-line) from a text blob."""
    dec = json.JSONDecoder()
    i = 0
    n = len(text)
    objs = []

    # skip leading whitespace
    while i < n and text[i].isspace():
        i += 1

    while i < n:
        obj, j = dec.raw_decode(text, i)
        objs.append(obj)
        i = j
        # skip whitespace between objects
        while i < n and text[i].isspace():
            i += 1

    return objs

def compress_jsonl_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8").strip()
    if not original:
        print(f"⚠ empty file: {path}")
        return False

    objs = parse_multiple_json_objects(original)

    out = "\n".join(json.dumps(o, ensure_ascii=False) for o in objs) + "\n"

    # If no change, do nothing
    if original == out.strip():
        print(f"= no change (already 1-line objs): {path}  (objs={len(objs)})")
        return False

    path.write_text(out, encoding="utf-8")
    print(f"✔ updated: {path}  (objs={len(objs)})")
    return True

def main():
    # Usage: python compress_jsonl.py DATASETV2
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("DATASETV2")
    root = root.resolve()

    if not root.exists():
        print(f"❌ Path not found: {root}")
        print("Run: python compress_jsonl.py <path_to_DATASETV2>")
        sys.exit(1)

    files = sorted(root.rglob("*.jsonl"))
    print(f"Root: {root}")
    print(f"Found {len(files)} .jsonl files")

    changed = 0
    for f in files:
        try:
            if compress_jsonl_file(f):
                changed += 1
        except json.JSONDecodeError as e:
            print(f"❌ JSON parse error in {f}")
            print(f"   {e}")
        except Exception as e:
            print(f"❌ Error processing {f}: {e}")

    print(f"Done. Updated {changed}/{len(files)} files.")

if __name__ == "__main__":
    main()
