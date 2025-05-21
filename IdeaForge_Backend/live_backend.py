import os
import requests
import json
import time
import random
import subprocess
import shutil
import uuid # For unique temporary directory names
import tempfile
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from google.cloud import storage
from google.cloud.devtools.cloudbuild_v1.services import cloud_build
from google.cloud.devtools.cloudbuild_v1.types import Build, RepoSource, StorageSource, Source
from google.oauth2 import service_account # For GCP authentication
from google.auth import default
import re
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Claude API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-3.7-sonnet"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

# GitHub Configuration
GITHUB_PAT = os.getenv("GITHUB_PAT")
GITHUB_REPO_URL = os.getenv("GITHUB_REPO_URL") # e.g., https://github.com/lithrlnd12/IdeaForge.git

# GCP Configuration
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_SERVICE_ACCOUNT_KEY_PATH = os.getenv("GCP_SERVICE_ACCOUNT_KEY_PATH")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

# --- Helper: GCP Credentials ---
def get_gcp_credentials():
    credentials, project = default()
    return credentials

# --- Helper: Claude API Call (existing, slightly modified for clarity) ---
conversation_history = {}
def call_claude_api(user_prompt: str, user_id: str, system_prompt: str = None):
    # ... (Keep existing Claude API call logic, ensure it returns generated_text clearly)
    if not ANTHROPIC_API_KEY:
        return {"error": "Anthropic API key not configured."}, 500, None

    current_user_history = conversation_history.get(user_id, [])
    messages_payload = list(current_user_history) # Make a copy
    messages_payload.append({"role": "user", "content": user_prompt})
    
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    default_system_prompt = (
        "You are Idea Forge, an expert Flutter application developer. Your ONLY job is to generate complete, correct, and well-structured Flutter code (Dart language) based on the user's requirements.\n\n"
        "IMPORTANT:\n"
        "- You MUST provide the entire application code for a single-file Flutter application in a code block, for 'main.dart'.\n"
        "- If needed, also provide a 'pubspec.yaml' in a separate code block, clearly marked.\n"
        "- DO NOT provide setup instructions, explanations, or guides—ONLY code blocks.\n"
        "- DO NOT include any asset references or image files in the code.\n"
        "- Use Flutter's built-in Icons and colored Containers instead of images.\n"
        "- If you cannot generate the code, respond with: ERROR: Unable to generate main.dart code.\n\n"
        "Format Example:\n"
        "FILENAME: main.dart\n"
        "````dart\n"
        "// ... main.dart code ...\n"
        "````\n\n"
        "FILENAME: pubspec.yaml\n"
        "````yaml\n"
        "// ... pubspec.yaml code ...\n"
        "````"
    )
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 4096, 
        "messages": messages_payload,
        "system": system_prompt if system_prompt else default_system_prompt,
        "temperature": 0.3 
    }
    try:
        response = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=180)
        response.raise_for_status()
        api_response_json = response.json()
        generated_text = ""
        if api_response_json.get("content") and isinstance(api_response_json["content"], list) and len(api_response_json["content"]) > 0:
            generated_text = api_response_json["content"][0].get("text", "")
        
        # Update history
        current_user_history.append({"role": "user", "content": user_prompt})
        current_user_history.append({"role": "assistant", "content": generated_text})
        conversation_history[user_id] = current_user_history[-10:]
        return api_response_json, 200, generated_text
    except requests.exceptions.RequestException as e:
        # ... (existing error handling) ...
        return {"error": f"Error calling Claude API: {e}"}, 500, None
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}, 500, None

