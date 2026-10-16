from datetime import datetime, timedelta, timezone
import pytest

from app.scoring import (
    QuizError,
    deadline_for,
    grade,
    is_expired,
    score_question,
    seconds_left,
)


def test_deadline_for_positive_limit():
    start = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)
    expected = datetime(2026, 10, 16, 12, 5, 0, tzinfo=timezone.utc)
    assert deadline_for(start, 300) == expected


def test_deadline_for_non_positive_limit():
    start = datetime.now(timezone.utc)
    with pytest.raises(QuizError, match="must be positive"):
        deadline_for(start, 0)
    with pytest.raises(QuizError, match="must be positive"):
        deadline_for(start, -10)


def test_seconds_left_future():
    now = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)
    deadline = now + timedelta(seconds=120)
    assert seconds_left(deadline, now=now) == 120


def test_seconds_left_past():
    now = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)
    deadline = now - timedelta(seconds=30)
    assert seconds_left(deadline, now=now) == 0


def test_seconds_left_default_now():
    deadline = datetime.now(timezone.utc) + timedelta(seconds=60)
    left = seconds_left(deadline)
    assert 55 <= left <= 65


def test_is_expired_before_deadline():
    now = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)
    deadline = now + timedelta(seconds=10)
    assert not is_expired(deadline, now=now, grace_seconds=2)


def test_is_expired_within_grace():
    now = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)
    deadline = now - timedelta(seconds=1)
    # 1 second past deadline, but within 2s grace
    assert not is_expired(deadline, now=now, grace_seconds=2)


def test_is_expired_after_grace():
    now = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)
    deadline = now - timedelta(seconds=3)
    # 3 seconds past deadline exceeds 2s grace
    assert is_expired(deadline, now=now, grace_seconds=2)


def test_is_expired_default_now():
    deadline = datetime.now(timezone.utc) - timedelta(seconds=10)
    assert is_expired(deadline)


def test_score_question_unanswered():
    assert score_question([0], [], marks=2.0, negative=1.0) == 0.0


def test_score_question_exact_match():
    assert score_question([0, 1], [0, 1], marks=3.0, negative=1.0) == 3.0


def test_score_question_wrong_no_partial():
    assert score_question([0], [1], marks=2.0, negative=0.5, partial=False) == -0.5


def test_score_question_partial_credit_valid_subset():
    # 2 correct choices, student got 1 correct choice and no wrong choices
    res = score_question([0, 1], [0], marks=2.0, negative=0.5, partial=True)
    assert res == 1.0


def test_score_question_partial_credit_with_extra_wrong():
    # Student answered correct choice plus a wrong choice -> negative marks applied
    res = score_question([0, 1], [0, 2], marks=2.0, negative=0.5, partial=True)
    assert res == -0.5


def test_grade_empty_questions():
    res = grade([], {})
    assert res["score"] == 0.0
    assert res["possible"] == 0.0
    assert res["percent"] == 0.0
    assert res["breakdown"] == []


def test_grade_all_correct():
    questions = [
        {"id": 1, "marks": 2, "correct": [0]},
        {"id": 2, "marks": 3, "correct": [1, 2]},
    ]
    answers = {1: [0], 2: [1, 2]}
    res = grade(questions, answers, negative=1.0, partial=True)
    assert res["score"] == 5.0
    assert res["possible"] == 5.0
    assert res["percent"] == 100.0
    assert len(res["breakdown"]) == 2
    assert res["breakdown"][0]["awarded"] == 2.0
    assert res["breakdown"][1]["awarded"] == 3.0


def test_grade_capped_at_zero():
    questions = [
        {"id": 1, "marks": 1, "correct": [0]},
    ]
    answers = {1: [2]}
    res = grade(questions, answers, negative=5.0, partial=False)
    assert res["score"] == 0.0  # total should never be below zero
    assert res["breakdown"][0]["awarded"] == -5.0
