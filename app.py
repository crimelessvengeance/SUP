import streamlit as st
import os
import tempfile
from dotenv import load_dotenv
from google import genai

load_dotenv()

# =========================
# API KEY
# =========================

try:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error("GEMINI_API_KEY was not found.")
    st.stop()

# =========================
# CONNECT TO GEMINI
# =========================

client = genai.Client(api_key=api_key)

# =========================
# AI PERSONALITY
# =========================

SYSTEM_INSTRUCTION = """
You are a smart personal AI assistant.

PERSONALITY:
- Friendly and helpful.
- Smart and confident.
- Use light humor when appropriate.
- Do not make jokes when the user is asking something serious.
- Give direct answers.
- Keep conversations natural.
- Do not overuse emojis.
- Match the user's mood.
- Do not ask unnecessary follow-up questions.

WHEN HELPING WITH STUDIES:
- Explain concepts simply.
- Give examples when useful.
- Be accurate.
- Make answers exam-friendly when requested.
- Do not add unnecessary conversation.

WHEN HELPING WITH CODING:
- Prefer beginner-friendly explanations.
- Explain errors clearly.
- Show corrected code.
- Explain important parts of the code.

GENERAL:
- Never pretend you performed an action you did not perform.
- Never make up information.
- Be honest about limitations.
- Respond naturally.
"""

# =========================
# PAGE SETTINGS
# =========================

st.set_page_config(
    page_title="SUP",
    page_icon="🤖",
    layout="centered"
)

# =========================
# TITLE
# =========================

st.title("🤖 SUP")
st.caption("Your personal AI assistant")

# =========================
# INITIALIZE SESSION STATE
# =========================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "study_file" not in st.session_state:
    st.session_state.study_file = None

if "study_file_name" not in st.session_state:
    st.session_state.study_file_name = None

# =========================
# SIDEBAR
# =========================

with st.sidebar:

    st.header("⚙️ SUP Settings")

    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

    st.divider()

    st.header("📚 Study Files")

    uploaded_file = st.file_uploader(
        "Upload your study material",
        type=[
            "pdf",
            "txt",
            "docx",
            "pptx",
            "jpg",
            "jpeg",
            "png",
            "webp",
            "py",
            "java",
            "c",
            "cpp"
        ]
    )

    if uploaded_file is not None:

        if st.session_state.study_file_name != uploaded_file.name:

            try:

                file_extension = os.path.splitext(
                    uploaded_file.name
                )[1]

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=file_extension
                ) as temp_file:

                    temp_file.write(
                        uploaded_file.getvalue()
                    )

                    temp_path = temp_file.name

                with st.spinner("📖 Reading your file..."):

                    study_file = client.files.upload(
                        file=temp_path
                    )

                os.remove(temp_path)

                st.session_state.study_file = study_file
                st.session_state.study_file_name = uploaded_file.name

                st.success(
                    f"✅ {uploaded_file.name} is ready"
                )

            except Exception as e:

                st.error(
                    f"❌ Could not upload the file:\n\n{e}"
                )

        else:

            st.success(
                f"✅ {uploaded_file.name} is ready"
            )

    if st.session_state.study_file_name:

        if st.button("❌ Remove Study File"):

            st.session_state.study_file = None
            st.session_state.study_file_name = None

            st.rerun()

# =========================
# DISPLAY CHAT HISTORY
# =========================

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.write(message["content"])

# =========================
# CHAT INPUT
# =========================

prompt = st.chat_input(
    "Ask anything..."
)

if prompt:

    # Add user message
    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    # Display user message
    with st.chat_message("user"):

        st.write(prompt)

    # =========================
    # PREPARE GEMINI CONTENT
    # =========================

    contents = []

    # System instruction
    contents.append(
        {
            "role": "user",
            "parts": [
                {
                    "text": SYSTEM_INSTRUCTION
                }
            ]
        }
    )

    contents.append(
        {
            "role": "model",
            "parts": [
                {
                    "text": "Understood."
                }
            ]
        }
    )

    # Conversation history
    for message in st.session_state.messages:

        role = "user"

        if message["role"] == "assistant":
            role = "model"

        contents.append(
            {
                "role": role,
                "parts": [
                    {
                        "text": message["content"]
                    }
                ]
            }
        )

    # =========================
    # GENERATE RESPONSE
    # =========================

    try:

        # If a study file exists,
        # send it together with the user's question.
        if st.session_state.study_file is not None:

            contents.append(
                st.session_state.study_file
            )

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=contents
        )

        answer = response.text

    except Exception as e:

        answer = (
            "Sorry, something went wrong.\n\n"
            f"{e}"
        )

    # =========================
    # SAVE ASSISTANT RESPONSE
    # =========================

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer
        }
    )

    # Display response
    with st.chat_message("assistant"):

        st.write(answer)
