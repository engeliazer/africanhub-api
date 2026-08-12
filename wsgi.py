from app import app

# Database init runs in app.py (non-fatal if DB is temporarily unavailable).

if __name__ == "__main__":
    app.run()
