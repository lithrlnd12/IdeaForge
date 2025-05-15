package com.example.ideaforge.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

object LiveBackendClient {
    // Ensure this matches the address your Flask backend is running on.
    // For testing with Android Emulator, "10.0.2.2" usually points to the host machine.
    // The live_backend.py is set to run on port 5001.
    // For cloud deployment, use the Cloud Run URL:
    private const val BASE_URL = "https://ideaforge-backend-921972313555.us-central1.run.app/api/v1/"

    suspend fun generateAppWithLiveAI(prompt: String, userId: String = "live_user", systemPromptOverride: String? = null): Pair<String?, JSONObject?> {
        return withContext(Dispatchers.IO) {
            var connection: HttpURLConnection? = null
            try {
                val url = URL("${BASE_URL}generate-app-real-build")
                connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type", "application/json; charset=UTF-8")
                connection.setRequestProperty("Accept", "application/json")
                connection.doOutput = true
                connection.doInput = true
                connection.connectTimeout = 60000 // 60 seconds, AI generation can take time
                connection.readTimeout = 180000    // 180 seconds, AI generation can take time

                val jsonParam = JSONObject()
                jsonParam.put("prompt", prompt)
                jsonParam.put("user_id", userId)
                if (systemPromptOverride != null) {
                    jsonParam.put("system_prompt", systemPromptOverride)
                }

                val outputStreamWriter = OutputStreamWriter(connection.outputStream)
                outputStreamWriter.write(jsonParam.toString())
                outputStreamWriter.flush()
                outputStreamWriter.close()

                val responseCode = connection.responseCode
                if (responseCode == HttpURLConnection.HTTP_OK) {
                    val inputStream = BufferedReader(InputStreamReader(connection.inputStream))
                    val response = inputStream.use(BufferedReader::readText)
                    inputStream.close()
                    Pair(null, JSONObject(response))
                } else {
                    val errorStream = BufferedReader(InputStreamReader(connection.errorStream ?: connection.inputStream))
                    val errorResponse = errorStream.use(BufferedReader::readText)
                    errorStream.close()
                    Pair("Error: $responseCode - $errorResponse", null)
                }
            } catch (e: Exception) {
                e.printStackTrace()
                Pair("Exception: ${e.message}", null)
            } finally {
                connection?.disconnect()
            }
        }
    }
}

