from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_student_account_only_sees_own_student_record():
    teacher_login = client.post("/api/v1/auth/login", json={"username": "teacher", "password": "teacher123"})
    assert teacher_login.status_code == 200
    teacher_token = teacher_login.json()["data"]["access_token"]

    suffix = uuid4().hex[:8]
    own_student_no = f"S{suffix}"
    other_student_no = f"O{suffix}"

    own_student = client.post(
        "/api/v1/students",
        json={"student_no": own_student_no, "name": "权限学生", "class_name": "权限测试班"},
        headers=auth_headers(teacher_token),
    )
    assert own_student.status_code == 200

    other_student = client.post(
        "/api/v1/students",
        json={"student_no": other_student_no, "name": "其他学生", "class_name": "权限测试班"},
        headers=auth_headers(teacher_token),
    )
    assert other_student.status_code == 200

    register = client.post(
        "/api/v1/auth/register",
        json={
            "username": f"student_{suffix}",
            "password": "student123",
            "role": "student",
            "student_no": own_student_no,
        },
    )
    assert register.status_code == 200
    student_token = register.json()["data"]["access_token"]

    student_list = client.get("/api/v1/students", headers=auth_headers(student_token))
    assert student_list.status_code == 200
    rows = student_list.json()["data"]
    assert len(rows) == 1
    assert rows[0]["student_no"] == own_student_no

    forbidden_create = client.post(
        "/api/v1/students",
        json={"student_no": f"X{suffix}", "name": "越权", "class_name": "权限测试班"},
        headers=auth_headers(student_token),
    )
    assert forbidden_create.status_code == 403
