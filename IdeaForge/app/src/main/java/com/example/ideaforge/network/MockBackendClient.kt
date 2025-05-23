package com.example.ideaforge.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import android.util.Log
import com.example.ideaforge.BuildConfig

// For a real app, consider using Retrofit or Ktor
// This is a simplified client for the mock backend
object MockBackendClient {
    // Default local development URL for Android Emulator
    private const val LOCAL_BASE_URL = "http://10.0.2.2:8080/api/v1/"
    
    // Get BASE_URL from BuildConfig or use default
    private val BASE_URL: String = BuildConfig.MOCK_BACKEND_URL.ifEmpty { LOCAL_BASE_URL }.apply {
        Log.d("MockBackendClient", "Using mock backend URL: $this")
    }

    suspend fun sendMessageToBackend(prompt: String, userId: String = "beta_user", clarificationDone: Boolean = false): Pair<String?, JSONObject?> {
        return withContext(Dispatchers.IO) {
            var connection: HttpURLConnection? = null
            try {
                val url = URL("${BASE_URL}generate-app-real-build")
                Log.d("MockBackendClient", "Making request to: $url")
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

