import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.config import Channel
from scripts.extractor import PermanentError, TransientError, VideoTranscript
from scripts.scrape import (
    REPO_ROOT,
    fetch_video_ids,
    git_commit_and_push,
    process_channel,
    run,
)
from scripts.state import ChannelState


class TestFetchVideoIds:
    @patch("scripts.scrape.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="abc123\ndef456\nghi789\n", stderr="")
        ids = fetch_video_ids("UCxxxxxxxxxxxxxxxxxxxxxx")
        assert ids == ["abc123", "def456", "ghi789"]

    @patch("scripts.scrape.subprocess.run")
    def test_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        ids = fetch_video_ids("UCxxxxxxxxxxxxxxxxxxxxxx")
        assert ids == []

    @patch("scripts.scrape.subprocess.run")
    def test_empty_output(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        ids = fetch_video_ids("UCxxxxxxxxxxxxxxxxxxxxxx")
        assert ids == []

    @patch("scripts.scrape.subprocess.run")
    def test_strips_whitespace(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="  abc123  \n  def456  \n", stderr="")
        ids = fetch_video_ids("UCxxxxxxxxxxxxxxxxxxxxxx")
        assert ids == ["abc123", "def456"]


class TestProcessChannel:
    def _channel(self, slug="test-channel", max_duration=None):
        return Channel(id="UCxxxxxxxxxxxxxxxxxxxxxx", name="Test Channel", slug=slug, max_duration=max_duration)

    def _transcript(self, video_id="v1", duration=600):
        return VideoTranscript(
            id=video_id,
            title="Test",
            channel="Test Channel",
            channel_slug="test-channel",
            date="2024-01-15",
            duration=duration,
            url=f"https://youtube.com/watch?v={video_id}",
            description="",
            has_captions=True,
            caption_type="manual",
            language="en",
            segments=[],
            chapters=[],
            extracted_at="2024-01-01T00:00:00Z",
        )

    @patch("scripts.scrape.extract_video")
    @patch("scripts.scrape.fetch_video_ids")
    def test_no_new_videos(self, mock_fetch, mock_extract):
        mock_fetch.return_value = ["v1", "v2"]
        state = ChannelState(video_ids=["v1", "v2"])
        success, fail = process_channel(self._channel(), state)
        assert success == 0
        assert fail == 0
        mock_extract.assert_not_called()

    @patch("scripts.scrape.TRANSCRIPTS_DIR")
    @patch("scripts.scrape.extract_video")
    @patch("scripts.scrape.fetch_video_ids")
    def test_new_video_extracted(self, mock_fetch, mock_extract, mock_dir, tmp_path):
        mock_dir.__truediv__ = lambda self, x: tmp_path / x
        mock_fetch.return_value = ["v1", "v2"]
        mock_extract.return_value = self._transcript("v2")
        state = ChannelState(video_ids=["v1"])

        (tmp_path / "test-channel").mkdir(parents=True, exist_ok=True)
        success, fail = process_channel(self._channel(), state)
        assert success == 1
        assert fail == 0
        assert "v2" in state.video_ids

    @patch("scripts.scrape.TRANSCRIPTS_DIR")
    @patch("scripts.scrape.extract_video")
    @patch("scripts.scrape.fetch_video_ids")
    def test_permanent_error_marks_video(self, mock_fetch, mock_extract, mock_dir, tmp_path):
        mock_dir.__truediv__ = lambda self, x: tmp_path / x
        mock_fetch.return_value = ["v1"]
        mock_extract.side_effect = PermanentError("Private video")
        state = ChannelState()

        success, fail = process_channel(self._channel(), state)
        assert success == 0
        assert fail == 1
        assert "v1" in state.video_ids

    @patch("scripts.scrape.extract_video")
    @patch("scripts.scrape.fetch_video_ids")
    def test_transient_error_does_not_mark(self, mock_fetch, mock_extract):
        mock_fetch.return_value = ["v1"]
        mock_extract.side_effect = TransientError("HTTP Error 429")
        state = ChannelState()

        success, fail = process_channel(self._channel(), state)
        assert success == 0
        assert fail == 1
        assert "v1" not in state.video_ids

    @patch("scripts.scrape.extract_video")
    @patch("scripts.scrape.fetch_video_ids")
    def test_unexpected_error(self, mock_fetch, mock_extract):
        mock_fetch.return_value = ["v1"]
        mock_extract.side_effect = RuntimeError("boom")
        state = ChannelState()

        success, fail = process_channel(self._channel(), state)
        assert success == 0
        assert fail == 1
        assert "v1" not in state.video_ids

    @patch("scripts.scrape.TRANSCRIPTS_DIR")
    @patch("scripts.scrape.extract_video")
    @patch("scripts.scrape.fetch_video_ids")
    def test_max_duration_skips(self, mock_fetch, mock_extract, mock_dir, tmp_path):
        mock_dir.__truediv__ = lambda self, x: tmp_path / x
        mock_fetch.return_value = ["v1"]
        mock_extract.return_value = self._transcript("v1", duration=9000)
        state = ChannelState()

        success, fail = process_channel(self._channel(max_duration=3600), state)
        assert success == 0
        assert fail == 0
        assert "v1" in state.video_ids


class TestGitCommitAndPush:
    @patch("scripts.scrape.subprocess.run")
    def test_no_changes(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git add
            MagicMock(returncode=0),  # git diff --cached --quiet (no changes)
        ]
        result = git_commit_and_push()
        assert result is False

    @patch("scripts.scrape.subprocess.run")
    def test_commit_and_push_success(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git add
            MagicMock(returncode=1),  # git diff --cached --quiet (has changes)
            MagicMock(returncode=0),  # git commit
            MagicMock(returncode=0),  # git push
        ]
        result = git_commit_and_push()
        assert result is True

    @patch("scripts.scrape.subprocess.run")
    def test_commit_fails(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git add
            MagicMock(returncode=1),  # git diff (has changes)
            subprocess.CalledProcessError(1, "git commit", stderr=b"error"),
        ]
        result = git_commit_and_push()
        assert result is False


class TestRun:
    @patch("scripts.scrape.git_commit_and_push")
    @patch("scripts.scrape.generate_manifest")
    @patch("scripts.scrape.process_channel")
    def test_no_channels(self, mock_process, mock_manifest, mock_git, tmp_path):
        config_file = tmp_path / "channels.yaml"
        config_file.write_text("channels: []\n")
        state_file = tmp_path / "state.json"
        state_file.write_text('{"last_run": null, "channels": {}}')

        run(config_path=config_file, state_path=state_file)
        mock_process.assert_not_called()
        mock_manifest.assert_not_called()

    @patch("scripts.scrape.git_commit_and_push")
    @patch("scripts.scrape.generate_manifest")
    @patch("scripts.scrape.process_channel")
    def test_with_channel(self, mock_process, mock_manifest, mock_git, tmp_path):
        import yaml

        config_file = tmp_path / "channels.yaml"
        config_file.write_text(
            yaml.dump({"channels": [{"id": "UCxxxxxxxxxxxxxxxxxxxxxx", "name": "Test", "slug": "test"}]})
        )
        state_file = tmp_path / "state.json"
        state_file.write_text('{"last_run": null, "channels": {}}')

        mock_process.return_value = (2, 0)
        run(config_path=config_file, state_path=state_file)

        mock_process.assert_called_once()
        mock_manifest.assert_called_once()
        mock_git.assert_called_once()

    @patch("scripts.scrape.git_commit_and_push")
    @patch("scripts.scrape.generate_manifest")
    @patch("scripts.scrape.process_channel")
    def test_no_success_skips_git(self, mock_process, mock_manifest, mock_git, tmp_path):
        import yaml

        config_file = tmp_path / "channels.yaml"
        config_file.write_text(
            yaml.dump({"channels": [{"id": "UCxxxxxxxxxxxxxxxxxxxxxx", "name": "Test", "slug": "test"}]})
        )
        state_file = tmp_path / "state.json"
        state_file.write_text('{"last_run": null, "channels": {}}')

        mock_process.return_value = (0, 1)
        run(config_path=config_file, state_path=state_file)

        mock_manifest.assert_called_once()
        mock_git.assert_not_called()

    @patch("scripts.scrape.git_commit_and_push")
    @patch("scripts.scrape.generate_manifest")
    @patch("scripts.scrape.process_channel")
    def test_state_saved(self, mock_process, mock_manifest, mock_git, tmp_path):
        import yaml

        config_file = tmp_path / "channels.yaml"
        config_file.write_text(
            yaml.dump({"channels": [{"id": "UCxxxxxxxxxxxxxxxxxxxxxx", "name": "Test", "slug": "test"}]})
        )
        state_file = tmp_path / "state.json"
        state_file.write_text('{"last_run": null, "channels": {}}')

        mock_process.return_value = (0, 0)
        run(config_path=config_file, state_path=state_file)

        data = json.loads(state_file.read_text())
        assert data["last_run"] is not None


class TestMain:
    @patch("scripts.scrape.run")
    def test_main_calls_run(self, mock_run):
        from scripts.scrape import main

        main()
        mock_run.assert_called_once()

