# Claude API Integration Plan for Idea Forge

## 1. AI Model Selection

*   **Model Choice:** Based on user request for "Claude's best coding model" and Anthropic's documentation, we will target **`claude-3-opus-20240229`**. This model is described as Anthropic's highest-performing model, suitable for complex analysis and higher-order math and coding tasks.
    *   An alternative strong candidate is `claude-3-5-sonnet-20240620`, which is newer and also highlighted for coding. If Opus proves too slow or costly for the desired interaction speed, Sonnet 3.5 could be considered.
*   **API Key:** The user has provided an API key: `[REMOVED_SECRET]`. This key must be handled securely.

## 2. API Endpoint

*   The primary endpoint for interacting with Claude models via the Messages API is:
    `https://api.anthropic.com/v1/messages`

## 3. Request Structure (Messages API)

Requests will be made as HTTP POST requests with a JSON body.

*   **Headers:**
    *   `x-api-key: $ANTHROPIC_API_KEY` (The API key provided by the user)
    *   `anthropic-version: 2023-06-01` (Or the latest recommended version)
    *   `content-type: application/json`
*   **Body (JSON):**
    ```json
    {
      "model": "claude-3-opus-20240229",
      "max_tokens": 4096, // Adjust as needed, max for Opus is 200k context, but output is limited per call.
      "messages": [
        {"role": "user", "content": "User's prompt for app generation..."}
        // Potentially include previous conversation history here for context
        // {"role": "assistant", "content": "Previous AI response..."},
        // {"role": "user", "content": "User's follow-up..."}
      ],
      "system": "You are Idea Forge, an expert Flutter application developer. Your goal is to generate complete, correct, and well-structured Flutter code based on the user's requirements. Ensure the code is production-ready and follows best practices. Provide the entire application code, split into appropriate files if necessary. If multiple files are generated, clearly indicate the filename and path for each code block. The primary language is Dart for Flutter. Aim to create a fully functional application component or a complete simple application.", // System prompt to guide AI behavior
      "temperature": 0.5, // Adjust for creativity vs. determinism. Lower for code generation.
      "tool_choice": {"type": "auto"} // If we plan to use tools later
      // "tools": [] // Define tools here if using tool_choice
    }
    ```

## 4. Response Structure (Messages API)

The API will respond with a JSON object.

*   **Success Response (Example Structure):**
    ```json
    {
      "id": "msg_01Xg9PAA5s22ac79hp4h980X",
      "type": "message",
      "role": "assistant",
      "model": "claude-3-opus-20240229",
      "content": [
        {
          "type": "text",
          "text": "Here is the Flutter code for your application...\n\n**main.dart:**\n```dart\n// Dart code for main.dart\n```\n\n**another_file.dart:**\n```dart\n// Dart code for another_file.dart\n```"
        }
        // Potentially "tool_use" blocks if tools are used
      ],
      "stop_reason": "end_turn" | "max_tokens" | "tool_use",
      "stop_sequence": null,
      "usage": {
        "input_tokens": 120,
        "output_tokens": 350
      }
    }
    ```
*   **Error Response:** Errors will also be in JSON format, typically including a `type: "error"` and an `error` object with `type` and `message` fields.

## 5. API Key Management

*   The API key (`[REMOVED_SECRET]`) must **NEVER** be hardcoded into the client-side (Android app) or version-controlled source code.
*   **Backend Implementation:** The Python Flask backend will read the API key from an environment variable (e.g., `ANTHROPIC_API_KEY`).
*   **Local Development:** Developers will set this environment variable locally (e.g., in their shell profile, or using a `.env` file loaded by the Python application with a library like `python-dotenv`). The `.env` file itself should be added to `.gitignore`.
*   **Production Deployment:** In a production environment, the API key will be configured as an environment variable through the hosting platform's interface.

## 6. Key Considerations for Code Generation

*   **Prompt Engineering:** The system prompt and user prompts will need to be carefully crafted to guide Claude to generate Flutter code, handle file structures, and produce the desired output format.
*   **Output Parsing:** The backend will need to parse Claude's response, which might include multiple code blocks for different files. A consistent format for specifying filenames in the AI's output will be important.
*   **Iterative Refinement & Error Handling:** The user requested that the AI attempt to fix errors. This will require a loop where the backend: 
    1.  Sends the prompt to Claude.
    2.  Receives generated code.
    3.  (Future) Attempts to build/validate the code.
    4.  If errors occur, sends the code and error messages back to Claude asking for a fix.
*   **Token Limits:** Be mindful of `max_tokens` for output and the overall context window of the model. For large applications, generation might need to be broken down into smaller, manageable parts.

This plan will guide the integration of the Claude API into the Idea Forge backend.
