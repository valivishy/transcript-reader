import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.state import ChannelState, ScrapeState, load_state, save_state


class TestChannelState:
    def test_defaults(self):
        cs = ChannelState()
        assert cs.last_checked is None
        assert cs.video_ids == []

    def test_with_values(self):
        cs = ChannelState(last_checked="2024-01-01T00:00:00Z", video_ids=["abc", "def"])
        assert cs.last_checked == "2024-01-01T00:00:00Z"
        assert len(cs.video_ids) == 2


class TestScrapeState:
    def test_defaults(self):
        ss = ScrapeState()
        assert ss.last_run is None
        assert ss.channels == {}

    def test_with_channels(self):
        ss = ScrapeState(channels={"test": ChannelState(video_ids=["v1"])})
        assert "test" in ss.channels
        assert ss.channels["test"].video_ids == ["v1"]


class TestLoadState:
    def test_valid_state(self, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text(
            json.dumps({"last_run": "2024-01-01T00:00:00Z", "channels": {"ch1": {"video_ids": ["a", "b"]}}})
        )
        state = load_state(state_file)
        assert state.last_run == "2024-01-01T00:00:00Z"
        assert state.channels["ch1"].video_ids == ["a", "b"]

    def test_missing_file(self, tmp_path):
        state = load_state(tmp_path / "nonexistent.json")
        assert state.last_run is None
        assert state.channels == {}

    def test_invalid_json(self, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text("not json{{{")
        state = load_state(state_file)
        assert state.last_run is None

    def test_invalid_schema(self, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"last_run": 12345, "channels": "not_a_dict"}))
        state = load_state(state_file)
        assert state.last_run is None


class TestSaveState:
    def test_saves_json(self, tmp_path):
        state_file = tmp_path / "state.json"
        state = ScrapeState(channels={"ch1": ChannelState(video_ids=["v1"])})
        save_state(state, state_file)

        data = json.loads(state_file.read_text())
        assert data["channels"]["ch1"]["video_ids"] == ["v1"]
        assert data["last_run"] is not None

    def test_updates_last_run(self, tmp_path):
        state_file = tmp_path / "state.json"
        state = ScrapeState()
        assert state.last_run is None
        save_state(state, state_file)
        assert state.last_run is not None

    def test_overwrites_existing(self, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"last_run": "old", "channels": {}}))

        state = ScrapeState(channels={"new": ChannelState()})
        save_state(state, state_file)

        data = json.loads(state_file.read_text())
        assert "new" in data["channels"]
