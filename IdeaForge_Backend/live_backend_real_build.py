import os
import requests
import json
import time
import random
import subprocess
import shutil
import uuid # For unique temporary directory names
import base64
import tempfile
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from google.cloud import storage
from google.cloud.devtools.cloudbuild_v1.services import cloud_build
from google.cloud.devtools.cloudbuild_v1.types import Build, RepoSource, StorageSource
from google.oauth2 import service_account # For GCP authentication
from google.cloud import secretmanager

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app at the top
app = Flask(__name__)

# Load configuration from environment variables
PORT = int(os.getenv("PORT", "8080"))
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
print(f"GCP_PROJECT_ID: {GCP_PROJECT_ID}")
GITHUB_PAT = os.getenv("GITHUB_PAT")
GITHUB_REPO_URL = os.getenv("GITHUB_REPO_URL")
GCP_SERVICE_ACCOUNT_KEY_PATH = os.getenv("GCP_SERVICE_ACCOUNT_KEY_PATH")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

def get_secret(secret_id, version_id="latest"):
    project_id = os.environ.get("GCP_PROJECT_ID")
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

# Get API key from Secret Manager
ANTHROPIC_API_KEY = get_secret("anthropic-api-key")
print(f"ANTHROPIC_API_KEY loaded from Secret Manager: {'Present' if ANTHROPIC_API_KEY else 'Missing'} (Length: {len(ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else 0})")

# Get API URL from Secret Manager
ANTHROPIC_API_URL = get_secret("anthropic-api-url")
if not ANTHROPIC_API_URL:
    ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
print(f"ANTHROPIC_API_URL loaded from Secret Manager: {ANTHROPIC_API_URL}")

# Claude API Configuration
CLAUDE_MODEL = "claude-3.7-sonnet"

# GitHub Configuration

# GCP Configuration

# In-memory storage for build statuses and APK links
build_statuses = {}

# --- Helper: GCP Credentials ---
def get_gcp_credentials():
    if not GCP_SERVICE_ACCOUNT_KEY_PATH:
        print("Error: GCP_SERVICE_ACCOUNT_KEY_PATH not set in .env")
        return None
    try:
        return service_account.Credentials.from_service_account_file(GCP_SERVICE_ACCOUNT_KEY_PATH)
    except Exception as e:
        print(f"Error loading GCP service account credentials: {e}")
        return None

# --- Helper: Claude API Call (existing, slightly modified for clarity) ---
conversation_history = {}
def call_claude_api(user_prompt: str, user_id: str, system_prompt: str = None):
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
        "It is extremely important that you only respond with code blocks and no plain language responses i.e. 'I will build you x' or end the message with any plain language. Just code.\n\n"
        "You are Idea Forge, an expert Flutter application developer. "
        "Your ONLY job is to generate complete, correct, and well-structured Flutter code (Dart language) based on the user's requirements.\n\n"
        "IMPORTANT RULES:\n"
        "- Only provide code blocks—do NOT include any additional text, explanations, or commentary outside of valid Dart comments or code blocks.\n"
        "- Provide ONLY code blocks with NO commentary, introductions, summaries, or plain language.\n"
        "- Provide the entire application code for a single-file Flutter application in a code block labeled: FILENAME: main.dart\n"
        "- If needed, provide a code block labeled: FILENAME: pubspec.yaml\n"
        "- If the app requires any asset files (like images), list them under 'assets:' in pubspec.yaml, but do NOT generate file contents or instructions.\n"
        "- DO NOT provide any explanations, setup instructions, commentary, notes, or text outside code blocks.\n"
        "- DO NOT mention missing assets, package installation, or usage instructions.\n"
        "- DO NOT greet the user, say thank you, or add any notes.\n"
        "- DO NOT provide any introduction to the application or summary of its functionality.\n"
        "- If you cannot generate the code, respond only with: ERROR: Unable to generate main.dart code.\n\n"
        "IMPORTANT: All Dart code MUST comply with Dart 3+ null safety.\n"
        "- Every non-nullable field must be either initialized with a default value, marked as nullable (with ?), or set as required in the constructor.\n"
        "- DO NOT leave any non-nullable field uninitialized.\n"
        "- Code must build successfully with Flutter 3.10+ and Dart 3.7+.\n\n"
        "EXAMPLE FORMAT:\n\n"
        "FILENAME: main.dart\n"
        "````dart\n"
        "// ... main.dart code here ...\n"
        "````\n"
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
        error_details = {
            "url": ANTHROPIC_API_URL,
            "status_code": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None,
            "response_body": getattr(e.response, 'text', None) if hasattr(e, 'response') else None,
            "error": str(e)
        }
        print(f"Error calling Claude API: {json.dumps(error_details, indent=2)}")
        return {"error": f"Error calling Claude API: {e}"}, 500, None
    except Exception as e:
        print(f"Unexpected error calling Claude API at {ANTHROPIC_API_URL}: {str(e)}")
        return {"error": f"An unexpected error occurred: {e}"}, 500, None