# --- Helper: Parse AI Generated Code ---
def parse_generated_code(generated_text: str):
    # Simple parser: assumes main.dart and optionally pubspec.yaml
    # A more robust parser would handle more complex project structures or zipped files.
    files = {}
    try:
        parts = generated_text.split("FILENAME:")
        for part in parts:
            if not part.strip():
                continue
            lines = part.strip().split("\n", 1)
            filename = lines[0].strip()
            code_content = ""
            if len(lines) > 1:
                code_block = lines[1].strip()
                # Remove markdown formatting
                if code_block.startswith("```"):
                    # Find the first newline after the opening ```
                    start_idx = code_block.find("\n") + 1
                    # Find the last ``` and remove it
                    end_idx = code_block.rfind("```")
                    if end_idx == -1:  # If no closing ```, take everything after the first newline
                        code_content = code_block[start_idx:].strip()
                    else:
                        code_content = code_block[start_idx:end_idx].strip()
                else:
                    code_content = code_block.strip()
            
            if filename in ["main.dart", "pubspec.yaml"]:
                files[filename] = code_content
            elif "main.dart" in filename:  # allow for path/to/main.dart
                files["main.dart"] = code_content
            elif "pubspec.yaml" in filename:
                files["pubspec.yaml"] = code_content

        if "main.dart" not in files:
            # Fallback: assume the whole text is main.dart if no FILENAME tags
            if "name:" not in generated_text and ("void main()" in generated_text or "MaterialApp" in generated_text):
                files["main.dart"] = generated_text
        if "pubspec.yaml" not in files:
            # Provide a default minimal pubspec.yaml if not generated
            files["pubspec.yaml"] = """name: idea_forge_generated_app
description: A new Flutter project generated by Idea Forge.
publish_to: 'none'

version: 1.0.0+1

environment:
  sdk: '>=2.19.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
  cupertino_icons: ^1.0.2

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^2.0.0

flutter:
  uses-material-design: true"""
        return files
    except Exception as e:
        print(f"Error parsing generated code: {e}")
        # Fallback if parsing fails, return the whole text as main.dart
        return {
            "main.dart": generated_text,
            "pubspec.yaml": """name: idea_forge_generated_app
description: A new Flutter project generated by Idea Forge.
publish_to: 'none'

version: 1.0.0+1

environment:
  sdk: '>=2.19.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
  cupertino_icons: ^1.0.2

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^2.0.0

flutter:
  uses-material-design: true"""
        }

# --- Helper: Git Operations ---
def update_github_repository(generated_files: dict, repo_url: str, pat: str, commit_message: str):
    if not pat or not repo_url:
        return False, "GitHub PAT or Repository URL not configured."
    
    temp_dir = os.path.join(tempfile.gettempdir(), f"ideaforge_repo_{uuid.uuid4()}")
    try:
        # Clone the repo
        # Construct the authenticated URL
        auth_repo_url = repo_url.replace("https://", f"https://oauth2:{pat}@")
        subprocess.run(["git", "clone", "--depth=1", auth_repo_url, temp_dir], check=True, capture_output=True, text=True)
        
        # Clear existing files (except .git and cloudbuild.yaml)
        for item in os.listdir(temp_dir):
            item_path = os.path.join(temp_dir, item)
            if item == ".git" or item == "cloudbuild.yaml":
                continue
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        
        # Create lib directory if it doesn_t exist for main.dart
        lib_dir = os.path.join(temp_dir, "lib")
        if not os.path.exists(lib_dir):
            os.makedirs(lib_dir)

        # Write new files
        for filename, content in generated_files.items():
            file_path = ""
            if filename == "main.dart":
                file_path = os.path.join(lib_dir, filename)
            else: # pubspec.yaml
                file_path = os.path.join(temp_dir, filename)
            with open(file_path, "w") as f:
                f.write(content)
        
        # Git commit and push
        subprocess.run(["git", "add", "."], cwd=temp_dir, check=True, capture_output=True, text=True)
        # Check if there are changes to commit
        status_result = subprocess.run(["git", "status", "--porcelain"], cwd=temp_dir, check=True, capture_output=True, text=True)
        if not status_result.stdout.strip():
            print("No changes to commit.")
            # If no changes, we can assume the build doesn_t need to run, or handle as needed
            # For now, let_s proceed as if a build is still desired if code was generated.
        else:
            subprocess.run(["git", "commit", "-m", commit_message], cwd=temp_dir, check=True, capture_output=True, text=True)
        subprocess.run(["git", "push"], cwd=temp_dir, check=True, capture_output=True, text=True)
        
        return True, "Successfully pushed to GitHub."
    except subprocess.CalledProcessError as e:
        error_message = f"Git operation failed: {e.stderr}"
        print(error_message)
        return False, error_message
    except Exception as e:
        error_message = f"Error updating GitHub repository: {e}"
        print(error_message)
        return False, error_message
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

