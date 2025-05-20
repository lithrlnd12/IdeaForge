import os
import requests
import json
import time # Added for simulating build delay
import random # Added for simulating build delay
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-3-opus-20240229" # Or "claude-3-5-sonnet-20240620"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

# Store conversation history in memory for simplicity in this version
conversation_history = {}

# Predefined sample APKs for the simulated build service
SAMPLE_APKS = {
    "calculator": "https://example.com/apks/live_sample_calculator.apk",
    "todo": "https://example.com/apks/live_sample_todo_list.apk",
    "gallery": "https://example.com/apks/live_sample_gallery.apk",
    "game": "https://example.com/apks/live_sample_game.apk",
    "default": "https://example.com/apks/live_sample_generic_app.apk"
}

def call_claude_api(user_prompt: str, user_id: str, system_prompt: str = None):
    if not ANTHROPIC_API_KEY:
        return {"error": "Anthropic API key not configured."}, 500

    current_user_history = conversation_history.get(user_id, [])
    messages_payload = []
    if not current_user_history:
        pass 
        messages_payload.append({"role": "user", "content": user_prompt})
    else:
        messages_payload.extend(current_user_history)
        messages_payload.append({"role": "user", "content": user_prompt})

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    default_system_prompt = (
        "You are Idea Forge, an expert Flutter application developer. "
        "Your goal is to generate complete, correct, and well-structured Flutter code (Dart language) "
        "based on the user\\'s requirements. Ensure the code is production-ready and follows best practices. "
        "Provide the entire application code. If the application requires multiple files, "
        "clearly indicate the filename and path for each code block using a consistent format like: "
        "FILENAME: path/to/your/filename.dart\n```dart\n// ... your code ...\n```\n"
        "If the user asks for an app, provide the complete source code for a simple, functional Flutter app. "
        "If the user asks for a game, provide the complete source code for a simple, functional Flutter game using a suitable game engine or custom painters if simple enough."
    )

    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 4000, 
        "messages": messages_payload,
        "system": system_prompt if system_prompt else default_system_prompt,
        "temperature": 0.3 
    }

    try:
        response = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=180) 
        response.raise_for_status()  
        api_response_json = response.json()

        current_user_history.append({"role": "user", "content": user_prompt})
        if api_response_json.get("content") and isinstance(api_response_json["content"], list) and len(api_response_json["content"]) > 0:
            assistant_response_text = api_response_json["content"][0].get("text", "")
            current_user_history.append({"role": "assistant", "content": assistant_response_text})
        conversation_history[user_id] = current_user_history[-10:] 

        return api_response_json, 200
    except requests.exceptions.RequestException as e:
        print(f"Error calling Claude API: {e}")
        error_message = f"Error calling Claude API: {e}"
        if e.response is not None:
            try:
                error_details = e.response.json()
                error_message += f" - Details: {error_details}"
            except json.JSONDecodeError:
                error_message += f" - Could not decode error response: {e.response.text}"
        return {"error": error_message}, 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {"error": f"An unexpected error occurred: {e}"}, 500

@app.route("/api/v1/generate-app-live", methods=["POST"])
def generate_app_live():
    data = request.get_json()
    if not data or "prompt" not in data:
        return jsonify({"error": "No prompt provided"}), 400

    user_prompt = data["prompt"]
    user_id = data.get("user_id", "default_user")
    system_prompt_override = data.get("system_prompt", None)

    # 1. Call Claude API to generate code
    claude_response, status_code = call_claude_api(user_prompt, user_id, system_prompt_override)
    
    if status_code != 200:
        return jsonify(claude_response), status_code

    generated_text = ""
    try:
        if claude_response.get("content") and isinstance(claude_response["content"], list) and len(claude_response["content"]) > 0:
            generated_text = claude_response["content"][0].get("text", "")
        else:
            return jsonify({"error": "No content in Claude response", "raw_response": claude_response}), 500
    except (IndexError, KeyError, TypeError) as e:
        return jsonify({"error": f"Error parsing Claude response: {e}", "raw_response": claude_response}), 500

    # 2. Simulate Build Service
    print(f"Simulating build for prompt: {user_prompt}")
    # Simulate some processing time for the build
    simulated_build_time = random.uniform(15, 45) # Simulate 15-45 seconds build time
    time.sleep(simulated_build_time)
    print(f"Simulated build completed in {simulated_build_time:.2f} seconds.")

    # Determine which sample APK to return based on prompt keywords
    apk_url = SAMPLE_APKS["default"]
    prompt_lower = user_prompt.lower()
    if "calculator" in prompt_lower:
        apk_url = SAMPLE_APKS["calculator"]
    elif "todo" in prompt_lower or "to-do" in prompt_lower or "list" in prompt_lower:
        apk_url = SAMPLE_APKS["todo"]
    elif "gallery" in prompt_lower or "photo" in prompt_lower or "image" in prompt_lower:
        apk_url = SAMPLE_APKS["gallery"]
    elif "game" in prompt_lower:
        apk_url = SAMPLE_APKS["game"]

    # 3. Return response with generated code and simulated APK link
    return jsonify({
        "status": "success_simulated_build",
        "message": f"Code generated by Claude. Simulated build complete. APK available for download.",
        "generated_code_from_claude": generated_text, # The actual code from Claude
        "apk_download_url": apk_url, # Link to a sample/placeholder APK
        "model_used": CLAUDE_MODEL,
        "claude_usage": claude_response.get("usage")
    }), 200

# Placeholder for iterative error correction logic (to be developed further)
def attempt_error_correction(generated_code_with_filenames, original_prompt, user_id):
    print("Attempting error correction (conceptual)...")
    pass

if __name__ == "__main__":
    if not ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY environment variable not set.")
        print("Please create a .env file with ANTHROPIC_API_KEY=\'your_key\' or set the environment variable.")
    else:
        print(f"ANTHROPIC_API_KEY loaded. Starting Flask app on 0.0.0.0:5001 for Idea Forge Live Backend.")
        app.run(host="0.0.0.0", port=5001, debug=True)

