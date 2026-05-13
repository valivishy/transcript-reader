import json
from pathlib import Path

import pytest

from scripts.manifest_gen import _load_transcript, generate_manifest


def _make_transcript_json(video_id: str, title: str, channel: str, channel_slug: str, date: str) -> str:
    return json.dumps(
        {
            "id": video_id,
            "title": title,
            "channel": channel,
            "channel_slug": channel_slug,
            "date": date,
            "duration": 600,
            "url": f"https://youtube.com/watch?v={video_id}",
            "description": "",
            "has_captions": True,
            "caption_type": "manual",
            "language": "en",
            "segments": [{"time": 0, "text": "Hello"}],
            "chapters": [],
            "extracted_at": "2024-01-01T00:00:00Z",
        }
    )


class TestGenerateManifest:
    def test_empty_directory(self, tmp_path):
        transcripts_dir = tmp_path / "transcripts"
        transcripts_dir.mkdir()
        output = tmp_path / "manifest.json"

        manifest = generate_manifest(transcripts_dir, output)
        assert manifest["count"] == 0
        assert manifest["videos"] == []
        assert output.exists()

    def test_single_channel(self, tmp_path):
        transcripts_dir = tmp_path / "transcripts"
        channel_dir = transcripts_dir / "test-channel"
        channel_dir.mkdir(parents=True)

        (channel_dir / "2024-01-15_abc123.json").write_text(
            _make_transcript_json("abc123", "Video One", "Test Channel", "test-channel", "2024-01-15")
        )
        output = tmp_path / "manifest.json"

        manifest = generate_manifest(transcripts_dir, output)
        assert manifest["count"] == 1
        assert manifest["videos"][0]["id"] == "abc123"
        assert manifest["videos"][0]["path"] == "transcripts/test-channel/2024-01-15_abc123.json"

    def test_multiple_channels_sorted_by_date(self, tmp_path):
        transcripts_dir = tmp_path / "transcripts"
        ch1 = transcripts_dir / "channel-a"
        ch2 = transcripts_dir / "channel-b"
        ch1.mkdir(parents=True)
        ch2.mkdir(parents=True)

        (ch1 / "2024-01-10_v1.json").write_text(
            _make_transcript_json("v1", "Old Video", "A", "channel-a", "2024-01-10")
        )
        (ch2 / "2024-01-20_v2.json").write_text(
            _make_transcript_json("v2", "New Video", "B", "channel-b", "2024-01-20")
        )
        output = tmp_path / "manifest.json"

        manifest = generate_manifest(transcripts_dir, output)
        assert manifest["count"] == 2
        assert manifest["videos"][0]["date"] == "2024-01-20"
        assert manifest["videos"][1]["date"] == "2024-01-10"

    def test_skips_invalid_json(self, tmp_path):
        transcripts_dir = tmp_path / "transcripts"
        channel_dir = transcripts_dir / "channel"
        channel_dir.mkdir(parents=True)

        (channel_dir / "bad.json").write_text("not valid json{{{")
        (channel_dir / "2024-01-15_good.json").write_text(
            _make_transcript_json("good", "Good", "Ch", "channel", "2024-01-15")
        )
        output = tmp_path / "manifest.json"

        manifest = generate_manifest(transcripts_dir, output)
        assert manifest["count"] == 1

    def test_skips_non_directory_files(self, tmp_path):
        transcripts_dir = tmp_path / "transcripts"
        transcripts_dir.mkdir()
        (transcripts_dir / "readme.txt").write_text("ignore me")
        output = tmp_path / "manifest.json"

        manifest = generate_manifest(transcripts_dir, output)
        assert manifest["count"] == 0

    def test_output_has_generated_at(self, tmp_path):
        transcripts_dir = tmp_path / "transcripts"
        transcripts_dir.mkdir()
        output = tmp_path / "manifest.json"

        manifest = generate_manifest(transcripts_dir, output)
        assert "generated_at" in manifest


class TestLoadTranscript:
    def test_valid_transcript(self, tmp_path):
        f = tmp_path / "t.json"
        f.write_text(_make_transcript_json("id1", "Title", "Ch", "ch", "2024-01-01"))
        result = _load_transcript(f)
        assert result is not None
        assert result.id == "id1"

    def test_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{{not json}}")
        assert _load_transcript(f) is None

    def test_invalid_schema(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text(json.dumps({"id": "x"}))
        assert _load_transcript(f) is None