# --- Helper: Google Cloud Build Operations ---
def trigger_cloud_build(project_id: str, repo_url: str, branch_name: str = "generated-app"):
    credentials = get_gcp_credentials()
    if not credentials:
        return None, "Failed to get GCP credentials."

    client = cloud_build.CloudBuildClient(credentials=credentials)

    # Extract repo name from URL
    repo_name = repo_url.split("/")[-1].replace(".git", "")

    # Use Build and RepoSource objects instead of a plain dict
    build = Build(
        source=Source(
            repo_source=RepoSource(
                project_id=project_id,
                repo_name=repo_name,
                branch_name=branch_name
            )
        )
        # Add more fields as needed
    )

    try:
        operation = client.create_build(project_id=project_id, build=build)
        print(f"Triggered Cloud Build. Operation: {operation.name}")
        build_id = operation.metadata.build.id
        return build_id, f"Build triggered successfully. Build ID: {build_id}"
    except Exception as e:
        error_message = f"Error triggering Cloud Build: {e}"
        print(error_message)
        return None, error_message

def get_cloud_build_status_and_apk_url(project_id: str, build_id: str, gcs_bucket_name: str):
    credentials = get_gcp_credentials()
    if not credentials:
        return "ERROR", "Failed to get GCP credentials.", None

    client = cloud_build.CloudBuildClient(credentials=credentials)
    storage_client = storage.Client(credentials=credentials)

    try:
        build_info = client.get_build(project_id=project_id, id=build_id)
        status = Build.Status(build_info.status).name
        print(f"Build ID {build_id} status: {status}")

        apk_url = None
        if status == "SUCCESS":
            # Construct the expected APK path based on cloudbuild.yaml
            # Example: gs://ideaforge-apks-aaron/ideaforge-builds/${SHORT_SHA}_app-release.apk
            # We need to list objects or know the exact name. For now, let_s assume a convention or find the latest.
            # This part is tricky without knowing the exact commit SHA used by the build.
            # A more robust way is to have cloudbuild.yaml output a manifest or a fixed name, or use build tags.
            
            # Let_s try to find the artifact from build_info if available
            if build_info.results and build_info.results.artifacts and build_info.results.artifacts.objects:
                apk_path_in_gcs = build_info.results.artifacts.objects.location
                # This location is like gs://bucket/path/to/object
                # We need to parse it to get bucket and object name
                if apk_path_in_gcs.startswith(f"gs://{gcs_bucket_name}/"):
                    blob_name = apk_path_in_gcs[len(f"gs://{gcs_bucket_name}/"):]
                    bucket = storage_client.bucket(gcs_bucket_name)
                    blob = bucket.blob(blob_name)
                    # Generate a signed URL for download (valid for 1 hour)
                    apk_url = blob.generate_signed_url(version="v4", expiration=3600) # 1 hour
                    print(f"Generated signed URL for APK: {apk_url}")
                else:
                    print(f"Artifact path {apk_path_in_gcs} does not match expected bucket {gcs_bucket_name}")
            else:
                 print(f"Build {build_id} successful, but no artifact objects found in build results. Check cloudbuild.yaml artifacts section.")
                 # Fallback: try listing the bucket (less ideal)
                 # This is a simplified fallback and might not get the correct APK
                 # It assumes the APK is the latest in the /ideaforge-builds/ prefix
                 prefix_to_list = "ideaforge-builds/"
                 blobs = storage_client.list_blobs(gcs_bucket_name, prefix=prefix_to_list)
                 latest_blob = None
                 latest_time = None
                 for blob_item in blobs:
                     if blob_item.name.endswith(".apk"):
                         if latest_time is None or blob_item.updated > latest_time:
                             latest_time = blob_item.updated
                             latest_blob = blob_item
                 if latest_blob:
                     apk_url = latest_blob.generate_signed_url(version="v4", expiration=3600)
                     print(f"Found latest APK via listing: {latest_blob.name}, URL: {apk_url}")
                 else:
                     print(f"No APKs found in gs://{gcs_bucket_name}/{prefix_to_list}")

        return status, build_info.log_url, apk_url

    except Exception as e:
        error_message = f"Error getting build status: {e}"
        print(error_message)
        return "ERROR", None, None

