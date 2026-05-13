import json
import logging
import subprocess
import sys
from pathlib import Path

from .config import Channel, load_config
from .extractor import PermanentError, TransientError, extract_video
from .manifest_gen import generate_manifest
from .state import ChannelState, load_state, save_state

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS_DIR = REPO_ROOT / "transcripts"
MANIFEST_PATH = REPO_ROOT / "manifest.json"
CONFIG_PATH = REPO_ROOT / "channels.yaml"
STATE_PATH = REPO_ROOT / "state.json"


def fetch_video_ids(channel_id: str, max_results: int = 10) -> list[str]:
    result = subprocess.run(
        [
            "yt-dlp",
            "--flat-playlist",
            "--print",
            "id",
            "--playlist-end",
            str(max_results),
            "--no-warnings",
            f"https://www.youtube.com/channel/{channel_id}/videos",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        logger.warning("Failed to fetch videos for %s: %s", channel_id, result.stderr.strip())
        return []
    return [vid.strip() for vid in result.stdout.strip().split("\n") if vid.strip()]


def process_channel(channel: Channel, state: ChannelState) -> tuple[int, int]:
    video_ids = fetch_video_ids(channel.id)
    new_ids = [vid for vid in video_ids if vid not in state.video_ids]

    if not new_ids:
        logger.info("No new videos for %s", channel.name)
        return 0, 0

    logger.info("Found %d new videos for %s", len(new_ids), channel.name)
    success_count = 0
    fail_count = 0

    for video_id in new_ids:
        try:
            transcript = extract_video(video_id, channel.name, channel.slug, channel.language)

            if channel.max_duration and transcript.duration > channel.max_duration:
                logger.info("Skipping %s (duration %ds exceeds max %ds)", video_id, transcript.duration, channel.max_duration)
                state.video_ids.append(video_id)
                continue

            output_dir = TRANSCRIPTS_DIR / channel.slug
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{transcript.date}_{video_id}.json"
            output_file.write_text(json.dumps(transcript.model_dump(), indent=2) + "\n")

            state.video_ids.append(video_id)
            success_count += 1
            logger.info("Extracted: %s - %s", video_id, transcript.title)

        except PermanentError as e:
            logger.warning("Permanent error for %s: %s", video_id, e)
            state.video_ids.append(video_id)
            fail_count += 1

        except TransientError as e:
            logger.warning("Transient error for %s (will retry next run): %s", video_id, e)
            fail_count += 1

        except Exception as e:
            logger.error("Unexpected error for %s: %s", video_id, e)
            fail_count += 1

    return success_count, fail_count


def git_commit_and_push() -> bool:
    try:
        subprocess.run(["git", "add", "transcripts/", "manifest.json", "state.json"], cwd=REPO_ROOT, check=True, capture_output=True)

        result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT, capture_output=True)
        if result.returncode == 0:
            logger.info("No changes to commit")
            return False

        subprocess.run(
            ["git", "commit", "-m", "chore: update transcripts"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "push"], cwd=REPO_ROOT, check=True, capture_output=True)
        logger.info("Committed and pushed")
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Git operation failed: %s", e.stderr.decode() if e.stderr else str(e))
        return False


def run(config_path: Path | None = None, state_path: Path | None = None) -> None:
    config_path = config_path or CONFIG_PATH
    state_path = state_path or STATE_PATH

    config = load_config(config_path)
    state = load_state(state_path)

    if not config.channels:
        logger.info("No channels configured")
        return

    total_success = 0
    total_fail = 0

    for channel in config.channels:
        if channel.slug not in state.channels:
            state.channels[channel.slug] = ChannelState()
        channel_state = state.channels[channel.slug]

        success, fail = process_channel(channel, channel_state)
        total_success += success
        total_fail += fail

    save_state(state, state_path)
    generate_manifest(TRANSCRIPTS_DIR, MANIFEST_PATH)

    if total_success > 0:
        git_commit_and_push()

    logger.info("Done. Extracted: %d, Failed: %d", total_success, total_fail)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()


if __name__ == "__main__":  # pragma: no cover
    main()
