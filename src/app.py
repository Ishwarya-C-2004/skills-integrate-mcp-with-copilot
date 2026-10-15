"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=current_dir / "static"), name="static")

PASSWORD_HASH_ITERATIONS = 600_000
SESSION_TTL_SECONDS = 8 * 60 * 60
SESSION_COOKIE_NAME = "teacher_session"
SESSION_SECRET = os.environ.get("SESSION_SECRET")
if SESSION_SECRET is None:
    SESSION_SECRET = secrets.token_urlsafe(32)
elif len(SESSION_SECRET) < 32:
    raise ValueError("SESSION_SECRET must be at least 32 characters long")
SESSION_SECRET = SESSION_SECRET.encode()

cookie_secure_setting = os.environ.get("SESSION_COOKIE_SECURE", "false").lower()
if cookie_secure_setting not in {"true", "false"}:
    raise ValueError("SESSION_COOKIE_SECURE must be 'true' or 'false'")
SESSION_COOKIE_SECURE = cookie_secure_setting == "true"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


def load_teachers() -> dict[str, str]:
    with (current_dir / "teachers.json").open(encoding="utf-8") as teachers_file:
        configured_teachers = json.load(teachers_file)

    if not isinstance(configured_teachers, dict) or any(
        not isinstance(username, str)
        or not username
        or ":" in username
        or not isinstance(password_hash, str)
        for username, password_hash in configured_teachers.items()
    ):
        raise ValueError("teachers.json must map teacher usernames to password hashes")

    return configured_teachers


teachers = load_teachers()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, PASSWORD_HASH_ITERATIONS
    )
    return (
        f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}"
        f"${salt.hex()}${digest.hex()}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored_hash.split("$")
        if algorithm != "pbkdf2_sha256" or int(iterations) != PASSWORD_HASH_ITERATIONS:
            return False
        salt = bytes.fromhex(salt_hex)
        expected_digest = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, PASSWORD_HASH_ITERATIONS
    )
    return hmac.compare_digest(actual_digest, expected_digest)


def create_session_token(username: str) -> str:
    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    payload = base64.urlsafe_b64encode(
        f"{username}:{expires_at}".encode()
    ).decode().rstrip("=")
    signature = hmac.new(SESSION_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def get_session_username(token: str | None) -> str | None:
    if token is None:
        return None

    try:
        payload, signature = token.split(".", 1)
        expected_signature = hmac.new(
            SESSION_SECRET, payload.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return None

        padded_payload = payload + "=" * (-len(payload) % 4)
        username, expires_at = base64.urlsafe_b64decode(
            padded_payload.encode()
        ).decode().rsplit(":", 1)
        if int(expires_at) <= int(time.time()) or username not in teachers:
            return None
    except (ValueError, UnicodeDecodeError):
        return None

    return username


def require_teacher(request: Request) -> str:
    username = get_session_username(request.cookies.get(SESSION_COOKIE_NAME))
    if username is None:
        raise HTTPException(status_code=401, detail="Teacher login required")
    return username


@app.post("/auth/login")
def login(credentials: LoginRequest):
    if not teachers:
        raise HTTPException(
            status_code=503,
            detail="No teacher accounts are configured",
        )

    password_hash = teachers.get(credentials.username)
    if password_hash is None:
        # Keep the failure path comparable to a password check for a known user.
        verify_password(
            credentials.password,
            f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}"
            "$00000000000000000000000000000000$"
            "0000000000000000000000000000000000000000000000000000000000000000",
        )
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not verify_password(credentials.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    response = JSONResponse(
        {"message": "Teacher signed in", "username": credentials.username}
    )
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_token(credentials.username),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
    return response


@app.get("/auth/me")
def current_teacher(request: Request):
    return {"username": require_teacher(request)}


@app.post("/auth/logout")
def logout():
    response = JSONResponse({"message": "Teacher signed out"})
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
    return response

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str, request: Request):
    """Sign up a student for an activity"""
    require_teacher(request)

    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str, request: Request):
    """Unregister a student from an activity"""
    require_teacher(request)

    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
