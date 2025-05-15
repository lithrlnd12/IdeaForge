package com.example.ideaforge.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

// For a real app, consider using Retrofit or Ktor
// This is a simplified client for the mock backend
object MockBackendClient {
    // Ensure this matches the address your Flask backend is running on.
    // For testing with Android Emulator, "10.0.2.2" usually points to the host machine.
    // If running backend on a different machine, use its IP address.
    private const val BASE_URL = "http://10.0.2.2:5000/api/v1/"

    suspend fun sendMessageToBackend(prompt: String, userId: String = "beta_user", clarificationDone: Boolean = false): Pair<String?, JSONObject?> {
        return withContext(Dispatchers.IO) {
            var connection: HttpURLConnection? = null
            try {
                val url = URL("${BASE_URL}generate-app")
                connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type", "application/json; charset=UTF-8")
                connection.setRequestProperty("Accept", "application/json")
                connection.doOutput = true
                connection.doInput = true
                connection.connectTimeout = 15000 // 15 seconds
                connection.readTimeout = 15000    // 15 seconds

                val jsonParam = JSONObject()
                jsonParam.put("prompt", prompt)
                jsonParam.put("user_id", userId)
                if (clarificationDone) {
                    jsonParam.put("clarification_done", true)
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