# --- Helper: Parse AI Generated Code ---
def parse_generated_code(generated_text: str):
    files = {}
    ignored_text = []
    current_text = []
    in_code_block = False
    current_filename = None
    current_language = None
    
    # Split text into lines for processing
    lines = generated_text.split('\n')
    
    for line in lines:
        line = line.rstrip()  # Remove trailing whitespace but preserve leading
        
        # Check for code block markers
        if line.strip().startswith('```'):
            if not in_code_block:
                # Start of code block
                in_code_block = True
                # Extract filename if present (e.g., ```dart:main.dart or ```yaml:pubspec.yaml)
                parts = line.strip()[3:].split(':')
                if len(parts) > 1:
                    current_language = parts[0].strip()
                    current_filename = parts[1].strip()
                else:
                    current_language = parts[0].strip()
                continue  # Skip the marker line
            else:
                # End of code block
                in_code_block = False
                if current_filename and current_text:
                    # Only accept main.dart, pubspec.yaml, and asset files
                    if current_filename in ["main.dart", "pubspec.yaml"]:
                        files[current_filename] = '\n'.join(current_text)
                    elif "main.dart" in current_filename:
                        files["main.dart"] = '\n'.join(current_text)
                    elif "pubspec.yaml" in current_filename:
                        files["pubspec.yaml"] = '\n'.join(current_text)
                    elif current_filename.startswith("assets/"):
                        files[current_filename] = '\n'.join(current_text)
                current_text = []
                current_filename = None
                current_language = None
                continue  # Skip the marker line
            
        if in_code_block:
            current_text.append(line)
        else:
            # Collect non-code text for logging
            if line.strip() and not line.strip().startswith('FILENAME:'):
                ignored_text.append(line.strip())
    
    # Log ignored text if any
    if ignored_text:
        print("Ignored non-code text from AI response:")
        for text in ignored_text:
            print(f"- {text}")
    
    # Validate required files
    if "main.dart" not in files:
        return {"error": "Missing required file: main.dart"}
    if "pubspec.yaml" not in files:
        return {"error": "Missing required file: pubspec.yaml"}
    
    # Validate file contents
    for filename, content in files.items():
        # Check for stray backticks or markdown syntax
        if '```' in content:
            return {"error": f"Invalid content in {filename}: Contains markdown code block markers"}
        if 'FILENAME:' in content:
            return {"error": f"Invalid content in {filename}: Contains filename markers"}
        
        # Validate pubspec.yaml format
        if filename == "pubspec.yaml":
            try:
                import yaml
                yaml.safe_load(content)  # Validate YAML syntax
            except yaml.YAMLError as e:
                return {"error": f"Invalid YAML syntax in pubspec.yaml: {str(e)}"}
            
            # Check for asset references
            try:
                yaml_content = yaml.safe_load(content)
                if 'flutter' in yaml_content and 'assets' in yaml_content['flutter']:
                    assets = yaml_content['flutter']['assets']
                    for asset in assets:
                        if asset.startswith('assets/') and asset not in files:
                            return {"error": f"Missing required asset file: {asset}"}
            except Exception as e:
                return {"error": f"Error parsing pubspec.yaml assets: {str(e)}"}
        
        # Validate main.dart format and null safety
        if filename == "main.dart":
            if not content.strip().startswith('import '):
                return {"error": "Invalid main.dart: Missing import statements"}
            if 'void main()' not in content:
                return {"error": "Invalid main.dart: Missing main() function"}
            
            # Check for uninitialized non-nullable fields
            lines = content.split('\n')
            for i, line in enumerate(lines):
                line = line.strip()
                # Look for class field declarations
                if line and not line.startswith(('import ', '//', '/*', '*', '*/', 'class ', 'void ', 'return ', '}')):
                    # Check for uninitialized non-nullable fields
                    if any(field in line for field in ['double ', 'int ', 'String ', 'bool ', 'List<', 'Map<']):
                        if '?' not in line and '=' not in line and 'required' not in line:
                            return {"error": f"Invalid main.dart: Uninitialized non-nullable field at line {i+1}: {line}"}
    
    return files