def extract_and_write_flutter_code(ai_response: str, project_path: str) -> tuple[bool, str]:
    """
    Extract code blocks from AI response and write them to Flutter project files.
    
    Args:
        ai_response (str): The raw response from Claude AI containing code blocks
        project_path (str): Path to the Flutter project root directory
        
    Returns:
        tuple[bool, str]: (success, message)
    """
    try:
        # Convert project_path to Path object for better path handling
        project_path = Path(project_path)
        
        # Define regex pattern to match code blocks
        # This pattern matches:
        # 1. FILENAME: followed by filename
        # 2. Optional language identifier (```dart, ```yaml, etc)
        # 3. The code content
        # 4. Closing ```
        pattern = r'FILENAME:\s*([^\n]+)\s*(?:```(?:[a-z]*)\n)?(.*?)(?:```|$)'
        
        # Find all code blocks
        matches = re.finditer(pattern, ai_response, re.DOTALL)
        
        # Dictionary to store extracted code
        code_blocks = {}
        
        # Extract code from matches
        for match in matches:
            filename = match.group(1).strip()
            code = match.group(2).strip()
            
            # Map the filename to the correct file
            if 'main.dart' in filename:
                code_blocks['main.dart'] = code
            elif 'pubspec.yaml' in filename:
                code_blocks['pubspec.yaml'] = code
        
        # Check if we have both required files
        if 'main.dart' not in code_blocks:
            return False, "Missing main.dart code block in AI response"
        if 'pubspec.yaml' not in code_blocks:
            return False, "Missing pubspec.yaml code block in AI response"
        
        # Create lib directory if it doesn't exist
        lib_dir = project_path / 'lib'
        lib_dir.mkdir(parents=True, exist_ok=True)
        
        # Write main.dart
        main_dart_path = lib_dir / 'main.dart'
        with open(main_dart_path, 'w', encoding='utf-8') as f:
            f.write(code_blocks['main.dart'])
        
        # Write pubspec.yaml
        pubspec_path = project_path / 'pubspec.yaml'
        with open(pubspec_path, 'w', encoding='utf-8') as f:
            f.write(code_blocks['pubspec.yaml'])
        
        # Check if platform directories exist
        android_dir = project_path / 'android'
        ios_dir = project_path / 'ios'
        
        # If either platform directory is missing, run flutter create
        if not (android_dir.exists() and ios_dir.exists()):
            try:
                subprocess.run(
                    ['flutter', 'create', '.'],
                    cwd=project_path,
                    check=True,
                    capture_output=True,
                    text=True
                )
            except subprocess.CalledProcessError as e:
                return False, f"Failed to initialize Flutter project: {e.stderr}"
        
        return True, "Successfully wrote code to Flutter project files"
        
    except Exception as e:
        return False, f"Error processing code blocks: {str(e)}"

