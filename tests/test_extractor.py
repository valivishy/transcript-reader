import json
import subprocess
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from scripts.extractor import (
    Chapter,
    ExtractionError,
    PermanentError,
    Segment,
    TransientError,
    VideoTranscript,
    _clean_text,
    _deduplicate_segments,
    _merge_segments,
    classify_error,
    extract_chapters,
    extract_metadata,
    extract_subtitles,
    extract_video,
    parse_srt,
    parse_vtt,
)


class TestClassifyError:
    def test_permanent_age_restricted(self):
        err = classify_error("Sign in to confirm your age")
        assert isinstance(err, PermanentError)

    def test_permanent_members_only(self):
        err = classify_error("This is members only content")
        assert isinstance(err, PermanentError)

    def test_permanent_private(self):
        err = classify_error("Private video. Sign in if you've been granted access.")
        assert isinstance(err, PermanentError)

    def test_permanent_unavailable(self):
        err = classify_error("Video unavailable")
        assert isinstance(err, PermanentError)

    def test_permanent_country(self):
        err = classify_error("This video is not available in your country")
        assert isinstance(err, PermanentError)

    def test_permanent_not_available(self):
        err = classify_error("The content is not available")
        assert isinstance(err, PermanentError)

    def test_permanent_join_channel(self):
        err = classify_error("Join this channel to access")
        assert isinstance(err, PermanentError)

    def test_transient_rate_limit(self):
        err = classify_error("HTTP Error 429: Too Many Requests")
        assert isinstance(err, TransientError)

    def test_transient_connection_refused(self):
        err = classify_error("Connection refused by server")
        assert isinstance(err, TransientError)

    def test_transient_timeout(self):
        err = classify_error("Request timed out")
        assert isinstance(err, TransientError)

    def test_transient_connection_reset(self):
        err = classify_error("Connection reset by peer")
        assert isinstance(err, TransientError)

    def test_transient_server_error(self):
        err = classify_error("HTTP Error 503: Service Unavailable")
        assert isinstance(err, TransientError)

    def test_transient_unable_to_download(self):
        err = classify_error("Unable to download webpage")
        assert isinstance(err, TransientError)

    def test_unknown_error(self):
        err = classify_error("Some unknown error message")
        assert isinstance(err, ExtractionError)
        assert not isinstance(err, PermanentError)
        assert not isinstance(err, TransientError)

    def test_case_insensitive(self):
        err = classify_error("SIGN IN TO CONFIRM YOUR AGE")
        assert isinstance(err, PermanentError)

    def test_strips_whitespace(self):
        err = classify_error("  Video unavailable  \n")
        assert isinstance(err, PermanentError)
        assert str(err) == "Video unavailable"


