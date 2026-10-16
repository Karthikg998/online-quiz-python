import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.integration
def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["postgres"] is True
    assert data["redis"] is True


@pytest.mark.integration
def test_version_endpoint(client):
    response = client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "online-quiz"
    assert "version" in data


@pytest.mark.integration
def test_quizzes_list(client):
    response = client.get("/quizzes")
    assert response.status_code == 200
    data = response.json()
    assert "quizzes" in data
    assert len(data["quizzes"]) >= 1
    quiz = data["quizzes"][0]
    assert quiz["id"] == 1
    assert quiz["title"] == "Git Basics"


@pytest.mark.integration
def test_quiz_detail(client):
    response = client.get("/quizzes/1")
    assert response.status_code == 200
    data = response.json()
    assert data["quiz"]["id"] == 1
    assert data["quiz"]["title"] == "Git Basics"

    # Non-existent quiz
    not_found = client.get("/quizzes/999")
    assert not_found.status_code == 404


@pytest.mark.integration
def test_start_attempt_validation(client):
    # Missing student name
    resp = client.post("/attempts", json={"quiz_id": 1, "student": ""})
    assert resp.status_code == 400

    # Non-existent quiz
    resp = client.post("/attempts", json={"quiz_id": 999, "student": "alice"})
    assert resp.status_code == 404


@pytest.mark.integration
def test_full_attempt_flow(client):
    # 1. Start attempt
    resp = client.post("/attempts", json={"quiz_id": 1, "student": "alice"})
    assert resp.status_code == 201
    start_data = resp.json()
    attempt_id = start_data["attempt_id"]
    assert start_data["seconds_left"] > 0

    # 2. Check initial progress
    progress_resp = client.get(f"/attempts/{attempt_id}")
    assert progress_resp.status_code == 200
    prog = progress_resp.json()
    assert prog["student"] == "alice"
    assert prog["submitted"] is False
    assert prog["answered"] == 0

    # 3. Answer question
    ans_resp = client.post(
        f"/attempts/{attempt_id}/answer",
        json={"question_id": 1, "choice": [0]},
    )
    assert ans_resp.status_code == 200
    assert ans_resp.json()["saved"] is True

    # Check updated progress
    prog2 = client.get(f"/attempts/{attempt_id}").json()
    assert prog2["answered"] == 1

    # 4. Submit attempt
    sub_resp = client.post(f"/attempts/{attempt_id}/submit")
    assert sub_resp.status_code == 200
    result = sub_resp.json()
    assert result["attempt_id"] == attempt_id
    assert result["score"] >= 1.0
    assert result["possible"] == 4.0

    # 5. Prevent answering or submitting again
    sub_again = client.post(f"/attempts/{attempt_id}/submit")
    assert sub_again.status_code == 409

    ans_again = client.post(
        f"/attempts/{attempt_id}/answer",
        json={"question_id": 2, "choice": [1]},
    )
    assert ans_again.status_code == 409
