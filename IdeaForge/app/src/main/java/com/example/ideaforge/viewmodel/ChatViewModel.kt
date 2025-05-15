package com.example.ideaforge.viewmodel

import androidx.compose.runtime.mutableStateListOf
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.ideaforge.ui.Message // Assuming Message data class is in ui package
import com.example.ideaforge.network.LiveBackendClient
import kotlinx.coroutines.launch
import org.json.JSONObject

class ChatViewModel : ViewModel() {

    // Use mutableStateListOf for better Compose observability if items are added/removed/updated frequently
    val messages = mutableStateListOf<Message>()

    init {
        // Initial welcome message
        addMessageToList(Message(id = "0", text = "Welcome to Idea Forge (Live AI Mode)! Describe the app you want to build.", author = Message.AUTHOR_AI))
    }

    private fun addMessageToList(message: Message) {
        messages.add(message)
    }

    fun sendMessage(text: String) {
        val userMessage = Message(id = (messages.size + 1).toString(), text = text, author = Message.AUTHOR_USER)
        addMessageToList(userMessage)

        val thinkingMessageId = (messages.size + 1).toString()
        val thinkingMessage = Message(id = thinkingMessageId, text = "Idea Forge is crafting with Claude...", author = Message.AUTHOR_SYSTEM)
        addMessageToList(thinkingMessage)

        viewModelScope.launch {
            val (error, responseJson) = LiveBackendClient.generateAppWithLiveAI(prompt = text, userId = "live_user_android")

            // Remove thinking indicator
            messages.removeIf { it.id == thinkingMessageId }

            if (responseJson != null) {
                handleBackendResponse(responseJson)
            } else {
                val errorMessageText = error ?: "An unknown error occurred connecting to the live backend."
                val errorMessage = Message(id = (messages.size + 1).toString(), text = errorMessageText, author = Message.AUTHOR_SYSTEM)
                addMessageToList(errorMessage)
            }
        }
    }

    private fun handleBackendResponse(responseJson: JSONObject) {
        val status = responseJson.optString("status", "error")
        val messageText = responseJson.optString("message", "No message from AI.")
        val generatedCode = responseJson.optString("generated_code_from_claude", null)
        val apkUrl = responseJson.optString("apk_download_url", null)
        val modelUsed = responseJson.optString("model_used", "Unknown Model")
        val usage = responseJson.optJSONObject("claude_usage")

        // Main AI response message
        val aiResponseMessageText = if (status.startsWith("success")) messageText else "AI Response: $messageText (Status: $status)"
        val aiResponseMessage = Message(id = (messages.size + 1).toString(), text = aiResponseMessageText, author = Message.AUTHOR_AI)
        addMessageToList(aiResponseMessage)

        // Display generated code if available
        if (generatedCode != null && generatedCode.isNotBlank()) {
            val codeDisplayMessage = Message(
                id = (messages.size + 1).toString(),
                text = "Claude ($modelUsed) generated the following code:\n\n$generatedCode",
                author = Message.AUTHOR_SYSTEM, // Or AUTHOR_AI, depending on how you want to style it
                isCodeBlock = true // Add a flag to Message data class if you want special rendering
            )
            addMessageToList(codeDisplayMessage)
        }

        // Display APK download link if available
        if (apkUrl != null) {
            val apkMessage = Message(
                id = (messages.size + 1).toString(),
                text = "Simulated APK ready for download: $apkUrl", 
                author = Message.AUTHOR_SYSTEM,
                isApkLink = true
            )
            addMessageToList(apkMessage)
        }
        
        // Optionally display usage stats
        if (usage != null) {
            val usageMessage = Message(
                id = (messages.size + 1).toString(),
                text = "Claude API Usage: Input Tokens: ${usage.optInt("input_tokens")}, Output Tokens: ${usage.optInt("output_tokens")}",
                author = Message.AUTHOR_SYSTEM
            )
            addMessageToList(usageMessage)
        }
    }
}

