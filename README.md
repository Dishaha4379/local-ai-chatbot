# Local AI Chatbot 
A locally hosted AI chatbot built using **Python, Streamlit, Ollama, and SQLite**. The application allows users to interact with an AI language model, manage multiple conversations, and store chat history locally.
The chatbot uses the **Llama 3.2** model through Ollama, so responses are generated locally without requiring an external AI API key.
🚀 Features
- **AI-powered conversations:** Generate responses using the Llama 3.2 language model.
- **Local AI processing:** Run the language model through Ollama on your own machine.
- **Multiple conversations:** Create and switch between different chat sessions.
- **Chat history:** Store conversations locally using SQLite.
- **Persistent storage:** Previous conversations remain available when the application is restarted.
- **Background response generation:** Generate responses without blocking the Streamlit interface.
- **Conversation management:** Manage and organize chat sessions.
🛠️ Technologies Used
| Technology | Purpose |
|---|---|
| Python | Core programming language |
| Streamlit | Web application interface |
| Ollama | Run the local language model |
| Llama 3.2 | Large language model |
| SQLite | Store chat history |
| ThreadPoolExecutor | Background task execution |
📁 Project Structure
Chatbot1/
├── app.py
├── requirements.txt
├── .gitignore
└── README.md
```
The SQLite database (`chat_history.db`) is created locally when the application runs and is not included in this repository.

## ⚙️ Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/local-ai-chatbot.git
```

### 2. Navigate to the project folder

```bash
cd local-ai-chatbot
```

### 3. Install Python dependencies

```bash
py -m pip install -r requirements.txt
```

### 4. Install Ollama

Download and install Ollama from:

https://ollama.com/

### 5. Download the Llama 3.2 model

```bash
ollama pull llama3.2
```

### 6. Run the chatbot

```bash
py -m streamlit run app.py
```

The application will open in your default browser.

## 🧠 How It Works

1. The user enters a message through the Streamlit interface.
2. The application retrieves the relevant conversation history from SQLite.
3. The conversation is sent to the Llama 3.2 model through Ollama.
4. Ollama generates an AI response locally.
5. The response is displayed in the Streamlit interface.
6. User messages and AI responses are stored in SQLite for future conversations.

## 🔮 Future Improvements

- Add
