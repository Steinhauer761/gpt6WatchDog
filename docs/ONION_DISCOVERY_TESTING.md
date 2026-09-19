# Onion discovery test coverage

The backend test suite verifies that onion discovery is exposed as a real authenticated FastAPI endpoint, appears in health feature reporting, and rejects unauthenticated requests. Normal migration CI continues to compile Python, run pytest, import the FastAPI app, install frontend dependencies, and build Next.js.
