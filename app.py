
import streamlit as st
import ollama
import sqlite3
import time

from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager


# ==========================================
# 1. CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="My AI Chatbot",
    page_icon="🤖",
    layout="wide"
)

DB_PATH = Path(__file__).parent / "chat_history.db"
MODEL = "llama3.2"


# ==========================================
# 2. DATABASE CONNECTION
# ==========================================

@contextmanager
def get_db():

    conn = sqlite3.connect(DB_PATH, timeout=20)

    try:
        yield conn
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def initialize_database():

    with get_db() as conn:

        conn.execute("PRAGMA journal_mode=WAL")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chats(id)
            )
        """)

        # Track background AI generations
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generation_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                assistant_message_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                error TEXT,
                created_at TEXT NOT NULL
            )
        """)


# ==========================================
# 3. CHAT DATABASE FUNCTIONS
# ==========================================

def create_chat():

    now = datetime.now().isoformat(timespec="seconds")

    with get_db() as conn:

        cursor = conn.execute(
            """
            INSERT INTO chats (title, created_at, updated_at)
            VALUES (?, ?, ?)
            """,
            ("New Chat", now, now)
        )

        return cursor.lastrowid


def get_chats():

    with get_db() as conn:

        return conn.execute(
            """
            SELECT id, title
            FROM chats
            ORDER BY updated_at DESC
            """
        ).fetchall()


def rename_chat(chat_id, title):

    with get_db() as conn:

        conn.execute(
            "UPDATE chats SET title = ? WHERE id = ?",
            (title[:40], chat_id)
        )


def delete_chat(chat_id):

    with get_db() as conn:

        conn.execute(
            "DELETE FROM generation_jobs WHERE chat_id = ?",
            (chat_id,)
        )

        conn.execute(
            "DELETE FROM messages WHERE chat_id = ?",
            (chat_id,)
        )

        conn.execute(
            "DELETE FROM chats WHERE id = ?",
            (chat_id,)
        )


def update_chat_title(chat_id, title):

    with get_db() as conn:

        conn.execute(
            """
            UPDATE chats
            SET title = ?
            WHERE id = ? AND title = 'New Chat'
            """,
            (title[:40], chat_id)
        )


# ==========================================
# 4. MESSAGE DATABASE FUNCTIONS
# ==========================================

def get_messages(chat_id):

    with get_db() as conn:

        rows = conn.execute(
            """
            SELECT id, role, content
            FROM messages
            WHERE chat_id = ?
            ORDER BY id
            """,
            (chat_id,)
        ).fetchall()

    return [
        {
            "id": row[0],
            "role": row[1],
            "content": row[2]
        }
        for row in rows
    ]


def save_message(chat_id, role, content):

    now = datetime.now().isoformat(timespec="seconds")

    with get_db() as conn:

        cursor = conn.execute(
            """
            INSERT INTO messages (chat_id, role, content)
            VALUES (?, ?, ?)
            """,
            (chat_id, role, content)
        )

        conn.execute(
            "UPDATE chats SET updated_at = ? WHERE id = ?",
            (now, chat_id)
        )

        return cursor.lastrowid


def update_message(message_id, content):

    with get_db() as conn:

        conn.execute(
            "UPDATE messages SET content = ? WHERE id = ?",
            (content, message_id)
        )


# ==========================================
# 5. BACKGROUND AI GENERATION
# ==========================================

# Keep the executor alive across Streamlit reruns.
@st.cache_resource
def get_executor():

    return ThreadPoolExecutor(max_workers=3)


def create_generation_job(chat_id, conversation):

    # Create an empty assistant message immediately.
    assistant_id = save_message(
        chat_id,
        "assistant",
        ""
    )

    now = datetime.now().isoformat(timespec="seconds")

    with get_db() as conn:

        conn.execute(
            """
            INSERT INTO generation_jobs
            (chat_id, assistant_message_id, status, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, assistant_id, "running", now)
        )

    # Start generation in a background thread.
    executor = get_executor()

    executor.submit(
        generate_response_background,
        chat_id,
        assistant_id,
        conversation
    )

    return assistant_id


def generate_response_background(
    chat_id,
    assistant_id,
    conversation
):

    response = ""
    last_save_time = time.monotonic()

    try:

        stream = ollama.chat(
            model=MODEL,
            messages=conversation,
            stream=True
        )

        for chunk in stream:

            content = chunk["message"]["content"]

            if not content:
                continue

            response += content

            # Save partial response periodically.
            if time.monotonic() - last_save_time >= 0.4:

                update_message(
                    assistant_id,
                    response
                )

                last_save_time = time.monotonic()

        # Always save the final response.
        update_message(
            assistant_id,
            response
        )

        with get_db() as conn:

            conn.execute(
                """
                UPDATE generation_jobs
                SET status = 'completed'
                WHERE assistant_message_id = ?
                """,
                (assistant_id,)
            )

    except Exception as e:

        error_message = f"Sorry, something went wrong: {e}"

        update_message(
            assistant_id,
            response + "\n\n" + error_message
        )

        with get_db() as conn:

            conn.execute(
                """
                UPDATE generation_jobs
                SET status = 'failed', error = ?
                WHERE assistant_message_id = ?
                """,
                (str(e), assistant_id)
            )


# ==========================================
# 6. GENERATION STATUS
# ==========================================

def get_job_statuses(chat_id):

    with get_db() as conn:

        rows = conn.execute(
            """
            SELECT assistant_message_id, status
            FROM generation_jobs
            WHERE chat_id = ?
            """,
            (chat_id,)
        ).fetchall()

    return {
        message_id: status
        for message_id, status in rows
    }


def has_running_job(chat_id):

    with get_db() as conn:

        result = conn.execute(
            """
            SELECT COUNT(*)
            FROM generation_jobs
            WHERE chat_id = ? AND status = 'running'
            """,
            (chat_id,)
        ).fetchone()

    return result[0] > 0


# ==========================================
# 7. INITIALIZE APP
# ==========================================

initialize_database()

if "active_chat_id" not in st.session_state:

    chats = get_chats()

    if chats:
        st.session_state.active_chat_id = chats[0][0]

    else:
        st.session_state.active_chat_id = create_chat()


# Make sure the active chat still exists.
chats = get_chats()
chat_ids = [chat[0] for chat in chats]

if st.session_state.active_chat_id not in chat_ids:

    if chats:
        st.session_state.active_chat_id = chats[0][0]

    else:
        st.session_state.active_chat_id = create_chat()


# ==========================================
# 8. CUSTOM CSS
# ==========================================

st.markdown("""
<style>

.block-container {
    padding-top: 2rem;
}

[data-testid="stSidebar"] {
    padding-top: 1rem;
}

/* Natural-looking chat names */
[data-testid="stSidebar"] [class*="st-key-select_chat_"] button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: inherit !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 8px 10px !important;
    min-height: 38px !important;
}

