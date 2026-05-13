import json
from datetime import datetime, timezone
from pathlib import Path

from .extractor import VideoTranscript


def generate_manifest(transcripts_dir: Path, output_path: Path) -> dict:
    entries = []
    for channel_dir in sorted(transcripts_dir.iterdir()):
        if not channel_dir.is_dir():
            continue
        for json_file in sorted(channel_dir.glob("*.json")):
            transcript = _load_transcript(json_file)
            if transcript is None:
                continue
            entries.append(
                {
                    "id": transcript.id,
                    "title": transcript.title,
                    "channel": transcript.channel,
                    "channel_slug": transcript.channel_slug,
                    "date": transcript.date,
                    "duration": transcript.duration,
                    "has_captions": transcript.has_captions,
                    "path": str(json_file.relative_to(transcripts_dir.parent)),
                }
            )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(entries),
        "videos": sorted(entries, key=lambda e: e["date"], reverse=True),
    }

    output_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def _load_transcript(path: Path) -> VideoTranscript | None:
    try:
        data = json.loads(path.read_text())
        return VideoTranscript.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        return None
