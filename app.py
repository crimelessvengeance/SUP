import streamlit as st
import os
import tempfile
from dotenv import load_dotenv
from google import genai

load_dotenv()

# API key
api_key = st.secrets["GEMINI_API_KEY"]

if not api_key:
    st.error("GEMINI_API_KEY was not found in your .env file.")
    st.stop()

# Connect to Gemini
client = genai.Client(api_key=api_key)

# SUP personality
SYSTEM_INSTRUCTION = """
You are a smart personal AI assistant with a Jarvis-inspired personality.

PERSONALITY:
- Friendly and funny.
- Smart and confident.
- Use witty humor when appropriate.
- Don't make jokes when the user is asking something serious.
- Don't sound like a boring textbook.
- Keep conversations natural.

HOW YOU TALK:
- Sometimes chat casually like a friend.
- Act friendly and warm.
- Give direct answers instead of unnecessary introductions.
- Occasionally use playful remarks.
- If the user makes a mistake, correct them politely.
- If something is obvious, you can make a light joke about it.
- Don't overuse emojis.
- Don't repeat the same jokes or phrases.
- Match the user's mood and style.
- Don't ask too many follow-up questions.
- Behave naturally.
- Think and respond naturally.
- Go with the flow of the conversation.
- Never break the topic or mood.

WHEN HELPING WITH STUDIES:
- Explain concepts in simple language.
- Give examples.
- Don't sacrifice accuracy for humor.
- Don't be overly flirty or distracting while answering study questions.
- If the user asks for an exam answer, make it exam-friendly.
- Just write the answer and don't ask unnecessary follow-ups.

WHEN HELPING WITH CODING:
- Prefer beginner-friendly explanations.
- Explain errors clearly.
- Don't just give code; explain what important parts do.
- If the user's code has a mistake, point it out and show the correction.

JARVIS-STYLE BEHAVIOR:
- Be calm and composed.
- Be clever without being arrogant.
- Give useful suggestions when appropriate.
- Occasionally use phrases like "Certainly", "Right away", or "I've got you."
- Do not imitate or claim to literally be Jarvis.
- Use emojis occasionally.

IMPORTANT:
- Never pretend to have performed an action that you did not actually perform.
- Never make up information when you are unsure.
- Be honest about your limitations.
- Understand the mood of the user and answer accordingly.
- Your creator is Sayan Nandi.
"""

# Page settings
st.set_page_config(
    page_title="SUP",
    page_icon="🤖",
    layout="centered"
)

# Title
st.title("🤖 SUP")
st.caption("Your personal AI assistant")

# Sidebar
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

        if (
            "study_file_name" not in st.session_state
            or st.session_state.study_file_name != uploaded_file.name
        ):

            try:
                file_extension = os.path.splitext(uploaded_file.name)[1]

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=file_extension
                ) as temp_file:
                    temp_file.write(uploaded_file.getvalue())
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
                    f"❌ Could not read the file:\n\n{e}"
                )

        else:
            st.success(
                f"✅ {uploaded_file.name} is ready"
            )

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Chat input
prompt = st.chat_input("Ask anything...")

if prompt:

    # Add user message
    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })

    with st.chat_message("user"):
        st.write(prompt)

    # Prepare conversation
    contents = [
        {
            "role": "user",
            "parts": [
                {
                    "text": SYSTEM_INSTRUCTION
                }
            ]
        },
        {
            "role": "model",
            "parts": [
                {
                    "text": "Understood."
                }
            ]
        }
    ]

    # Add chat history
    for message in st.session_state.messages:
        role = "user" if message["role"] == "user" else "model"

        contents.append({
            "role": role,
            "parts": [
                {
                    "text": message["content"]
                }
            ]
        })

    # Ask Gemini
    try:

        # Add uploaded study file if available
        if "study_file" in st.session_state:
            contents.append(
                st.session_state.study_file
            )

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=contents
        )

        answer = response.text

    except Exception as e:
        answer = f"Sorry, something went wrong:\n\n{e}"

    # Save response
    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })

    # Display response
    with st.chat_message("assistant"):
        st.write(answer)
```

### The specific error

Your original code had this:

```python
try:
               if "study_file" in st.session_state:

                 contents.append(
                 st.session_state.study_file
            )

        response = client.models.generate_content(
```

Python expects everything inside `try:` to have consistent indentation.

It should be:

```python
try:

    if "study_file" in st.session_state:
        contents.append(
            st.session_state.study_file
        )

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=contents
    )
```

So **replace the whole file**, save it, and redeploy Streamlit. That should remove the `IndentationError` errors you've been getting.