[data-testid="stSidebar"] [class*="st-key-select_chat_"] button:hover {
    background: rgba(128, 128, 128, 0.16) !important;
}

[data-testid="stSidebar"] [class*="st-key-select_chat_"] p {
    text-align: left !important;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# 9. SIDEBAR
# ==========================================

with st.sidebar:

    st.title("🤖 My AI Chatbot")

    if st.button("＋ New Chat", use_container_width=True):

        st.session_state.active_chat_id = create_chat()
        st.rerun()

    st.divider()

    st.subheader("Your conversations")

    chats = get_chats()

    for chat_id, title in chats:

        col1, col2 = st.columns([5, 1])

        with col1:

            if st.button(
                title,
                key=f"select_chat_{chat_id}",
                use_container_width=True
            ):

                st.session_state.active_chat_id = chat_id
                st.rerun()

        with col2:

            with st.popover("⋯"):

                st.write("Chat options")

                new_title = st.text_input(
                    "Chat name",
                    value=title,
                    key=f"rename_input_{chat_id}"
                )

                if st.button(
                    "Save name",
                    key=f"rename_button_{chat_id}",
                    use_container_width=True
                ):

                    if new_title.strip():

                        rename_chat(
                            chat_id,
                            new_title.strip()
                        )

                        st.rerun()

                st.divider()

                confirm_delete = st.checkbox(
                    "Confirm deletion",
                    key=f"confirm_delete_{chat_id}"
                )

                if st.button(
                    "Delete chat",
                    key=f"delete_button_{chat_id}",
                    disabled=not confirm_delete,
                    type="primary",
                    use_container_width=True
                ):

                    delete_chat(chat_id)

                    if st.session_state.active_chat_id == chat_id:

                        remaining = get_chats()

                        if remaining:
                            st.session_state.active_chat_id = remaining[0][0]

                        else:
                            st.session_state.active_chat_id = create_chat()

                    st.rerun()

    st.divider()

    st.caption("Powered by Ollama • Llama 3.2")


# ==========================================
# 10. CHAT DISPLAY
# ==========================================

chat_id = st.session_state.active_chat_id


def display_chat(chat_id):

    # Get latest chat title.
    with get_db() as conn:

        chat = conn.execute(
            "SELECT title FROM chats WHERE id = ?",
            (chat_id,)
        ).fetchone()

    if chat:
        st.title(chat[0])
    else:
        st.title("My AI Chatbot")

    st.caption("Ask me anything!")

    messages = get_messages(chat_id)
    job_statuses = get_job_statuses(chat_id)

    for message in messages:

        with st.chat_message(message["role"]):

            if message["content"]:

                st.markdown(message["content"])

            elif job_statuses.get(message["id"]) == "running":

                st.markdown("*Thinking...*")

    # Show background generation status.
    if has_running_job(chat_id):

        st.caption("⏳ AI is generating a response...")


# Automatically refresh the chat display every second
# when supported by the installed Streamlit version.

if hasattr(st, "fragment"):

    @st.fragment(run_every="1s")
    def render_chat(chat_id):
        display_chat(chat_id)

else:

    def render_chat(chat_id):
        display_chat(chat_id)


render_chat(st.session_state.active_chat_id)


# ==========================================
# 11. CHAT INPUT
# ==========================================

chat_id = st.session_state.active_chat_id

if prompt := st.chat_input("Message your AI assistant..."):

    # Save user message immediately.
    previous_messages = get_messages(chat_id)

    save_message(
        chat_id,
        "user",
        prompt
    )

    # Give the chat a title based on the first message.
    if not previous_messages:
        update_chat_title(chat_id, prompt)

    # Build conversation history.
    conversation = get_messages(chat_id)

    # Do not send empty placeholder messages to Ollama.
    conversation = [
        {
            "role": message["role"],
            "content": message["content"]
        }
        for message in conversation
        if message["content"].strip()
    ]

    # Start background generation.
    try:

        create_generation_job(
            chat_id,
            conversation
        )

    except Exception as e:

        st.error(f"Could not start AI generation: {e}")

    st.rerun()
