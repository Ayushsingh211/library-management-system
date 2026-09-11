# Smart Library Management System

A Flask + SQLite library website with authentication, book inventory, member management, book issue/return, overdue fine calculation and an AI library assistant.

## Requirements
- Python 3.10 or newer
- VS Code (recommended)
- Optional Gemini API key for generative AI. Without a key, the built-in library assistant still answers common library questions.

## Run on Windows (VS Code terminal)

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
flask --app app create-admin
flask --app app run --debug
```

Open http://127.0.0.1:5000

Create your administrator account when prompted. Students can register from the login page.

## Enable Gemini AI
1. Get an API key from Google AI Studio.
2. Open `.env` and set `GEMINI_API_KEY=your_key_here`.
3. Stop and restart Flask. Never commit `.env` or expose your API key in frontend JavaScript.

## Features
- Admin and student accounts with hashed passwords
- Dashboard statistics
- Searchable book catalogue
- Admin-only add/delete books and member list
- Issue and return workflow
- 14-day borrowing period and ₹5 per late day
- AI assistant with live catalogue context when Gemini is configured
- Local fallback assistant when no API key is configured

## Suggested genuine Git workflow
Commit each completed stage on the date you actually finish it. Do not fabricate or backdate commits.

```bash
git init
git add .
git commit -m "Initial Flask project structure"
```

Then make focused commits as you implement and test features, for example:
- `Add user registration and login`
- `Create book catalogue and search`
- `Implement issue and return workflow`
- `Add admin dashboard and member management`
- `Integrate AI library assistant`
- `Polish responsive layout and documentation`

## Notes
This is a college-project starter. Before public production deployment, add CSRF protection, rate limiting, stronger secret management, automated tests, database migrations, and deployment configuration. Change the default development secret before deployment.
