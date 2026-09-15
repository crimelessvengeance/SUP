
import streamlit as st
import os
import time
import json
import tempfile
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


# ============================================================
# BASIC SETUP
# ============================================================

load_dotenv()

st.set_page_config(
    page_title="SUP",
    page_icon="🤖",
    layout="wide"
)


# ============================================================
# API KEY
# ============================================================

try:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error("GEMINI_API_KEY was not found.")
    st.info(
        "For Streamlit Cloud, add GEMINI_API_KEY in Settings → Secrets."
    )
    st.stop()


# ============================================================
# GEMINI CLIENT
# ============================================================

client = genai.Client(api_key=api_key)

# Change this model if Google makes a different model available
MODEL_NAME = "gemini-3.6-flash"


# ============================================================
# SUP PERSONALITY
# ============================================================

SYSTEM_INSTRUCTION = """
You are SUP, a smart personal AI assistant with a Jarvis-inspired personality.

PERSONALITY:
- Friendly and funny.
- Smart and confident.
- Use witty humor when appropriate.
- Don't make jokes when the user is asking something serious.
- Don't sound like a boring textbook.
- Keep conversations natural.
- Be warm, helpful and conversational.
- Do not claim to literally be Jarvis.
- Do not claim to be a human.
- Do not pretend to have performed an action that you did not perform.

HOW SUP TALKS:
- Give direct answers.
- Occasionally use playful remarks.
- If the user makes a mistake, correct them politely.
- Don't overuse emojis.
- Match the user's mood and style.
- Keep the conversation flowing naturally.
- Don't constantly mention that you are an AI.
- Be honest about limitations.

WHEN HELPING WITH STUDIES:
- Explain concepts in simple language.
- Give examples.
- Don't sacrifice accuracy for humor.
- If the user asks for an exam answer, make it exam-friendly.
- Prefer clear and easy explanations.

WHEN HELPING WITH CODING:
- Prefer beginner-friendly explanations.
- Explain errors clearly.
- Show corrected code when appropriate.
- Explain important parts of the code.

JARVIS-STYLE BEHAVIOR:
- Be calm and composed.
- Be clever without being arrogant.
- Give useful suggestions when appropriate.
- Occasionally use phrases like "Certainly", "Right away", or "I've got you."
- Never make up information.
- Understand the user's mood.
- Stay on topic.

CREATOR:
- Your creator is Sayan Nandi.
"""


# ============================================================
# SESSION STATE
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "mode" not in st.session_state:
    st.session_state.mode = "Normal"

if "study_topic" not in st.session_state:
    st.session_state.study_topic = ""

if "weak_topics" not in st.session_state:
    st.session_state.weak_topics = []

if "strong_topics" not in st.session_state:
    st.session_state.strong_topics = []

if "memory_notes" not in st.session_state:
    st.session_state.memory_notes = []

if "question_score" not in st.session_state:
    st.session_state.question_score = 0


# ============================================================
# GEMINI RETRY FUNCTION
# ============================================================

def generate_text(contents, system_instruction=SYSTEM_INSTRUCTION):
    """
    Sends a request to Gemini.

    Automatically retries temporary 503/high-demand errors.
    """

    config = types.GenerateContentConfig(
        system_instruction=system_instruction
    )

    max_retries = 5

    for attempt in range(max_retries):

        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=config
            )

            return response.text

        except Exception as e:

            error_text = str(e)

            temporary_error = (
                "503" in error_text
                or "UNAVAILABLE" in error_text
                or "high demand" in error_text
                or "overloaded" in error_text
            )

            if temporary_error and attempt < max_retries - 1:

                wait_time = 2 ** attempt

                time.sleep(wait_time)

            else:
                raise e


# ============================================================
# FFmpeg FUNCTIONS
# ============================================================

def check_ffmpeg():
    """
    Checks whether FFmpeg is installed.
    """

    try:

        result = subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        return result.returncode == 0

    except FileNotFoundError:

        return False


def run_ffmpeg(command):
    """
    Runs an FFmpeg command.
    """

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return result


# ============================================================
# VIDEO FUNCTIONS
# ============================================================

