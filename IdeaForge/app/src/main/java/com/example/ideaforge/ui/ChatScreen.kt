package com.example.ideaforge.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp
import androidx.compose.ui.tooling.preview.Preview
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.ideaforge.ui.theme.IdeaForgeTheme
import com.example.ideaforge.viewmodel.ChatViewModel
import kotlinx.coroutines.launch

// Updated Message data class to include isCodeBlock
data class Message(
    val id: String,
    val text: String,
    val author: String,
    val timestamp: Long = System.currentTimeMillis(),
    val isApkLink: Boolean = false,
    val isCodeBlock: Boolean = false // Added for special rendering of code
) {
    companion object {
        const val AUTHOR_USER = "user"
        const val AUTHOR_AI = "ai"
        const val AUTHOR_SYSTEM = "system" // For status updates and code blocks
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(chatViewModel: ChatViewModel = viewModel()) {
    // Correctly observe messages from the ViewModel which uses mutableStateListOf
    val messages: List<Message> = chatViewModel.messages
    var inputText by remember { mutableStateOf(TextFieldValue("")) }
    val listState = rememberLazyListState()
    val coroutineScope = rememberCoroutineScope()
    val context = LocalContext.current

    // Scroll to bottom when new messages are added
    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            coroutineScope.launch {
                listState.animateScrollToItem(messages.size - 1)
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Idea Forge (Live AI)") }, // Updated title
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    titleContentColor = MaterialTheme.colorScheme.primary,
                )
            )
        },
        bottomBar = {
            ChatInputBox(value = inputText, onValueChange = { inputText = it }) {
                if (inputText.text.isNotBlank()) {
                    chatViewModel.sendMessage(inputText.text)
                    inputText = TextFieldValue("") // Clear input field
                }
            }
        }
    ) { recationPadding ->
        Column(modifier = Modifier
            .fillMaxSize()
            .padding(recationPadding)) {
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp),
                reverseLayout = false
            ) {
                items(messages) { message ->
                    MessageBubble(message) {
                        if (message.isApkLink && message.text.contains("http")) { // Check if it actually contains a link
                            try {
                                // Extract URL more robustly
                                val urlToOpen = message.text.substringAfter("APK ready for download: ").trim()
                                if (urlToOpen.startsWith("http://") || urlToOpen.startsWith("https://")){
                                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(urlToOpen))
                                    context.startActivity(intent)
                                } else {
                                    println("Invalid URL format: $urlToOpen")
                                }
                            } catch (e: Exception) {
                                println("Error opening link: ${e.message}")
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun MessageBubble(message: Message, onClick: () -> Unit) {
    val horizontalArrangement = when (message.author) {
        Message.AUTHOR_USER -> Arrangement.End
        else -> Arrangement.Start
    }
    val bubbleColor = when (message.author) {
        Message.AUTHOR_USER -> MaterialTheme.colorScheme.primaryContainer
        Message.AUTHOR_AI -> MaterialTheme.colorScheme.secondaryContainer
        else -> MaterialTheme.colorScheme.tertiaryContainer 
    }
    val textColor = when (message.author) {
        Message.AUTHOR_USER -> MaterialTheme.colorScheme.onPrimaryContainer
        Message.AUTHOR_AI -> MaterialTheme.colorScheme.onSecondaryContainer
        else -> MaterialTheme.colorScheme.onTertiaryContainer
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = horizontalArrangement
    ) {
        Card(
            shape = MaterialTheme.shapes.medium,
            colors = CardDefaults.cardColors(containerColor = bubbleColor),
            modifier = Modifier.clickable(enabled = message.isApkLink, onClick = onClick)
        ) {
            if (message.isCodeBlock) {
                SelectionContainer {
                    Text(
                        text = message.text,
                        modifier = Modifier.padding(12.dp).background(MaterialTheme.colorScheme.surfaceVariant),
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        style = MaterialTheme.typography.bodyMedium.copy(fontFamily = FontFamily.Monospace)
                    )
                }
            } else {
                Text(
                    text = message.text,
                    modifier = Modifier.padding(12.dp),
                    color = textColor,
                    style = MaterialTheme.typography.bodyLarge
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatInputBox(value: TextFieldValue, onValueChange: (TextFieldValue) -> Unit, onSend: () -> Unit) {
    Surface(shadowElevation = 8.dp) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            TextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier.weight(1f),
                placeholder = { Text("Describe your app or game...") }, // Updated placeholder
                colors = TextFieldDefaults.textFieldColors(), // Use default colors
                shape = MaterialTheme.shapes.medium,
                maxLines = 5
            )
            Spacer(modifier = Modifier.width(8.dp))
            Button(onClick = onSend) {
                Text("Send")
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun ChatScreenPreview() {
    IdeaForgeTheme {
        // Preview will use the default ViewModel with initial messages
        ChatScreen(chatViewModel = ChatViewModel()) // Ensure ViewModel is instantiated for preview
    }
}

@Preview(showBackground = true)
@Composable
fun MessageBubbleUserPreview() {
    IdeaForgeTheme {
        MessageBubble(Message("1", "Hello AI!", Message.AUTHOR_USER)) {}
    }
}

@Preview(showBackground = true)
@Composable
fun MessageBubbleAIPreview() {
    IdeaForgeTheme {
        MessageBubble(Message("2", "Hello User! How can I help?", Message.AUTHOR_AI)) {}
    }
}

@Preview(showBackground = true)
@Composable
fun MessageBubbleSystemPreview() {
    IdeaForgeTheme {
        MessageBubble(Message("3", "System update: Processing your request...", Message.AUTHOR_SYSTEM)) {}
    }
}

@Preview(showBackground = true)
@Composable
fun MessageBubbleCodeBlockPreview() {
    IdeaForgeTheme {
        MessageBubble(Message("4", "```dart\nvoid main() {\n  print(\"Hello, Flutter!\");\n}\n```", Message.AUTHOR_SYSTEM, isCodeBlock = true)) {}
    }
}

