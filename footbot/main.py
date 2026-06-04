import logging
import signal
import sys

from slack.app import app, start
from notifier import poller
from football_data import client
from slack import formatter
from config import (
    SLACK_CHANNEL, FOOTBALL_DATA_POLL_INTERVAL,
    MATCHDAY_SUMMARY_HOUR, MATCHDAY_SUMMARY_MINUTE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("slack_bolt").setLevel(logging.WARNING)
logging.getLogger("slack_sdk").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def _post_to_slack(blocks: list[dict]) -> None:
    """Posts a Block Kit message to the configured channel."""
    try:
        app.client.chat_postMessage(channel=SLACK_CHANNEL, blocks=blocks)
    except Exception:
        logger.exception("Failed to post message to Slack (channel=%s)", SLACK_CHANNEL)


def _post_matchday_summary() -> None:
    """Fires at MATCHDAY_SUMMARY_HOUR:MATCHDAY_SUMMARY_MINUTE UTC every day."""
    try:
        matches = client.get_today_matches()
        finished = [m for m in matches if m.is_finished]
        if finished:
            logger.info("Posting matchday summary (%d finished matches)", len(finished))
            _post_to_slack(formatter.matchday_summary_blocks(finished))
        else:
            logger.debug("Matchday summary: no finished matches today, skipping")
    except Exception:
        logger.exception("Error posting matchday summary")


def _shutdown(scheduler, signum, frame):
    logger.info("Shutting down...")
    scheduler.shutdown(wait=False)
    sys.exit(0)


if __name__ == "__main__":
    scheduler = poller.start(post_fn=_post_to_slack, interval_seconds=FOOTBALL_DATA_POLL_INTERVAL)

    scheduler.add_job(
        _post_matchday_summary,
        trigger="cron",
        hour=MATCHDAY_SUMMARY_HOUR,
        minute=MATCHDAY_SUMMARY_MINUTE,
        id="matchday_summary",
    )
    logger.info("Matchday summary scheduled at %02d:%02d UTC",
                MATCHDAY_SUMMARY_HOUR, MATCHDAY_SUMMARY_MINUTE)

    signal.signal(signal.SIGINT,  lambda s, f: _shutdown(scheduler, s, f))
    signal.signal(signal.SIGTERM, lambda s, f: _shutdown(scheduler, s, f))

    start()  # blocks here — Slack Socket Mode runs until interrupted
