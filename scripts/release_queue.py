#!/usr/bin/env python3
"""Release the next scheduled wallpaper from data/queue.json.

Each queue entry has a slug, a UTC publish_at time, a title and a description;
its image waits in data/queue/<slug>.jpg. When an entry is due, this script
moves the image to static/assets/originals/, adds the row to the top of
data/wallpapers.csv and drops the entry from the queue. At most one entry is
released per run, so a delayed run never posts two images at once.

Prints "released=<slug>" (also to $GITHUB_OUTPUT) when something was released.
"""
import csv
import io
import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "data" / "queue.json"
CSV = ROOT / "data" / "wallpapers.csv"
IST = timezone(timedelta(hours=3))


def main():
    queue = json.loads(QUEUE.read_text()) if QUEUE.exists() else []
    now = datetime.now(timezone.utc)
    due = [q for q in queue if datetime.fromisoformat(q["publish_at"].replace("Z", "+00:00")) <= now]
    if not due:
        print("nothing due; queue length", len(queue))
        return
    item = min(due, key=lambda q: q["publish_at"])
    slug = item["slug"]
    image = f"/assets/originals/{slug}.jpg"
    shutil.move(str(ROOT / "data" / "queue" / f"{slug}.jpg"), str(ROOT / "static" / image.lstrip("/")))

    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerow(
        [slug, now.astimezone(IST).strftime("%Y-%m-%d"), "originals", image, item["title"], item["description"]])
    header, rest = CSV.read_text(encoding="utf-8").split("\n", 1)
    CSV.write_text(header + "\n" + buf.getvalue() + rest, encoding="utf-8")

    queue.remove(item)
    QUEUE.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n")
    print(f"released={slug}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"released={slug}\n")


if __name__ == "__main__":
    main()
