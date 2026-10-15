# Mergington High School Activities API

A super simple FastAPI application that allows students to view and sign up for extracurricular activities.

## Features

- View all available extracurricular activities
- Teacher sign-in to register or unregister students
- Students can view activity rosters without signing in

## Getting Started

1. Install the dependencies:

   ```
   pip install fastapi uvicorn
   ```

2. From the `src` directory, run the application:

   ```
   uvicorn app:app --reload
   ```

3. Open your browser and go to:
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc
   - Activities website: http://localhost:8000/

## Teacher Accounts

Teacher accounts are stored in `src/teachers.json`. The file maps usernames to
PBKDF2 password hashes; do not store plaintext passwords there. Generate a hash
from the `src` directory:

```sh
python -c "from getpass import getpass; from app import hash_password; print(hash_password(getpass('Teacher password: ')))"
```

Add the resulting hash to `teachers.json`, for example:

```json
{
  "teacher1": "pbkdf2_sha256$600000$...$..."
}
```

The application refuses sign-in until at least one teacher is configured.
Sessions use a signed, HTTP-only cookie that expires after eight hours. For
deployment, set a persistent random `SESSION_SECRET` and set
`SESSION_COOKIE_SECURE=true` when serving the site over HTTPS. Without an
explicit `SESSION_SECRET`, a random secret is generated at startup, so signing
in again is required after a restart. Configured session secrets must be at
least 32 characters long.

## API Endpoints

| Method | Endpoint                                                          | Description                                                         |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Get all activities with their details and current participant count |
| POST   | `/auth/login`                                                     | Sign in as a teacher and receive a session cookie                   |
| GET    | `/auth/me`                                                        | Get the signed-in teacher                                          |
| POST   | `/auth/logout`                                                    | Sign out and clear the session cookie                              |
| POST   | `/activities/{activity_name}/signup?email=student@mergington.edu` | Register a student (teacher session required)                      |
| DELETE | `/activities/{activity_name}/unregister?email=student@mergington.edu` | Unregister a student (teacher session required)                  |

## Data Model

The application uses a simple data model with meaningful identifiers:

1. **Activities** - Uses activity name as identifier:

   - Description
   - Schedule
   - Maximum number of participants allowed
   - List of student emails who are signed up

2. **Students** - Uses email as identifier:
   - Name
   - Grade level

All data is stored in memory, which means data will be reset when the server restarts.