class TestExtractMetadata:
    @patch("scripts.extractor.subprocess.run")
    def test_success(self, mock_run):
        metadata = {"title": "Test Video", "duration": 300}
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(metadata), stderr="")
        result = extract_metadata("https://youtube.com/watch?v=test123")
        assert result == metadata
        mock_run.assert_called_once()

    @patch("scripts.extractor.subprocess.run")
    def test_failure_permanent(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Private video")
        with pytest.raises(PermanentError):
            extract_metadata("https://youtube.com/watch?v=test123")

    @patch("scripts.extractor.subprocess.run")
    def test_failure_transient(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="HTTP Error 429")
        with pytest.raises(TransientError):
            extract_metadata("https://youtube.com/watch?v=test123")


class TestExtractSubtitles:
    @patch("scripts.extractor.subprocess.run")
    def test_no_captions(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="no subtitles are available")
        content, caption_type = extract_subtitles("https://youtube.com/watch?v=test", "en")
        assert content is None
        assert caption_type is None

    @patch("scripts.extractor.subprocess.run")
    def test_error_raises(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="Private video")
        with pytest.raises(PermanentError):
            extract_subtitles("https://youtube.com/watch?v=test", "en")

    @patch("scripts.extractor.subprocess.run")
    def test_vtt_found(self, mock_run, tmp_path):
        def side_effect(cmd, **kwargs):
            output_dir = None
            for i, arg in enumerate(cmd):
                if arg == "-o":
                    output_dir = cmd[i + 1].split("/%(id)s")[0]
                    break
            if output_dir:
                vtt_path = Path(output_dir) / "test123.en.vtt"
                vtt_path.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello world\n")
            return MagicMock(returncode=0, stderr="")

        mock_run.side_effect = side_effect
        content, caption_type = extract_subtitles("https://youtube.com/watch?v=test123", "en")
        assert content is not None
        assert "Hello world" in content
        assert caption_type == "manual"

    @patch("scripts.extractor.subprocess.run")
    def test_auto_caption_detected(self, mock_run, tmp_path):
        def side_effect(cmd, **kwargs):
            output_dir = None
            for i, arg in enumerate(cmd):
                if arg == "-o":
                    output_dir = cmd[i + 1].split("/%(id)s")[0]
                    break
            if output_dir:
                vtt_path = Path(output_dir) / "test123.auto.en.vtt"
                vtt_path.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nAuto caption\n")
            return MagicMock(returncode=0, stderr="")

        mock_run.side_effect = side_effect
        content, caption_type = extract_subtitles("https://youtube.com/watch?v=test123", "en")
        assert caption_type == "auto"

    @patch("scripts.extractor.subprocess.run")
    def test_no_subtitle_files_found(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        content, caption_type = extract_subtitles("https://youtube.com/watch?v=test", "en")
        assert content is None
        assert caption_type is None

    @patch("scripts.extractor.subprocess.run")
    def test_srt_found(self, mock_run, tmp_path):
        def side_effect(cmd, **kwargs):
            output_dir = None
            for i, arg in enumerate(cmd):
                if arg == "-o":
                    output_dir = cmd[i + 1].split("/%(id)s")[0]
                    break
            if output_dir:
                srt_path = Path(output_dir) / "test123.en.srt"
                srt_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello SRT\n")
            return MagicMock(returncode=0, stderr="")

        mock_run.side_effect = side_effect
        content, caption_type = extract_subtitles("https://youtube.com/watch?v=test123", "en")
        assert content is not None
        assert "Hello SRT" in content
        assert caption_type == "manual"


from pathlib import Path


class TestParseVtt:
    def test_basic_vtt(self):
        content = """WEBVTT

00:00:01.000 --> 00:00:04.000
Hello world

00:00:05.000 --> 00:00:08.000
Second segment
"""
        segments = parse_vtt(content)
        assert len(segments) >= 1
        assert segments[0].time == 1
        assert "Hello world" in segments[0].text

    def test_strips_html_tags(self):
        content = """WEBVTT

00:00:01.000 --> 00:00:04.000
<c.colorE5E5E5>Hello</c> <c.colorCCCCCC>world</c>
"""
        segments = parse_vtt(content)
        assert "<c" not in segments[0].text
        assert "Hello" in segments[0].text

    def test_deduplicates(self):
        content = """WEBVTT

00:00:01.000 --> 00:00:02.000
Same text

00:00:02.000 --> 00:00:03.000
Same text

00:00:04.000 --> 00:00:05.000
Different text
"""
        segments = parse_vtt(content)
        texts = [s.text for s in segments]
        assert texts.count("Same text") <= 1

    def test_merges_close_segments(self):
        content = """WEBVTT

00:00:01.000 --> 00:00:02.000
Part one

00:00:02.000 --> 00:00:03.000
Part two

00:00:10.000 --> 00:00:11.000
Far away
"""
        segments = parse_vtt(content)
        assert any("Part one" in s.text and "Part two" in s.text for s in segments)

    def test_empty_content(self):
        segments = parse_vtt("WEBVTT\n\n")
        assert segments == []

    def test_skips_note_lines(self):
        content = """WEBVTT

NOTE This is a comment

00:00:01.000 --> 00:00:02.000
Actual content
"""
        segments = parse_vtt(content)
        assert all("NOTE" not in s.text for s in segments)

    def test_multiline_cue(self):
        content = """WEBVTT

00:00:01.000 --> 00:00:04.000
Line one
Line two
"""
        segments = parse_vtt(content)
        assert "Line one" in segments[0].text
        assert "Line two" in segments[0].text


class TestParseSrt:
    def test_basic_srt(self):
        content = """1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:05,000 --> 00:00:08,000
Second segment
"""
        segments = parse_srt(content)
        assert len(segments) >= 1
        assert segments[0].time == 1

    def test_strips_html_tags(self):
        content = """1
00:00:01,000 --> 00:00:04,000
<b>Bold text</b>
"""
        segments = parse_srt(content)
        assert "<b>" not in segments[0].text
        assert "Bold text" in segments[0].text

    def test_skips_sequence_numbers(self):
        content = """1
00:00:01,000 --> 00:00:04,000
Text here

2
00:00:05,000 --> 00:00:08,000
More text
"""
        segments = parse_srt(content)
        assert all(s.text not in ("1", "2") for s in segments)

    def test_empty_blocks(self):
        segments = parse_srt("")
        assert segments == []

    def test_multiline_text(self):
        content = """1
00:00:01,000 --> 00:00:04,000
Line one
Line two
"""
        segments = parse_srt(content)
        assert "Line one" in segments[0].text
        assert "Line two" in segments[0].text


class TestCleanText:
    def test_collapses_whitespace(self):
        assert _clean_text("hello   world") == "hello world"

    def test_strips_edges(self):
        assert _clean_text("  hello  ") == "hello"

    def test_handles_newlines(self):
        assert _clean_text("hello\n\nworld") == "hello world"


class TestDeduplicateSegments:
    def test_empty(self):
        assert _deduplicate_segments([]) == []

    def test_no_duplicates(self):
        segs = [Segment(time=0, text="a"), Segment(time=5, text="b")]
        assert _deduplicate_segments(segs) == segs

    def test_consecutive_duplicates(self):
        segs = [Segment(time=0, text="a"), Segment(time=1, text="a"), Segment(time=5, text="b")]
        result = _deduplicate_segments(segs)
        assert len(result) == 2
        assert result[0].text == "a"
        assert result[1].text == "b"

    def test_non_consecutive_duplicates_kept(self):
        segs = [Segment(time=0, text="a"), Segment(time=3, text="b"), Segment(time=6, text="a")]
        result = _deduplicate_segments(segs)
        assert len(result) == 3


class TestMergeSegments:
    def test_empty(self):
        assert _merge_segments([]) == []

    def test_close_segments_merged(self):
        segs = [Segment(time=0, text="a"), Segment(time=1, text="b")]
        result = _merge_segments(segs)
        assert len(result) == 1
        assert result[0].text == "a b"

    def test_far_segments_not_merged(self):
        segs = [Segment(time=0, text="a"), Segment(time=10, text="b")]
        result = _merge_segments(segs)
        assert len(result) == 2

    def test_custom_threshold(self):
        segs = [Segment(time=0, text="a"), Segment(time=5, text="b")]
        result = _merge_segments(segs, gap_threshold=5)
        assert len(result) == 1

    def test_chain_merging(self):
        segs = [Segment(time=0, text="a"), Segment(time=1, text="b"), Segment(time=2, text="c")]
        result = _merge_segments(segs)
        assert len(result) == 1
        assert result[0].text == "a b c"


class TestExtractChapters:
    def test_basic_chapters(self):
        desc = "0:00 Introduction\n2:30 Main Topic\n10:00 Conclusion"
        chapters = extract_chapters(desc)
        assert len(chapters) == 3
        assert chapters[0] == Chapter(time=0, title="Introduction")
        assert chapters[1] == Chapter(time=150, title="Main Topic")
        assert chapters[2] == Chapter(time=600, title="Conclusion")

    def test_hours_format(self):
        desc = "1:00:00 Chapter One\n2:30:00 Chapter Two"
        chapters = extract_chapters(desc)
        assert chapters[0].time == 3600
        assert chapters[1].time == 9000

    def test_no_chapters(self):
        desc = "This is just a normal description\nwith no timestamps"
        chapters = extract_chapters(desc)
        assert chapters == []

    def test_mixed_content(self):
        desc = "Subscribe!\n\n0:00 Start\n5:30 Middle\n\nFollow me on twitter"
        chapters = extract_chapters(desc)
        assert len(chapters) == 2


class TestExtractVideo:
    @patch("scripts.extractor.extract_subtitles")
    @patch("scripts.extractor.extract_metadata")
    def test_full_extraction(self, mock_metadata, mock_subtitles):
        mock_metadata.return_value = {
            "title": "Test Video",
            "duration": 600,
            "upload_date": "20240115",
            "description": "0:00 Intro\n5:00 Main",
        }
        mock_subtitles.return_value = (
            "WEBVTT\n\n00:00:01.000 --> 00:00:04.000\nHello world\n",
            "manual",
        )

        result = extract_video("abc123", "Channel", "channel-slug", "en")

        assert isinstance(result, VideoTranscript)
        assert result.id == "abc123"
        assert result.title == "Test Video"
        assert result.channel == "Channel"
        assert result.channel_slug == "channel-slug"
        assert result.date == "2024-01-15"
        assert result.duration == 600
        assert result.has_captions is True
        assert result.caption_type == "manual"
        assert len(result.chapters) == 2
        assert len(result.segments) >= 1

    @patch("scripts.extractor.extract_subtitles")
    @patch("scripts.extractor.extract_metadata")
    def test_no_captions(self, mock_metadata, mock_subtitles):
        mock_metadata.return_value = {
            "title": "No Subs",
            "duration": 100,
            "upload_date": "20240101",
            "description": "",
        }
        mock_subtitles.return_value = (None, None)

        result = extract_video("xyz789", "Ch", "ch", "en")
        assert result.has_captions is False
        assert result.segments == []
        assert result.caption_type is None

    @patch("scripts.extractor.extract_subtitles")
    @patch("scripts.extractor.extract_metadata")
    def test_missing_upload_date(self, mock_metadata, mock_subtitles):
        mock_metadata.return_value = {"title": "T", "duration": 0, "upload_date": "", "description": ""}
        mock_subtitles.return_value = (None, None)

        result = extract_video("v1", "C", "c", "en")
        assert len(result.date) == 10  # YYYY-MM-DD format

    @patch("scripts.extractor.extract_subtitles")
    @patch("scripts.extractor.extract_metadata")
    def test_none_description(self, mock_metadata, mock_subtitles):
        mock_metadata.return_value = {"title": "T", "duration": 0, "upload_date": "20240101", "description": None}
        mock_subtitles.return_value = (None, None)

        result = extract_video("v1", "C", "c", "en")
        assert result.description == ""
        assert result.chapters == []

    @patch("scripts.extractor.extract_subtitles")
    @patch("scripts.extractor.extract_metadata")
    def test_none_duration(self, mock_metadata, mock_subtitles):
        mock_metadata.return_value = {"title": "T", "duration": None, "upload_date": "20240101", "description": ""}
        mock_subtitles.return_value = (None, None)

        result = extract_video("v1", "C", "c", "en")
        assert result.duration == 0

    @patch("scripts.extractor.extract_subtitles")
    @patch("scripts.extractor.extract_metadata")
    def test_srt_subtitles(self, mock_metadata, mock_subtitles):
        mock_metadata.return_value = {"title": "T", "duration": 60, "upload_date": "20240101", "description": ""}
        mock_subtitles.return_value = (
            "1\n00:00:01,000 --> 00:00:04,000\nSRT content\n",
            "srt",
        )

        result = extract_video("v1", "C", "c", "en")
        assert result.has_captions is True
        assert len(result.segments) >= 1