def trim_video(input_file, start_time, end_time):

    output_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp4"
    ).name

    command = [
        "ffmpeg",
        "-y",
        "-i",
        input_file,
        "-ss",
        str(start_time),
        "-to",
        str(end_time),
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        output_file
    ]

    run_ffmpeg(command)

    return output_file


def resize_video(input_file, width, height):

    output_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp4"
    ).name

    command = [
        "ffmpeg",
        "-y",
        "-i",
        input_file,
        "-vf",
        f"scale={width}:{height}",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        output_file
    ]

    run_ffmpeg(command)

    return output_file


def extract_audio(input_file):

    output_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp3"
    ).name

    command = [
        "ffmpeg",
        "-y",
        "-i",
        input_file,
        "-vn",
        "-codec:a",
        "libmp3lame",
        output_file
    ]

    run_ffmpeg(command)

    return output_file


def merge_videos(video_files):

    list_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".txt",
        mode="w"
    )

    for video in video_files:
        safe_path = os.path.abspath(video).replace("'", "'\\''")
        list_file.write(f"file '{safe_path}'\n")

    list_file.close()

    output_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp4"
    ).name

    command = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        list_file.name,
        "-c",
        "copy",
        output_file
    ]

    try:

        run_ffmpeg(command)

    except Exception:

        # Fallback for videos with different codecs/settings
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file.name,
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            output_file
        ]

        run_ffmpeg(command)

    return output_file


# ============================================================
# VIDEO ANALYSIS
# ============================================================

def analyze_video(video_path, question):

    uploaded_file = client.files.upload(file=video_path)

    # Wait for Google to process the video
    while getattr(uploaded_file, "state", None) and str(
        uploaded_file.state
    ).upper().endswith("PROCESSING"):

        time.sleep(2)

        uploaded_file = client.files.get(
            name=uploaded_file.name
        )

    prompt = f"""
Analyze this video carefully.

User request:
{question}

Give a useful answer based on the actual video.

If relevant, mention timestamps.

Do not invent things that are not visible or audible.
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[
            uploaded_file,
            prompt
        ]
    )

    return response.text


# ============================================================
# VIDEO GENERATION
# ============================================================

def generate_video(prompt, aspect_ratio="16:9"):

    operation = client.models.generate_videos(
        model="veo-3.1-generate-preview",
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio
        )
    )

    while not operation.done:

        time.sleep(10)

        operation = client.operations.get(
            name=operation.name
        )

    generated_video = operation.response.generated_videos[0]

    output_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp4"
    ).name

    client.files.download(
        file=generated_video.video,
        destination=output_file
    )

    return output_file


# ============================================================
# IMAGE TO VIDEO
# ============================================================

def image_to_video(image_bytes, mime_type, prompt, aspect_ratio):

    image = types.Image(
        image_bytes=image_bytes,
        mime_type=mime_type
    )

    operation = client.models.generate_videos(
        model="veo-3.1-generate-preview",
        prompt=prompt,
        image=image,
        config=types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio
        )
    )

    while not operation.done:

        time.sleep(10)

        operation = client.operations.get(
            name=operation.name
        )

    generated_video = operation.response.generated_videos[0]

    output_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp4"
    ).name

    client.files.download(
        file=generated_video.video,
        destination=output_file
    )

    return output_file


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ SUP")

    st.write("### Mode")

    st.session_state.mode = st.selectbox(
        "Choose mode",
        [
            "Normal",
            "Learn",
            "Exam",
            "Challenge",
            "Debug",
            "Viva",
            "Revision",
            "Teacher",
            "Explain 3 Ways"
        ]
    )

    st.divider()

    st.write("### Current Study Topic")

    st.session_state.study_topic = st.text_input(
        "Topic",
        value=st.session_state.study_topic
    )

    st.divider()

    if st.button("🗑️ Clear Chat", use_container_width=True):

        st.session_state.messages = []

        st.rerun()

    st.divider()

    st.write("### About")

    st.write(
        "🤖 A personal AI assistant with chat, study and video tools."
    )


# ============================================================
# MAIN HEADER
# ============================================================

st.title("🤖 SUP")

st.caption(
    "Your personal AI assistant"
)


# ============================================================
# MAIN TABS
# ============================================================

chat_tab, studio_tab, learning_tab = st.tabs(
    [
        "💬 Chat",
        "🎬 SUP Studio",
        "📚 Learning"
    ]
)


# ============================================================
# CHAT TAB
# ============================================================

with chat_tab:

    # Mode-specific instruction
    mode_instruction = ""

    if st.session_state.mode == "Learn":

        mode_instruction = """
