# Global Strategic Alert (GSA)

Android + cloud-backend starter project for a selective global critical-events alert system.

## Included
- Native Android app (Kotlin / Jetpack Compose), dark dashboard, Arabic labels, severity filters.
- FastAPI backend with RSS ingestion, SQLite deduplication and conservative keyword triage.
- GitHub Actions workflow to build a debug APK in the cloud.
- Dockerfile for backend deployment.

## Important: this is an MVP foundation, not a finished 24/7 alert service
The app currently fetches events when opened/refreshed. It does not yet have reliable push notifications or background monitoring. RSS keyword matches are preliminary triage, not independent confirmation. FCM, corroboration, AI analysis and production monitoring are later phases.

## Build an APK using only your phone
1. Create a GitHub repository named `global-strategic-alert`.
2. Upload the contents of this folder to the repository.
3. Open Actions and enable workflows if requested.
4. Run **Build Android APK** (or push to `main`).
5. Open the completed workflow and download artifact `GSA-debug-apk`.
6. Extract it and install `app-debug.apk` on Android.

## Backend
Deploy `backend/` to a Docker-capable host with persistent storage. Set `DATABASE_PATH=/data/gsa.db`. After deployment, replace `YOUR-BACKEND-HOST` in `app/build.gradle.kts` with the real HTTPS base URL, then rebuild the APK.

Endpoints: `/health`, `/sources`, `/refresh`, `/events?min_level=4&limit=50`.

Never put API keys or Firebase service-account secrets in Android code. Use hosting secrets. A production release needs source validation, independent corroboration, FCM, monitoring, tests, and secure deployment.