# --- Helper: Git Operations ---
def update_github_repository(generated_files: dict, repo_url: str, pat: str, commit_message: str):
    if not pat or not repo_url:
        return False, "GitHub PAT or Repository URL not configured."
    
    temp_dir = f"/tmp/ideaforge_repo_{uuid.uuid4()}"
    try:
        # Clone the repo
        auth_repo_url = repo_url.replace("https://", f"https://oauth2:{pat}@")
        subprocess.run(["git", "clone", "--depth=1", auth_repo_url, temp_dir], check=True, capture_output=True, text=True)
        
        # Switch to generated-app branch or create it if it doesn't exist
        subprocess.run(["git", "checkout", "-b", "generated-app"], cwd=temp_dir, check=True, capture_output=True, text=True)
        
        # Only update specific files
        for filename, content in generated_files.items():
            file_path = ""
            if filename == "main.dart":
                file_path = os.path.join(temp_dir, "lib", filename)
                # Ensure lib directory exists
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
            elif filename == "pubspec.yaml":
                file_path = os.path.join(temp_dir, filename)
            else:
                # Handle asset files
                if filename.startswith("assets/"):
                    file_path = os.path.join(temp_dir, filename)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                else:
                    print(f"Skipping non-standard file: {filename}")
                    continue
            
            # Write the file with proper line endings
            with open(file_path, "w", newline='\n') as f:
                f.write(content)
        
        # Git commit and push
        subprocess.run(["git", "add", "."], cwd=temp_dir, check=True, capture_output=True, text=True)
        
        # Check if there are changes to commit
        status_result = subprocess.run(["git", "status", "--porcelain"], cwd=temp_dir, check=True, capture_output=True, text=True)
        if not status_result.stdout.strip():
            print("No changes to commit.")
            return True, "No changes to commit."
        
        # Commit and push changes
        subprocess.run(["git", "commit", "-m", commit_message], cwd=temp_dir, check=True, capture_output=True, text=True)
        subprocess.run(["git", "push", "-u", "origin", "generated-app", "--force"], cwd=temp_dir, check=True, capture_output=True, text=True)
        
        return True, "Successfully updated files in GitHub repository."
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
    
    # Assuming the cloudbuild.yaml is in the root of the repository
    source = RepoSource(
        project_id=project_id,
        repo_name=repo_url.split("/")[-1].replace(".git", ""),
        branch_name=branch_name,
    )

    build = Build(
        source=source,
    )
    
    try:
        operation = client.create_build(project_id=project_id, build=build)
        print(f"Triggered Cloud Build. Operation: {operation.name}")
        # For simplicity, we return the operation name. Client might need to poll for completion.
        # Or, the backend can poll here.
        build_id = operation.metadata.build.id
        return build_id, f"Build triggered successfully. Build ID: {build_id}"
    except Exception as e:
        error_message = f"Error triggering Cloud Build: {e}"
        print(error_message)
        return None, error_message

