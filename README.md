Quick Capture [MVP] is a case management tool for Simon on the Streets social workers. It enables rapid recording of interactions with prospects — capturing names, locations, notes, and voice recordings with minimal friction.

The system is composed of two services running in Docker containers on the same network:

1. **Web Application** — Flask-based MVC app serving the UI and handling business logic
2. **Transcription Service** — whisper.cpp HTTP server that converts audio recordings to text

Please refer to `docs/archicture.md` for the full system architecture