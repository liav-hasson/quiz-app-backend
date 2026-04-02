#!/usr/bin/env python3
"""Pre-generate tomorrow's daily challenge question and deep dive article.

Designed to run as a K8s CronJob or standalone script.
Uses the server's OpenAI API key (from env var or SSM).

Usage:
    python -m api.scripts.generate_dailies
"""

from __future__ import annotations

import logging
import random
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from common.database import DBController
from common.repositories.daily_challenge_repository import DailyChallengeRepository
from common.repositories.daily_deep_dive_repository import DailyDeepDiveRepository
from common.repositories.quiz_repository import QuizRepository
from common.utils.ai import get_service

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("generate_dailies")


def _tomorrow_key() -> str:
    """Return tomorrow's date key in Israel time (YYYY-MM-DD)."""
    return (datetime.now(ISRAEL_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")


def _pick_random_topic(quiz_repo: QuizRepository) -> dict:
    """Pick a random category → subject → keyword → style modifier."""
    categories = quiz_repo.get_all_topics()
    if not categories:
        raise RuntimeError("No categories in quiz_data")

    category = random.choice(categories)
    subjects = quiz_repo.get_subtopics_by_topic(category)
    if not subjects:
        raise RuntimeError(f"No subjects for category {category}")
    subject = random.choice(subjects)

    keywords = quiz_repo.get_keywords_by_topic_subtopic(category, subject)
    keyword = random.choice(keywords) if keywords else subject

    style_modifiers = quiz_repo.get_style_modifiers_by_topic_subtopic(category, subject)
    style_modifier = random.choice(style_modifiers) if style_modifiers else "general explanation"

    return {
        "category": category,
        "subject": subject,
        "keyword": keyword,
        "style_modifier": style_modifier,
    }


def generate_daily_challenge(
    quiz_repo: QuizRepository,
    challenge_repo: DailyChallengeRepository,
) -> bool:
    """Generate tomorrow's daily challenge question. Returns True on success."""
    date_key = _tomorrow_key()

    existing = challenge_repo.collection.find_one({"date": date_key})
    if existing:
        logger.info("daily_challenge_already_exists date=%s — skipping", date_key)
        return True

    topic = _pick_random_topic(quiz_repo)
    ai_service = get_service()

    question = ai_service.generate_question(
        topic["category"],
        topic["subject"],
        topic["keyword"],
        difficulty=1,
        style_modifier=topic["style_modifier"],
    )

    doc = {
        "date": date_key,
        "question": question,
        "answers": [],
        "created_at": datetime.now(timezone.utc),
    }
    challenge_repo.collection.insert_one(doc)
    logger.info(
        "daily_challenge_generated date=%s category=%s subject=%s keyword=%s",
        date_key, topic["category"], topic["subject"], topic["keyword"],
    )
    return True


def generate_daily_deep_dive(
    quiz_repo: QuizRepository,
    deep_dive_repo: DailyDeepDiveRepository,
) -> bool:
    """Generate tomorrow's deep dive article. Returns True on success."""
    date_key = _tomorrow_key()

    existing = deep_dive_repo.collection.find_one({"date": date_key})
    if existing:
        logger.info("daily_deep_dive_already_exists date=%s — skipping", date_key)
        return True

    topic = _pick_random_topic(quiz_repo)
    ai_service = get_service()

    content = ai_service.generate_deep_dive(
        topic["category"],
        topic["subject"],
        topic["keyword"],
        style_modifier=topic["style_modifier"],
    )

    doc = {
        "date": date_key,
        "keyword": topic["keyword"],
        "category": topic["category"],
        "subject": topic["subject"],
        "content": content,
        "status": "ready",
        "xp_claims": [],
        "created_at": datetime.now(timezone.utc),
    }
    deep_dive_repo.collection.insert_one(doc)
    logger.info(
        "daily_deep_dive_generated date=%s keyword=%s category=%s",
        date_key, topic["keyword"], topic["category"],
    )
    return True


def main() -> int:
    logger.info("Starting daily content generation for %s", _tomorrow_key())

    db = DBController()
    if not db.connect():
        logger.error("Failed to connect to MongoDB")
        return 1

    quiz_repo = QuizRepository(db)
    challenge_repo = DailyChallengeRepository(db)
    deep_dive_repo = DailyDeepDiveRepository(db)

    success = True

    try:
        generate_daily_challenge(quiz_repo, challenge_repo)
    except Exception:
        logger.error("daily_challenge_generation_failed", exc_info=True)
        success = False

    try:
        generate_daily_deep_dive(quiz_repo, deep_dive_repo)
    except Exception:
        logger.error("daily_deep_dive_generation_failed", exc_info=True)
        success = False

    if success:
        logger.info("Daily content generation completed successfully")
    else:
        logger.error("Daily content generation completed with errors")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
