import pytest
import yaml
from pathlib import Path

from scripts.config import Channel, ChannelsConfig, load_config


class TestChannel:
    def test_valid_channel(self):
        ch = Channel(id="UCxxxxxxxxxxxxxxxxxxxxxx", name="Test", slug="test-channel")
        assert ch.id == "UCxxxxxxxxxxxxxxxxxxxxxx"
        assert ch.language == "en"
        assert ch.max_duration is None

    def test_invalid_channel_id_wrong_prefix(self):
        with pytest.raises(ValueError, match="Invalid channel ID"):
            Channel(id="ABxxxxxxxxxxxxxxxxxxxxxx", name="Test", slug="test")

    def test_invalid_channel_id_wrong_length(self):
        with pytest.raises(ValueError, match="Invalid channel ID"):
            Channel(id="UCshort", name="Test", slug="test")

    def test_invalid_slug_uppercase(self):
        with pytest.raises(ValueError, match="Invalid slug"):
            Channel(id="UCxxxxxxxxxxxxxxxxxxxxxx", name="Test", slug="Test-Channel")

    def test_invalid_slug_underscore(self):
        with pytest.raises(ValueError, match="Invalid slug"):
            Channel(id="UCxxxxxxxxxxxxxxxxxxxxxx", name="Test", slug="test_channel")

    def test_valid_slug_single_word(self):
        ch = Channel(id="UCxxxxxxxxxxxxxxxxxxxxxx", name="Test", slug="test")
        assert ch.slug == "test"

    def test_custom_language_and_duration(self):
        ch = Channel(id="UCxxxxxxxxxxxxxxxxxxxxxx", name="Test", slug="test", language="de", max_duration=3600)
        assert ch.language == "de"
        assert ch.max_duration == 3600


class TestChannelsConfig:
    def test_valid_config(self):
        config = ChannelsConfig(
            channels=[
                Channel(id="UCxxxxxxxxxxxxxxxxxxxxxx", name="A", slug="channel-a"),
                Channel(id="UCyyyyyyyyyyyyyyyyyyyyyy", name="B", slug="channel-b"),
            ]
        )
        assert len(config.channels) == 2

    def test_duplicate_slugs(self):
        with pytest.raises(ValueError, match="Duplicate channel slugs"):
            ChannelsConfig(
                channels=[
                    Channel(id="UCxxxxxxxxxxxxxxxxxxxxxx", name="A", slug="same"),
                    Channel(id="UCyyyyyyyyyyyyyyyyyyyyyy", name="B", slug="same"),
                ]
            )

    def test_empty_channels(self):
        config = ChannelsConfig(channels=[])
        assert config.channels == []


class TestLoadConfig:
    def test_load_valid_yaml(self, tmp_path):
        config_file = tmp_path / "channels.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "channels": [
                        {"id": "UCxxxxxxxxxxxxxxxxxxxxxx", "name": "Test", "slug": "test"},
                    ]
                }
            )
        )
        config = load_config(config_file)
        assert len(config.channels) == 1
        assert config.channels[0].name == "Test"

    def test_load_empty_channels(self, tmp_path):
        config_file = tmp_path / "channels.yaml"
        config_file.write_text(yaml.dump({"channels": []}))
        config = load_config(config_file)
        assert config.channels == []

    def test_load_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_load_invalid_yaml(self, tmp_path):
        config_file = tmp_path / "channels.yaml"
        config_file.write_text("channels: not_a_list")
        with pytest.raises(ValueError):
            load_config(config_file)