# --- Helper: List Latest APKs in GCS ---
def list_latest_apks(bucket_name: str, prefix: str = "ideaforge-builds/") -> list:
    """
    Lists the latest APK files in the specified GCS bucket.
    Returns a list of (blob_name, signed_url) tuples.
    """
    credentials = get_gcp_credentials()
    if not credentials:
        return []
    
    storage_client = storage.Client(credentials=credentials)
    bucket = storage_client.bucket(bucket_name)
    
    try:
        blobs = list(bucket.list_blobs(prefix=prefix))
        apk_blobs = [(blob.name, blob.generate_signed_url(version="v4", expiration=3600)) 
                    for blob in blobs if blob.name.endswith('.apk')]
        return sorted(apk_blobs, key=lambda x: x[0], reverse=True)
    except Exception as e:
        print(f"Error listing APKs: {e}")
        return []

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
            # Look for APK artifacts in the build results
            if build_info.results and build_info.results.artifacts:
                for artifact in build_info.results.artifacts.objects:
                    if artifact.location.startswith(f"gs://{gcs_bucket_name}/") and artifact.location.endswith(".apk"):
                        blob_name = artifact.location[len(f"gs://{gcs_bucket_name}/"):]
                        bucket = storage_client.bucket(gcs_bucket_name)
                        blob = bucket.blob(blob_name)
                        apk_url = blob.generate_signed_url(version="v4", expiration=3600)
                        print(f"Found APK artifact: {blob_name}")
                        break
            
            # If no artifact found in build results, try listing the bucket
            if not apk_url:
                apks = list_latest_apks(gcs_bucket_name)
                if apks:
                    apk_url = apks[0][1]  # Get the signed URL of the latest APK
                    print(f"Found latest APK via bucket listing")

        return status, build_info.log_url, apk_url

    except Exception as e:
        error_message = f"Error getting build status: {e}"
        print(error_message)
        return "ERROR", None, None

# --- Helper: Validate and Fix Dart Null Safety ---
def validate_and_fix_dart_null_safety(content: str) -> tuple[bool, str, str]:
    """
    Validates and attempts to fix non-nullable fields in Dart code.
    Returns (success, fixed_content, error_message)
    """
    lines = content.split('\n')
    fixed_lines = []
    errors = []
    
    # Common non-nullable types to check
    non_nullable_types = [
        'double', 'int', 'String', 'bool', 'Color', 'List<', 'Map<',
        'Widget', 'BuildContext', 'State<', 'Key', 'Duration'
    ]
    
    for i, line in enumerate(lines):
        line = line.rstrip()
        original_line = line
        
        # Skip comments, imports, and other non-field declarations
        if any(line.strip().startswith(prefix) for prefix in ['//', '/*', '*', '*/', 'import ', 'class ', 'void ', 'return ', '}']):
            fixed_lines.append(line)
            continue
            
        # Check for uninitialized non-nullable fields
        for type_name in non_nullable_types:
            if f"{type_name} " in line and '?' not in line and '=' not in line and 'required' not in line:
                # Try to determine if it's a field declaration
                if ';' in line and not any(keyword in line for keyword in ['void', 'return', 'if', 'for', 'while']):
                    errors.append(f"Line {i+1}: Non-nullable field without initialization: {line.strip()}")
                    # Don't add the line to fixed_lines, effectively removing it
                    continue
        
        fixed_lines.append(line)
    
    if errors:
        error_message = "Code contains non-nullable fields without initialization:\n" + "\n".join(errors)
        return False, content, error_message
    
    return True, '\n'.join(fixed_lines), ""

@app.route("/api/v1/generate-app-real-build", methods=["POST"])
def generate_app_real_build():
    try:
        data = request.get_json()
        user_prompt = data.get("prompt")
        user_id = data.get("user_id", str(uuid.uuid4()))
        
        # Call Claude API
        api_response, status_code, generated_text = call_claude_api(user_prompt, user_id)
        if status_code != 200:
            return jsonify({"error": api_response.get("error", "Failed to generate code")}), status_code
        
        # Parse generated code
        files = parse_generated_code(generated_text)
        if "error" in files:
            return jsonify({"error": files["error"]}), 400
        
        # Validate and fix Dart null safety
        if "main.dart" in files:
            success, fixed_content, error_message = validate_and_fix_dart_null_safety(files["main.dart"])
            if not success:
                return jsonify({"error": error_message}), 400
            files["main.dart"] = fixed_content
        
        # Log successful extraction
        print(f"Successfully extracted files: {list(files.keys())}")
        
        # Update GitHub repository
        success, message = update_github_repository(files, GITHUB_REPO_URL, GITHUB_PAT, "Update Flutter app files")
        if not success:
            return jsonify({"error": message}), 500
        
        # Trigger Cloud Build
        build_id, build_message = trigger_cloud_build(GCP_PROJECT_ID, GITHUB_REPO_URL)
        if not build_id:
            return jsonify({"error": build_message}), 500
        
        # Store initial build status
        build_statuses[build_id] = {
            "status": "PENDING",
            "message": "Build triggered successfully"
        }
        
        return jsonify({
            "status": "success",
            "build_id": build_id,
            "message": "Build triggered successfully"
        })
        
    except Exception as e:
        print(f"Error in generate_app_real_build: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/build-status/<build_id>", methods=["GET"])