@app.route("/api/v1/generate-app-real-build", methods=["POST"])
def generate_app_real_build():
    data = request.get_json()
    if not data or "prompt" not in data:
        return jsonify({"error": "No prompt provided"}), 400

    user_prompt = data["prompt"]
    user_id = data.get("user_id", "default_user") # For conversation history

    # --- Validate configurations ---
    if not all([ANTHROPIC_API_KEY, GITHUB_PAT, GITHUB_REPO_URL, GCP_PROJECT_ID, GCP_SERVICE_ACCOUNT_KEY_PATH, GCS_BUCKET_NAME]):
        missing_configs = []
        if not ANTHROPIC_API_KEY: missing_configs.append("ANTHROPIC_API_KEY")
        if not GITHUB_PAT: missing_configs.append("GITHUB_PAT")
        if not GITHUB_REPO_URL: missing_configs.append("GITHUB_REPO_URL")
        if not GCP_PROJECT_ID: missing_configs.append("GCP_PROJECT_ID")
        if not GCP_SERVICE_ACCOUNT_KEY_PATH: missing_configs.append("GCP_SERVICE_ACCOUNT_KEY_PATH")
        if not GCS_BUCKET_NAME: missing_configs.append("GCS_BUCKET_NAME")
        return jsonify({"error": f"Server configuration incomplete. Missing: {', '.join(missing_configs)}"}), 500
    
    # 1. Call Claude API to generate code
    print(f"Calling Claude for prompt: {user_prompt[:50]}...")
    claude_response_json, status_code, generated_text = call_claude_api(user_prompt, user_id)
    if status_code != 200 or not generated_text:
        return jsonify(claude_response_json if claude_response_json else {"error": "Failed to get valid response from Claude"}), status_code
    print("Claude API call successful.")

    # 2. Parse generated code (expecting main.dart and pubspec.yaml)
    parsed_files = parse_generated_code(generated_text)
    if "main.dart" not in parsed_files:
        return jsonify({"error": "AI did not generate main.dart content as expected.", "generated_code": generated_text}), 500
    print(f"Parsed generated code. Files: {list(parsed_files.keys())}")

    # 3. Update GitHub Repository
    commit_msg = f"AI generated app for prompt: {user_prompt[:100]}"
    print(f"Pushing to GitHub repo: {GITHUB_REPO_URL}")
    push_success, push_message = update_github_repository(parsed_files, GITHUB_REPO_URL, GITHUB_PAT, commit_msg)
    if not push_success:
        return jsonify({"error": f"Failed to update GitHub repository: {push_message}", "generated_code": generated_text}), 500
    print("Successfully pushed code to GitHub.")

    # 4. Trigger Google Cloud Build
    print(f"Triggering Google Cloud Build for project: {GCP_PROJECT_ID}")
    # Ensure GITHUB_REPO_URL is the plain https URL for GCB connection, not the PAT authenticated one.
    plain_github_repo_url = GITHUB_REPO_URL
    build_id, build_message = trigger_cloud_build(GCP_PROJECT_ID, plain_github_repo_url, branch_name="generated-app")
    if not build_id:
        return jsonify({"error": f"Failed to trigger Cloud Build: {build_message}", "generated_code": generated_text}), 500
    print(f"Cloud Build triggered. Build ID: {build_id}. Message: {build_message}")

    # 5. Poll for build status
    max_polls = 20  # Poll for up to 10 minutes (20 * 30s)
    poll_interval = 30  # seconds
    build_status = "WORKING" # Initial status
    log_url = None
    apk_download_url = None

    for i in range(max_polls):
        print(f"Polling build status for {build_id} (Attempt {i+1}/{max_polls})...")
        time.sleep(poll_interval)
        build_status, log_url, apk_download_url = get_cloud_build_status_and_apk_url(GCP_PROJECT_ID, build_id, GCS_BUCKET_NAME)
        if build_status not in ["PENDING", "QUEUED", "WORKING"]:
            break
    
    print(f"Final build status for {build_id}: {build_status}")
    if build_status == "SUCCESS" and apk_download_url:
        return jsonify({
            "status": "success_real_build",
            "message": "App generated, built, and ready for download!",
            "generated_code_from_claude": generated_text,
            "apk_download_url": apk_download_url,
            "build_id": build_id,
            "build_log_url": log_url,
            "model_used": CLAUDE_MODEL
        }), 200
    else:
        return jsonify({
            "error": f"Build failed or timed out. Status: {build_status}",
            "generated_code_from_claude": generated_text,
            "build_id": build_id,
            "build_log_url": log_url,
            "details": "Check the build logs for more information."
        }), 500

if __name__ == "__main__":
    # Check essential startup configurations
    if not all([ANTHROPIC_API_KEY, GITHUB_PAT, GITHUB_REPO_URL, GCP_PROJECT_ID, GCP_SERVICE_ACCOUNT_KEY_PATH, GCS_BUCKET_NAME]):
        print("CRITICAL ERROR: One or more environment variables are not set. Please check your .env file.")
        print("Required: ANTHROPIC_API_KEY, GITHUB_PAT, GITHUB_REPO_URL, GCP_PROJECT_ID, GCP_SERVICE_ACCOUNT_KEY_PATH, GCS_BUCKET_NAME")
    else:
        print(f"All configurations loaded. Starting Flask app on 0.0.0.0:8080 for Idea Forge Live Backend with Real Builds.")
        app.run(host="0.0.0.0", port=8080, debug=True) # debug=False for production

