import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel


class Segment(BaseModel):
    time: int
    text: str


class Chapter(BaseModel):
    time: int
    title: str


class VideoTranscript(BaseModel):
    id: str
    title: str
    channel: str
    channel_slug: str
    date: str
    duration: int
    url: str
    description: str
    has_captions: bool
    caption_type: str | None
    language: str
    segments: list[Segment]
    chapters: list[Chapter]
    extracted_at: str


class ExtractionError(Exception):
    pass


class PermanentError(ExtractionError):
    pass


class TransientError(ExtractionError):
    pass


PERMANENT_PATTERNS = [
    "Sign in to confirm your age",
    "members only",
    "Private video",
    "Video unavailable",
    "not available in your country",
    "is not available",
    "Join this channel",
]

TRANSIENT_PATTERNS = [
    "HTTP Error 429",
    "Connection refused",
    "timed out",
    "Connection reset",
    "HTTP Error 5",
    "Unable to download",
]

NO_CAPTION_PATTERNS = [
    "no subtitles",
    "Subtitles are disabled",
    "no automatic captions",
]


def classify_error(stderr: str) -> ExtractionError:
    for pattern in PERMANENT_PATTERNS:
        if pattern.lower() in stderr.lower():
            return PermanentError(stderr.strip())
    for pattern in TRANSIENT_PATTERNS:
        if pattern.lower() in stderr.lower():
            return TransientError(stderr.strip())
    return ExtractionError(stderr.strip())


def extract_metadata(video_url: str) -> dict:
    result = subprocess.run(
        ["yt-dlp", "--skip-download", "--print-json", "--no-warnings", video_url],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise classify_error(result.stderr)
    return json.loads(result.stdout)


def extract_subtitles(video_url: str, language: str) -> tuple[str | None, str | None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                "yt-dlp",
                "--write-auto-sub",
                "--write-sub",
                "--sub-lang",
                language,
                "--skip-download",
                "--no-warnings",
                "-o",
                f"{tmpdir}/%(id)s.%(ext)s",
                video_url,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            for pattern in NO_CAPTION_PATTERNS:
                if pattern.lower() in result.stderr.lower():
                    return None, None
            raise classify_error(result.stderr)

        tmppath = Path(tmpdir)
        for vtt_file in tmppath.glob(f"*.{language}.vtt"):
            caption_type = "auto" if ".auto" in vtt_file.stem else "manual"
            return vtt_file.read_text(), caption_type

        for srt_file in tmppath.glob(f"*.{language}.srt"):
            caption_type = "auto" if ".auto" in srt_file.stem else "manual"
            return srt_file.read_text(), caption_type

        return None, None


def parse_vtt(content: str) -> list[Segment]:
    segments: list[Segment] = []
    lines = content.strip().split("\n")

    timestamp_re = re.compile(r"(\d{2}):(\d{2}):(\d{2})\.\d{3}\s*-->")
    tag_re = re.compile(r"<[^>]+>")

    current_time: int | None = None
    current_text_parts: list[str] = []

    for line in lines:
        line = line.strip()
        match = timestamp_re.match(line)
        if match:
            if current_time is not None and current_text_parts:
                text = _clean_text(" ".join(current_text_parts))
                if text:
                    segments.append(Segment(time=current_time, text=text))
            hours, minutes, seconds = int(match.group(1)), int(match.group(2)), int(match.group(3))
            current_time = hours * 3600 + minutes * 60 + seconds
            current_text_parts = []
        elif line and not line.startswith("WEBVTT") and not line.startswith("NOTE") and current_time is not None:
            cleaned = tag_re.sub("", line)
            if cleaned.strip():
                current_text_parts.append(cleaned.strip())

    if current_time is not None and current_text_parts:
        text = _clean_text(" ".join(current_text_parts))
        if text:
            segments.append(Segment(time=current_time, text=text))

    return _merge_segments(_deduplicate_segments(segments))


def parse_srt(content: str) -> list[Segment]:
    segments: list[Segment] = []
    timestamp_re = re.compile(r"(\d{2}):(\d{2}):(\d{2}),\d{3}\s*-->")
    tag_re = re.compile(r"<[^>]+>")

    blocks = re.split(r"\n\n+", content.strip())
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue

        time_match = None
        text_lines = []
        for line in lines:
            match = timestamp_re.match(line)
            if match:
                hours, minutes, seconds = int(match.group(1)), int(match.group(2)), int(match.group(3))
                time_match = hours * 3600 + minutes * 60 + seconds
            elif time_match is not None and not line.strip().isdigit():
                cleaned = tag_re.sub("", line)
                if cleaned.strip():
                    text_lines.append(cleaned.strip())

        if time_match is not None and text_lines:
            text = _clean_text(" ".join(text_lines))
            if text:
                segments.append(Segment(time=time_match, text=text))

    return _merge_segments(_deduplicate_segments(segments))


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _deduplicate_segments(segments: list[Segment]) -> list[Segment]:
    if not segments:
        return segments
    deduped: list[Segment] = [segments[0]]
    for seg in segments[1:]:
        if seg.text != deduped[-1].text:
            deduped.append(seg)
    return deduped


def _merge_segments(segments: list[Segment], gap_threshold: int = 2) -> list[Segment]:
    if not segments:
        return segments
    merged: list[Segment] = [segments[0]]
    for seg in segments[1:]:
        prev = merged[-1]
        if seg.time - prev.time <= gap_threshold:
            merged[-1] = Segment(time=prev.time, text=f"{prev.text} {seg.text}")
        else:
            merged.append(seg)
    return merged


def extract_chapters(description: str) -> list[Chapter]:
    chapter_re = re.compile(r"^(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$", re.MULTILINE)
    chapters = []
    for match in chapter_re.finditer(description):
        time_str, title = match.group(1), match.group(2)
        parts = time_str.split(":")
        if len(parts) == 3:
            seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        else:
            seconds = int(parts[0]) * 60 + int(parts[1])
        chapters.append(Chapter(time=seconds, title=title.strip()))
    return chapters


def extract_video(video_id: str, channel_name: str, channel_slug: str, language: str = "en") -> VideoTranscript:
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    metadata = extract_metadata(video_url)

    subtitle_content, caption_type = extract_subtitles(video_url, language)

    segments: list[Segment] = []
    has_captions = subtitle_content is not None
    if subtitle_content:
        if caption_type and "srt" in caption_type:
            segments = parse_srt(subtitle_content)
        else:
            segments = parse_vtt(subtitle_content)

    description = metadata.get("description", "") or ""
    chapters = extract_chapters(description)

    upload_date = metadata.get("upload_date", "")
    if upload_date and len(upload_date) == 8:
        date_str = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    else:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return VideoTranscript(
        id=video_id,
        title=metadata.get("title", "Unknown"),
        channel=channel_name,
        channel_slug=channel_slug,
        date=date_str,
        duration=metadata.get("duration", 0) or 0,
        url=video_url,
        description=description,
        has_captions=has_captions,
        caption_type=caption_type,
        language=language,
        segments=segments,
        chapters=chapters,
        extracted_at=datetime.now(timezone.utc).isoformat(),
    )