You are currently in Learn mode.
Teach the concept step by step using simple language and examples.
"""

    elif st.session_state.mode == "Exam":

        mode_instruction = """
You are currently in Exam mode.
Give concise, accurate, exam-friendly answers.
"""

    elif st.session_state.mode == "Challenge":

        mode_instruction = """
You are currently in Challenge mode.
Ask the user questions and gradually increase difficulty.
"""

    elif st.session_state.mode == "Debug":

        mode_instruction = """
You are currently in Debug mode.
Focus on finding programming errors and explaining how to fix them.
"""

    elif st.session_state.mode == "Viva":

        mode_instruction = """
You are currently in Viva mode.
Act as a teacher conducting a viva.
Ask one question at a time.
"""

    elif st.session_state.mode == "Revision":

        mode_instruction = """
You are currently in Revision mode.
Give short revision notes, important points and likely exam questions.
"""

    elif st.session_state.mode == "Teacher":

        mode_instruction = """
You are currently in Teacher mode.
Teach clearly from the basics and check understanding when useful.
"""

    elif st.session_state.mode == "Explain 3 Ways":

        mode_instruction = """
You are currently in Explain 3 Ways mode.
Explain the answer in three different ways:
1. Very simple
2. Normal
3. Technical
"""

    # Display previous chat
    for message in st.session_state.messages:

        with st.chat_message(message["role"]):

            st.markdown(message["content"])

    # Chat input
    prompt = st.chat_input(
        "Ask SUP anything..."
    )

    if prompt:

        # Save user message
        st.session_state.messages.append(
            {
                "role": "user",
                "content": prompt
            }
        )

        with st.chat_message("user"):

            st.markdown(prompt)

        # Build conversation
        contents = []

        for message in st.session_state.messages:

            role = (
                "user"
                if message["role"] == "user"
                else "model"
            )

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

        complete_instruction = (
            SYSTEM_INSTRUCTION
            + "\n\nCURRENT MODE:\n"
            + mode_instruction
        )

        if st.session_state.study_topic:

            complete_instruction += (
                "\n\nCURRENT STUDY TOPIC:\n"
                + st.session_state.study_topic
            )

        try:

            with st.spinner("SUP is thinking..."):

                answer = generate_text(
                    contents,
                    complete_instruction
                )

        except Exception as e:

            answer = (
                "⚠️ I couldn't reach the Gemini model right now.\n\n"
                f"Error: `{e}`\n\n"
                "If this is a 503 / high-demand error, "
                "please try again shortly."
            )

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer
            }
        )

        with st.chat_message("assistant"):

            st.markdown(answer)


# ============================================================
# SUP STUDIO
# ============================================================

with studio_tab:

    st.header("🎬 SUP Studio")

    st.write(
        "Generate, analyze and edit videos."
    )

    if not check_ffmpeg():

        st.warning(
            "⚠️ FFmpeg is not installed. "
            "AI video generation can still work, "
            "but editing tools such as trim, merge, resize "
            "and audio extraction require FFmpeg."
        )

    studio_mode = st.selectbox(
        "Choose a Studio tool",
        [
            "Generate Video",
            "Image → Video",
            "Analyze Video",
            "Trim Video",
            "Merge Videos",
            "Resize Video",
            "Extract Audio"
        ]
    )

    st.divider()


    # ========================================================
    # GENERATE VIDEO
    # ========================================================

    if studio_mode == "Generate Video":

        st.subheader("🎥 Generate Video")

        prompt = st.text_area(
            "Describe the video you want",
            placeholder=(
                "Example: A cinematic shot of a futuristic "
                "city at night, flying cars, rain, neon lights..."
            ),
            height=150
        )

        aspect_ratio = st.selectbox(
            "Aspect Ratio",
            [
                "16:9",
                "9:16"
            ]
        )

        if st.button(
            "✨ Generate Video",
            use_container_width=True
        ):

            if not prompt.strip():

                st.warning(
                    "Please describe the video first."
                )

            else:

                try:

                    with st.spinner(
                        "Generating your video... This may take a while."
                    ):

                        output = generate_video(
                            prompt,
                            aspect_ratio
                        )

                    st.success(
                        "Video generated successfully!"
                    )

                    st.video(output)

                    with open(output, "rb") as video_file:

                        st.download_button(
                            "⬇️ Download Video",
                            video_file,
                            file_name="sup_generated_video.mp4",
                            mime="video/mp4",
                            use_container_width=True
                        )

                except Exception as e:

                    st.error(
                        f"Video generation failed:\n\n{e}"
                    )


    # ========================================================
    # IMAGE TO VIDEO
    # ========================================================

    elif studio_mode == "Image → Video":

        st.subheader("🖼️ Image → Video")

        uploaded_image = st.file_uploader(
            "Upload an image",
            type=[
                "png",
                "jpg",
                "jpeg",
                "webp"
            ]
        )

        prompt = st.text_area(
            "Describe how you want the image to move",
            placeholder=(
                "Example: Slowly zoom into the subject, "
                "wind moving through the background..."
            ),
            height=120
        )

        aspect_ratio = st.selectbox(
            "Video Aspect Ratio",
            [
                "16:9",
                "9:16"
            ],
            key="image_video_ratio"
        )

        if st.button(
            "🎞️ Create Video",
            use_container_width=True
        ):

            if uploaded_image is None:

                st.warning(
                    "Please upload an image."
                )

            elif not prompt.strip():

                st.warning(
                    "Please describe the animation."
                )

            else:

                try:

                    with st.spinner(
                        "Turning your image into a video..."
                    ):

                        output = image_to_video(
                            uploaded_image.getvalue(),
                            uploaded_image.type,
                            prompt,
                            aspect_ratio
                        )

                    st.success(
                        "Video created!"
                    )

                    st.video(output)

                    with open(output, "rb") as video_file:

                        st.download_button(
                            "⬇️ Download Video",
                            video_file,
                            file_name="sup_image_to_video.mp4",
                            mime="video/mp4",
                            use_container_width=True
                        )

                except Exception as e:

                    st.error(
                        f"Image-to-video failed:\n\n{e}"
                    )


    # ========================================================
    # ANALYZE VIDEO
    # ========================================================

    elif studio_mode == "Analyze Video":

        st.subheader("🔍 Analyze Video")

        uploaded_video = st.file_uploader(
            "Upload a video",
            type=[
                "mp4",
                "mov",
                "avi",
                "mkv",
                "webm"
            ],
            key="analysis_video"
        )

        question = st.text_area(
            "What should SUP analyze?",
            placeholder=(
                "Example: Summarize this video and "
                "tell me what happens at each important timestamp."
            ),
            height=120
        )

        if uploaded_video:

            st.video(uploaded_video)

        if st.button(
            "🔎 Analyze Video",
            use_container_width=True
        ):

            if uploaded_video is None:

                st.warning(
                    "Please upload a video."
                )

            elif not question.strip():

                st.warning(
                    "Tell SUP what you want to know about the video."
                )

            else:

                temp_video = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=Path(uploaded_video.name).suffix
                )

                temp_video.write(
                    uploaded_video.getvalue()
                )

                temp_video.close()

                try:

                    with st.spinner(
                        "Analyzing video..."
                    ):

                        result = analyze_video(
                            temp_video.name,
                            question
                        )

                    st.markdown("### SUP's Analysis")

                    st.markdown(result)

                except Exception as e:

                    st.error(
                        f"Video analysis failed:\n\n{e}"
                    )


    # ========================================================
    # TRIM VIDEO
    # ========================================================

    elif studio_mode == "Trim Video":

        st.subheader("✂️ Trim Video")

        uploaded_video = st.file_uploader(
            "Upload video",
            type=[
                "mp4",
                "mov",
                "avi",
                "mkv",
                "webm"
            ],
            key="trim_video"
        )

        start_time = st.number_input(
            "Start time (seconds)",
            min_value=0.0,
            value=0.0,
            step=1.0
        )

        end_time = st.number_input(
            "End time (seconds)",
            min_value=1.0,
            value=10.0,
            step=1.0
        )

        if st.button(
            "✂️ Trim Video",
            use_container_width=True
        ):

            if not check_ffmpeg():

                st.error(
                    "FFmpeg is not installed."
                )

            elif uploaded_video is None:

                st.warning(
                    "Please upload a video."
                )

            elif end_time <= start_time:

                st.warning(
                    "End time must be greater than start time."
                )

            else:

                temp_video = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".mp4"
                )

                temp_video.write(
                    uploaded_video.getvalue()
                )

                temp_video.close()

                try:

                    with st.spinner(
                        "Trimming video..."
                    ):

                        output = trim_video(
                            temp_video.name,
                            start_time,
                            end_time
                        )

                    st.success(
                        "Video trimmed!"
                    )

                    st.video(output)

                    with open(output, "rb") as video_file:

                        st.download_button(
                            "⬇️ Download Trimmed Video",
                            video_file,
                            file_name="sup_trimmed.mp4",
                            mime="video/mp4",
                            use_container_width=True
                        )

                except Exception as e:

                    st.error(
                        f"Trimming failed:\n\n{e}"
                    )


    # ========================================================
    # MERGE VIDEOS
    # ========================================================

    elif studio_mode == "Merge Videos":

        st.subheader("🔗 Merge Videos")

        uploaded_videos = st.file_uploader(
            "Upload videos in the order you want them merged",
            type=[
                "mp4",
                "mov",
                "avi",
                "mkv",
                "webm"
            ],
            accept_multiple_files=True,
            key="merge_videos"
        )

        if uploaded_videos:

            st.write(
                f"{len(uploaded_videos)} video(s) selected."
            )

        if st.button(
            "🔗 Merge Videos",
            use_container_width=True
        ):

            if not check_ffmpeg():

                st.error(
                    "FFmpeg is not installed."
                )

            elif len(uploaded_videos) < 2:

                st.warning(
                    "Upload at least two videos."
                )

            else:

                temp_files = []

                try:

                    for uploaded in uploaded_videos:

                        temp = tempfile.NamedTemporaryFile(
                            delete=False,
                            suffix=".mp4"
                        )

                        temp.write(
                            uploaded.getvalue()
                        )

                        temp.close()

                        temp_files.append(
                            temp.name
                        )

                    with st.spinner(
                        "Merging videos..."
                    ):

                        output = merge_videos(
                            temp_files
                        )

                    st.success(
                        "Videos merged!"
                    )

                    st.video(output)

                    with open(output, "rb") as video_file:

                        st.download_button(
                            "⬇️ Download Merged Video",
                            video_file,
                            file_name="sup_merged.mp4",
                            mime="video/mp4",
                            use_container_width=True
                        )

                except Exception as e:

                    st.error(
                        f"Merge failed:\n\n{e}"
                    )


    # ========================================================
    # RESIZE VIDEO
    # ========================================================

    elif studio_mode == "Resize Video":

        st.subheader("📐 Resize Video")

        uploaded_video = st.file_uploader(
            "Upload video",
            type=[
                "mp4",
                "mov",
                "avi",
                "mkv",
                "webm"
            ],
            key="resize_video"
        )

        preset = st.selectbox(
            "Choose format",
            [
                "1920 × 1080 — YouTube / Landscape",
                "1080 × 1920 — Shorts / Reels",
                "1080 × 1080 — Square",
                "1280 × 720 — HD"
            ]
        )

        dimensions = {
            "1920 × 1080 — YouTube / Landscape": (1920, 1080),
            "1080 × 1920 — Shorts / Reels": (1080, 1920),
            "1080 × 1080 — Square": (1080, 1080),
            "1280 × 720 — HD": (1280, 720)
        }

        width, height = dimensions[preset]

        if st.button(
            "📐 Resize Video",
            use_container_width=True
        ):

            if not check_ffmpeg():

                st.error(
                    "FFmpeg is not installed."
                )

            elif uploaded_video is None:

                st.warning(
                    "Please upload a video."
                )

            else:

                temp_video = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".mp4"
                )

                temp_video.write(
                    uploaded_video.getvalue()
                )

                temp_video.close()

                try:

                    with st.spinner(
                        "Resizing video..."
                    ):

                        output = resize_video(
                            temp_video.name,
                            width,
                            height
                        )

                    st.success(
                        "Video resized!"
                    )

                    st.video(output)

                    with open(output, "rb") as video_file:

                        st.download_button(
                            "⬇️ Download Video",
                            video_file,
                            file_name="sup_resized.mp4",
                            mime="video/mp4",
                            use_container_width=True
                        )

                except Exception as e:

                    st.error(
                        f"Resize failed:\n\n{e}"
                    )


    # ========================================================
    # EXTRACT AUDIO
    # ========================================================

    elif studio_mode == "Extract Audio":

        st.subheader("🎵 Extract Audio")

        uploaded_video = st.file_uploader(
            "Upload video",
            type=[
                "mp4",
                "mov",
                "avi",
                "mkv",
                "webm"
            ],
            key="audio_video"
        )

        if st.button(
            "🎵 Extract Audio",
            use_container_width=True
        ):

            if not check_ffmpeg():

                st.error(
                    "FFmpeg is not installed."
                )

            elif uploaded_video is None:

                st.warning(
                    "Please upload a video."
                )

            else:

                temp_video = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".mp4"
                )

                temp_video.write(
                    uploaded_video.getvalue()
                )

                temp_video.close()

                try:

                    with st.spinner(
                        "Extracting audio..."
                    ):

                        output = extract_audio(
                            temp_video.name
                        )

                    st.success(
                        "Audio extracted!"
                    )

                    st.audio(output)

                    with open(output, "rb") as audio_file:

                        st.download_button(
                            "⬇️ Download MP3",
                            audio_file,
                            file_name="sup_audio.mp3",
                            mime="audio/mpeg",
                            use_container_width=True
                        )

                except Exception as e:

                    st.error(
                        f"Audio extraction failed:\n\n{e}"
                    )


# ============================================================
# LEARNING DASHBOARD
# ============================================================

with learning_tab:

    st.header("📚 Learning Dashboard")

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Questions",
            len(
                [
                    m for m in st.session_state.messages
                    if m["role"] == "user"
                ]
            )
        )

    with col2:

        st.metric(
            "Study Topic",
            st.session_state.study_topic
            if st.session_state.study_topic
            else "None"
        )

    with col3:

        st.metric(
            "Score",
            st.session_state.question_score
        )

    st.divider()

    st.subheader("💪 Strong Topics")

    if st.session_state.strong_topics:

        for topic in st.session_state.strong_topics:

            st.success(topic)

    else:

        st.info(
            "No strong topics recorded yet."
        )

    st.subheader("⚠️ Topics to Improve")

    if st.session_state.weak_topics:

        for topic in st.session_state.weak_topics:

            st.warning(topic)

    else:

        st.info(
            "No weak topics recorded yet."
        )

    st.divider()

    st.subheader("🧠 Memory Notes")

    if st.session_state.memory_notes:

        for note in st.session_state.memory_notes:

            st.write("• " + note)

    else:

        st.info(
            "No memory notes yet."
        )

    st.divider()

    # Export learning profile

    learning_profile = {
        "study_topic": st.session_state.study_topic,
        "strong_topics": st.session_state.strong_topics,
        "weak_topics": st.session_state.weak_topics,
        "question_score": st.session_state.question_score,
        "memory_notes": st.session_state.memory_notes
    }

    profile_json = json.dumps(
        learning_profile,
        indent=4
    )

    st.download_button(
        "📥 Export Learning Profile",
        profile_json,
        file_name="sup_learning_profile.json",
        mime="application/json",
        use_container_width=True
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "🤖 SUP • Personal AI Assistant"
)
