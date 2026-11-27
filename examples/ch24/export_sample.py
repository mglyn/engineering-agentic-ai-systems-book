"""Export the standalone Chinese sample from the chapter used by MkDocs."""
import argparse
import os
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1] / "docs/zh/part6/ch24_streaming_interrupts.md"


def render(destination):
    def relocate(match):
        target = match.group(1)
        if "://" in target or target.startswith("#"):
            return match.group()
        file, separator, fragment = target.partition("#")
        resolved = (SOURCE.parent / file).resolve(strict=True)
        relative = Path(os.path.relpath(resolved, destination.parent)).as_posix()
        return "](" + relative + separator + fragment + ")"

    return re.sub(r"\]\(([^)\s]+)\)", relocate, SOURCE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "sample_ch24_zh.md")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(args.output.resolve()), encoding="utf-8")
