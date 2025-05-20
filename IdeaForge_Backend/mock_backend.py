from flask import Flask, request, jsonify
import time
import random

app = Flask(__name__)

# Predefined sample APKs (replace with actual URLs if you host them)
# For now, these are just placeholders.
SAMPLE_APKS = {
    "calculator": "https://example.com/apks/sample_calculator.apk",
    "todo": "https://example.com/apks/sample_todo_list.apk",
    "gallery": "https://example.com/apks/sample_gallery.apk",
    "default": "https://example.com/apks/sample_generic_app.apk"
}

@app.route('/api/v1/generate-app', methods=['POST'])
def generate_app():
    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({"error": "No prompt provided"}), 400

    prompt = data['prompt'].lower()
    user_id = data.get('user_id', 'test_user')

    # Simulate AI processing and asking clarifying questions
    if "weather" in prompt and "clarification_done" not in data:
        time.sleep(1)
        return jsonify({
            "status": "clarification_needed",
            "message": "To create a weather app, should I get the user's current location or allow them to search for a city?",
            "next_action": "send_clarification_response"
        })

    # Simulate stages of app generation
    # Stage 1: Analyzing requirements
    # (No explicit message for this, but we can log it server-side)
    print(f"User {user_id} prompted: {prompt}")
    print("Stage: Analyzing requirements...")
    time.sleep(random.uniform(1, 2)) # Simulate work

    # Stage 2: Simulating code generation
    print("Stage: Simulating code generation...")
    # Send a status update to the client (client would need to poll or use websockets for real-time)
    # For this simple mock, we'll just proceed.
    time.sleep(random.uniform(2, 4)) # Simulate work

    # Stage 3: Simulating APK build
    print("Stage: Simulating APK build...")
    time.sleep(random.uniform(3, 5)) # Simulate work

    # Determine which sample APK to return based on prompt keywords
    apk_url = SAMPLE_APKS["default"]
    if "calculator" in prompt:
        apk_url = SAMPLE_APKS["calculator"]
    elif "todo" in prompt or "to-do" in prompt or "list" in prompt:
        apk_url = SAMPLE_APKS["todo"]
    elif "gallery" in prompt or "photo" in prompt or "image" in prompt:
        apk_url = SAMPLE_APKS["gallery"]
    
    print(f"Providing APK: {apk_url}")

    response_data = {
        "status": "success",
        "message": "Your app has been generated!",
        "apk_download_url": apk_url,
        "app_name": prompt.split(" ")[2] if len(prompt.split(" ")) > 2 else "GeneratedApp", # simple name extraction
        "version": "1.0.0-beta"
    }
    return jsonify(response_data)

if __name__ == '__main__':
    # IMPORTANT: Listen on 0.0.0.0 to be accessible within the sandbox network
    # and potentially exposed externally if needed for testing with a real device.
    app.run(host='0.0.0.0', port=5000, debug=True)