def get_build_status(build_id):
    try:
        # Check if we have stored status for this build
        if build_id not in build_statuses:
            return jsonify({
                "error": "Build ID not found",
                "build_id": build_id
            }), 404

        build_info = build_statuses[build_id]
        
        # If build is complete and we have a download URL
        if build_info["status"] == "SUCCESS" and "download_url" in build_info:
            return jsonify({
                "status": "success",
                "build_id": build_id,
                "download_url": build_info["download_url"]
            })
        
        # For builds in progress or failed
        return jsonify({
            "status": build_info["status"],
            "build_id": build_id
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/cloud-build-webhook", methods=["POST"])
def cloud_build_webhook():
    try:
        # Get the JSON payload from the request
        payload = request.get_json()
        
        # Extract the message data from Pub/Sub format
        if not payload or 'message' not in payload:
            return jsonify({"error": "Invalid payload format"}), 400
            
        # Decode the base64-encoded message data
        message_data = base64.b64decode(payload['message']['data']).decode('utf-8')
        build_data = json.loads(message_data)
        
        # Extract build information
        build_id = build_data.get('id')
        status = build_data.get('status')
        
        if not build_id or not status:
            return jsonify({"error": "Missing build ID or status"}), 400
            
        # Store the build status
        build_statuses[build_id] = {"status": status}
            
        # If build was successful, get the APK download URL
        if status == "SUCCESS":
            status, log_url, apk_url = get_cloud_build_status_and_apk_url(GCP_PROJECT_ID, build_id, GCS_BUCKET_NAME)
            if apk_url:
                # Store the download URL
                build_statuses[build_id]["download_url"] = apk_url
                return jsonify({
                    "status": "success",
                    "build_id": build_id,
                    "download_url": apk_url
                })
            else:
                return jsonify({
                    "status": "error",
                    "build_id": build_id,
                    "error": "APK not found in build artifacts"
                }), 500
        else:
            # For non-success statuses, return the status and build ID
            return jsonify({
                "status": status,
                "build_id": build_id
            })
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/list-apks", methods=["GET"])
def list_apks():
    """Endpoint to list available APKs in the GCS bucket"""
    try:
        apks = list_latest_apks(GCS_BUCKET_NAME)
        return jsonify({
            "status": "success",
            "apks": [{"name": name, "url": url} for name, url in apks]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Log startup information
    print(f"Starting Flask app on 0.0.0.0:{PORT}")
    print(f"Environment: {'Production' if os.getenv('FLASK_ENV') == 'production' else 'Development'}")
    print(f"Debug mode: {'Enabled' if os.getenv('FLASK_DEBUG') == '1' else 'Disabled'}")
    
    # Start the app immediately
    app.run(host="0.0.0.0", port=PORT, debug=False)  # debug=False for production
    print(f"ANTHROPIC_API_KEY status at startup: {'Present' if ANTHROPIC_API_KEY else 'Missing'} (Length: {len(ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else 0})")
    print(f"ANTHROPIC_API_URL: {ANTHROPIC_API_URL} (Valid: {ANTHROPIC_API_URL == 'https://api.anthropic.com/v1/messages'})")
else:
    # For Cloud Run, we need to ensure the app is created
    print(f"App created for Cloud Run on port {PORT}")
    print(f"ANTHROPIC_API_KEY status at startup: {'Present' if ANTHROPIC_API_KEY else 'Missing'} (Length: {len(ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else 0})")
    print(f"ANTHROPIC_API_URL: {ANTHROPIC_API_URL} (Valid: {ANTHROPIC_API_URL == 'https://api.anthropic.com/v1/messages'})")

