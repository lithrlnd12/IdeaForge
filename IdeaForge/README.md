# Idea Forge - AI-Powered Android App Generator

## 1. Project Description

Idea Forge is an Android application that allows users to generate other Android applications by providing natural language prompts. It connects to a live Claude AI model (Opus) for code generation and uses a cloud build pipeline to deliver APKs. Users interact with a chat-like interface, describe the app they want, and Idea Forge generates Flutter code and builds an APK, providing a download link.

**Key Technologies:**
*   **Idea Forge App (Client):** Kotlin, Jetpack Compose
*   **Live AI Model:** Anthropic Claude 3 Opus (via API)
*   **Generated Apps (Target):** Flutter (code generated by Claude)
*   **Backend:** Python (Flask)
*   **Build Service:** Google Cloud Build (automated pipeline)

## 2. Features

*   **Chat-like Interface:** Users describe the app they want to build.
*   **Live AI Code Generation:** Connects to Claude 3 Opus to generate Flutter code.
*   **Display of Generated Code:** The Android app displays the generated code.
*   **Cloud Build & APK Delivery:**
    *   Cloud Build pipeline builds the APK from generated code.
    *   Uploads the APK to a secure Google Cloud Storage bucket.
    *   Provides a download link to the user.
*   **Modern UI:** Built with Jetpack Compose.
*   **Conversation History:** Maintains context for better code generation.

## 3. Project Structure

- `/IdeaForge/`: Android Studio project for the Idea Forge app.
- `/IdeaForge_Backend/`: Python Flask backend for AI and build orchestration.
- `cloudbuild.yaml`: Defines the Google Cloud Build pipeline.

## 4. Security & Secret Management

- **Sensitive information (API keys, tokens, project IDs, bucket names) is never committed to the repository.**
- **`.env` files are for local development only and are included in `.gitignore`.**
- **Production secrets are managed using Google Secret Manager and injected as environment variables during the build.**
- **Do not share or commit your real API keys or sensitive configuration.**

## 5. Cloud Build & APK Delivery Pipeline

This project uses Google Cloud Build to automatically build and deliver APKs when code is pushed to GitHub.

- The `cloudbuild.yaml` file in the repository defines the build steps.
- Secrets (like the Anthropic API key) are managed securely using Google Secret Manager and are **not** committed to the repository.
- When you push code to GitHub, a Cloud Build trigger runs, builds the APK, and uploads it to a secure Google Cloud Storage bucket.
- The backend and mobile app are configured to use environment variables for all sensitive data.

## 6. Local Development

### Backend

1.  **Navigate to the backend directory:**
    ```bash
    cd /path/to/your/project/IdeaForge_Backend
    ```
2.  **Create a Python virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3.  **Install dependencies:**
    ```bash
    pip3 install -r requirements.txt
    ```
4.  **Create `.env` file:**
    *   In the `IdeaForge_Backend` directory, create a file named `.env`.
    *   Add your Anthropic API key to this file:
        ```
        ANTHROPIC_API_KEY=your-anthropic-api-key-here
        ```
    *   **Never commit this file.**
5.  **Run the Flask server:**
    ```bash
    python3 live_backend.py
    ```

### Android App

1.  **Open Android Studio.**
2.  Select "Open an Existing Project" and navigate to `/path/to/your/project/IdeaForge/`.
3.  Wait for Android Studio to sync the project and download dependencies.
4.  **Configure Backend URL:**
    *   Open `IdeaForge/app/src/main/java/com/example/ideaforge/network/LiveBackendClient.kt`
    *   Set `BASE_URL` to your backend's address (local or cloud).
5.  **Build and Run the App.**

## 7. Cloud Deployment

### Prerequisites
- Google Cloud SDK installed and configured (`gcloud init`)
- Authenticated (`gcloud auth login`)
- Default project set (`gcloud config set project [YOUR_PROJECT_ID]`)
- `cloudbuild.yaml` and all code present in the repository

### Setting Up Secrets
- Store your Anthropic API key and any other secrets in Google Secret Manager.
- Grant Cloud Build access to these secrets.

### Cloud Build Trigger
- Set up a trigger in Google Cloud Console to run on push to your GitHub repo.
- The pipeline will:
    1. Retrieve secrets from Secret Manager
    2. Build the APK
    3. Upload the APK to a secure bucket
    4. Provide a download link

### Updating the Mobile App for Cloud Backend
- Set the `BASE_URL` in your app to the deployed backend's public URL.

## 8. Notes
- All sensitive values are managed securely and never committed.
- `.env` is for local use only and is gitignored.
- For production, always use Google Secret Manager for secrets.

## 9. Future Enhancements
- Real-time build status updates
- Automated error correction with AI
- Persistent project and conversation history
- Enhanced UI/UX

---

**For more details, see the documentation files in this repository.**
