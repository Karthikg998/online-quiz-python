from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_both_ok():
    with patch("app.main.db.query") as mock_db, patch("app.main.cache.client") as mock_cache:
        mock_db.return_value = [{"?column?": 1}]
        mock_cache.return_value.ping.return_value = True

        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["postgres"] is True
        assert data["redis"] is True


def test_health_failure():
    with patch("app.main.db.query", side_effect=Exception("DB down")), patch("app.main.cache.client") as mock_cache:
        mock_cache.return_value.ping.return_value = True

        resp = client.get("/health")
        assert resp.status_code == 503
        data = resp.json()
        assert data["postgres"] is False
        assert "pg_error" in data


def test_quizzes():
    with patch("app.main.db.query") as mock_query:
        mock_query.return_value = [
            {"id": 1, "title": "Git Basics", "limit_seconds": 300, "negative_marks": 0.25, "questions": 3}
        ]
        resp = client.get("/quizzes")
        assert resp.status_code == 200
        assert len(resp.json()["quizzes"]) == 1


def test_quiz_detail():
    with patch("app.main.db.one") as mock_one:
        mock_one.return_value = {
            "id": 1,
            "title": "Git Basics",
            "limit_seconds": 300,
            "negative_marks": 0.25,
            "partial_credit": True,
            "questions": 3,
        }
        resp = client.get("/quizzes/1")
        assert resp.status_code == 200
        assert resp.json()["quiz"]["title"] == "Git Basics"


def test_quiz_detail_not_found():
    with patch("app.main.db.one", return_value=None):
        resp = client.get("/quizzes/999")
        assert resp.status_code == 404


def test_version():
    resp = client.get("/version")
    assert resp.status_code == 200
    assert resp.json()["service"] == "online-quiz"


def test_start_attempt_missing_quiz():
    with patch("app.main.db.one", return_value=None):
        resp = client.post("/attempts", json={"quiz_id": 99, "student": "alice"})
        assert resp.status_code == 404


def test_start_attempt_empty_student():
    with patch("app.main.db.one", return_value={"id": 1, "limit_seconds": 300}):
        resp = client.post("/attempts", json={"quiz_id": 1, "student": "  "})
        assert resp.status_code == 400


def test_start_attempt_success():
    with patch("app.main.db.one") as mock_one, patch("app.main.cache.set_json"):
        mock_one.side_effect = [
            {"id": 1, "limit_seconds": 300},  # select quiz
            {"id": 42},  # insert attempt returning id
        ]
        resp = client.post("/attempts", json={"quiz_id": 1, "student": "alice"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["attempt_id"] == 42
        assert data["seconds_left"] > 0


def test_progress():
    from datetime import datetime, timedelta, timezone

    deadline = datetime.now(timezone.utc) + timedelta(seconds=200)
    with patch("app.main._attempt") as mock_att, patch("app.main.cache.get_json") as mock_get:
        mock_att.return_value = {
            "id": 1,
            "quiz_id": 1,
            "student": "alice",
            "deadline": deadline,
            "submitted": False,
        }
        mock_get.return_value = {"answers": {"1": [0]}}

        resp = client.get("/attempts/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["student"] == "alice"
        assert data["answered"] == 1


def test_answer_when_submitted():
    with patch("app.main._attempt") as mock_att:
        mock_att.return_value = {"submitted": True}
        resp = client.post("/attempts/1/answer", json={"question_id": 1, "choice": [0]})
        assert resp.status_code == 409


def test_answer_when_expired():
    from datetime import datetime, timedelta, timezone

    deadline = datetime.now(timezone.utc) - timedelta(seconds=10)
    with patch("app.main._attempt") as mock_att:
        mock_att.return_value = {"submitted": False, "deadline": deadline}
        resp = client.post("/attempts/1/answer", json={"question_id": 1, "choice": [0]})
        assert resp.status_code == 409


def test_answer_success():
    from datetime import datetime, timedelta, timezone

    deadline = datetime.now(timezone.utc) + timedelta(seconds=200)
    with patch("app.main._attempt") as mock_att, patch("app.main.cache.get_json") as mock_get, patch(
        "app.main.cache.set_json"
    ):
        mock_att.return_value = {"submitted": False, "deadline": deadline}
        mock_get.return_value = {"answers": {}}

        resp = client.post("/attempts/1/answer", json={"question_id": 1, "choice": [0]})
        assert resp.status_code == 200
        assert resp.json()["saved"] is True


def test_submit_when_already_submitted():
    with patch("app.main._attempt") as mock_att:
        mock_att.return_value = {"submitted": True}
        resp = client.post("/attempts/1/submit")
        assert resp.status_code == 409


def test_submit_success():
    from datetime import datetime, timedelta, timezone

    deadline = datetime.now(timezone.utc) + timedelta(seconds=200)
    with patch("app.main._attempt") as mock_att, patch("app.main.db.one") as mock_one, patch(
        "app.main.db.query"
    ) as mock_query, patch("app.main.cache.get_json") as mock_get, patch("app.main.cache.drop"):
        mock_att.return_value = {
            "id": 1,
            "quiz_id": 1,
            "student": "alice",
            "deadline": deadline,
            "submitted": False,
        }
        mock_one.return_value = {"negative_marks": 0.25, "partial_credit": True}
        mock_query.side_effect = [
            [{"id": 1, "marks": 1, "correct": [0]}],  # select questions
            [],  # update attempt
        ]
        mock_get.return_value = {"answers": {"1": [0]}}

        resp = client.post("/attempts/1/submit")
        assert resp.status_code == 200
        assert resp.json()["score"] == 1.0
