```python
import streamlit as st
import os
import time
import tempfile
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="SUP - AI Assistant",
    page_icon="🤖",
    layout="wide"
)


# ============================================================
# LOAD API KEY
# ============================================================

load_dotenv()

try:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    api_key = os.getenv("GEMINI_API_KEY")


if not api_key:
    st.error("GEMINI_API_KEY was not found.")

    st.info(
        "For Streamlit Cloud, add GEMINI_API_KEY under "
        "Settings → Secrets."
    )

    st.stop()


# ============================================================
# CONNECT TO GEMINI
# ============================================================

client = genai.Client(api_key=api_key)

MODEL_NAME = "gemini-3.6-flash"

VIDEO_MODEL = "veo-3.1-generate-preview"


# ============================================================
# SUP PERSONALITY
# ============================================================

SYSTEM_INSTRUCTION = """
You are SUP, a smart personal AI assistant with a Jarvis-inspired personality.

Personality:
- Friendly
- Smart
- Confident
- Slightly funny when appropriate
- Helpful and natural
- Do not overuse jokes
- Do not joke about serious topics
- Do not use too many emojis
- Do not sound like a textbook
- Give direct and practical answers
- Explain difficult topics simply when the user is learning
- Be patient with beginners
- Help with programming, studies, projects and general questions

Important:
- You are an AI assistant, not a human.
- Do not claim to have performed an action that you did not actually perform.
- If something cannot be done, explain the limitation clearly.
"""


# ============================================================
# SESSION STATE
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "study_points" not in st.session_state:
    st.session_state.study_points = 0


# ============================================================
# GEMINI TEXT GENERATION
# ============================================================

def generate_text(contents, system_instruction=SYSTEM_INSTRUCTION):

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
                or "high demand" in error_text.lower()
                or "overloaded" in error_text.lower()
            )

            if temporary_error and attempt < max_retries - 1:

                wait_time = 2 ** attempt

                st.warning(
                    f"Gemini is temporarily busy. "
                    f"Retrying in {wait_time} seconds..."
                )

                time.sleep(wait_time)

            else:
                raise e


# ============================================================
# VIDEO REQUEST DETECTION
# ============================================================

def is_video_request(text):

    text = text.lower().strip()

    video_phrases = [
        "make a video",
        "create a video",
        "generate a video",
        "generate video",
        "make video",
        "create video",
        "produce a video",
        "produce video",
        "turn this into a video",
        "turn it into a video",
        "convert this into a video",
        "animate this",
        "create an animation",
        "make an animation",
        "generate an animation",
        "make me a video",
        "create me a video",
        "generate me a video"
    ]

    for phrase in video_phrases:

        if phrase in text:
            return True

    return False


# ============================================================
# CLEAN VIDEO PROMPT
# ============================================================

def extract_video_prompt(text):

    prompt = text.strip()

    prefixes = [
        "make a video of",
        "create a video of",
        "generate a video of",
        "make video of",
        "create video of",
        "generate video of",
        "make me a video of",
        "create me a video of",
        "generate me a video of",
        "make a video",
        "create a video",
        "generate a video",
        "make video",
        "create video",
        "generate video"
    ]

    lower_prompt = prompt.lower()

    for prefix in prefixes:

        if lower_prompt.startswith(prefix):

            prompt = prompt[len(prefix):].strip()

            break

    if not prompt:

        prompt = (
            "A cinematic, visually detailed scene with "
            "professional camera movement, realistic lighting "
            "and natural motion."
        )

    return prompt


# ============================================================
# CHECK FFMPEG
# ============================================================

def check_ffmpeg():

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


# ============================================================
# RUN FFMPEG
# ============================================================

def run_ffmpeg(command):

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:

        raise RuntimeError(
            result.stderr[-3000:]
        )

    return result


# ============================================================
# SAVE UPLOADED FILE
# ============================================================

def save_uploaded_file(uploaded_file, suffix=None):

    if suffix is None:

        suffix = Path(
            uploaded_file.name
        ).suffix

    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix
    )

    temp_file.write(
        uploaded_file.getbuffer()
    )

    temp_file.close()

    return temp_file.name


# ============================================================
# VIDEO GENERATION
# ============================================================

def generate_video(
    prompt,
    aspect_ratio="16:9"
):

    operation = client.models.generate_videos(
        model=VIDEO_MODEL,
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio
        )
    )

    progress_placeholder = st.empty()

    start_time = time.time()

    while not operation.done:

        elapsed = int(
            time.time() - start_time
        )

        progress_placeholder.info(
            f"🎬 Generating video... "
            f"{elapsed}s elapsed. Please wait."
        )

        time.sleep(10)

        operation = client.operations.get(
            operation
        )

    progress_placeholder.empty()

    if operation.response is None:

        raise RuntimeError(
            "Video generation finished without a response."
        )

    generated_videos = (
        operation.response.generated_videos
    )

    if not generated_videos:

        raise RuntimeError(
            "No video was returned by Veo."
        )

    generated_video = generated_videos[0]

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

def generate_video_from_image(
    image_bytes,
    mime_type,
    prompt,
    aspect_ratio="16:9"
):

    image = types.Image(
        image_bytes=image_bytes,
        mime_type=mime_type
    )

    operation = client.models.generate_videos(
        model=VIDEO_MODEL,
        prompt=prompt,
        image=image,
        config=types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio
        )
    )

    progress_placeholder = st.empty()

    while not operation.done:

        progress_placeholder.info(
            "🎬 Creating video from your image..."
        )

        time.sleep(10)

        operation = client.operations.get(
            operation
        )

    progress_placeholder.empty()

    if operation.response is None:

        raise RuntimeError(
            "Video generation finished without a response."
        )

    generated_videos = (
        operation.response.generated_videos
    )

    if not generated_videos:

        raise RuntimeError(
            "No video was returned by Veo."
        )

    generated_video = generated_videos[0]

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
# VIDEO ANALYSIS
# ============================================================

def analyze_video(video_path, prompt):

    uploaded_file = client.files.upload(
        file=video_path
    )

    while uploaded_file.state.name == "PROCESSING":

        time.sleep(3)

        uploaded_file = client.files.get(
            name=uploaded_file.name
        )

    if uploaded_file.state.name == "FAILED":

        raise RuntimeError(
            "Gemini failed to process the uploaded video."
        )

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[
            uploaded_file,
            prompt
        ]
    )

    return response.text


# ============================================================
# TRIM VIDEO
# ============================================================

def trim_video(
    input_path,
    start_time,
    duration
):

    output_path = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp4"
    ).name

    command = [
        "ffmpeg",
        "-y",
        "-ss",
        str(start_time),
        "-i",
        input_path,
        "-t",
        str(duration),
        "-c",
        "copy",
        output_path
    ]

    try:

        run_ffmpeg(command)

    except Exception:

        command = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start_time),
            "-i",
            input_path,
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            output_path
        ]

        run_ffmpeg(command)

    return output_path


# ============================================================
# RESIZE VIDEO
# ============================================================

def resize_video(
    input_path,
    width,
    height
):

    output_path = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp4"
    ).name

    command = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-vf",
        f"scale={width}:{height}",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        output_path
    ]

    run_ffmpeg(command)

    return output_path


# ============================================================
# EXTRACT AUDIO
# ============================================================

def extract_audio(input_path):

    output_path = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp3"
    ).name

    command = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-vn",
        "-acodec",
        "mp3",
        output_path
    ]

    run_ffmpeg(command)

    return output_path


# ============================================================
# MERGE VIDEOS
# ============================================================

def merge_videos(video_paths):

    list_file = tempfile.NamedTemporaryFile(
        delete=False,
        mode="w",
        suffix=".txt"
    )

    for path in video_paths:

        clean_path = str(
            Path(path).resolve()
        ).replace("\\", "/")

        list_file.write(
            f"file '{clean_path}'\n"
        )

    list_file.close()

    output_path = tempfile.NamedTemporaryFile(
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
        output_path
    ]

    try:

        run_ffmpeg(command)

    except Exception:

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
            output_path
        ]

        run_ffmpeg(command)

    return output_path


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("🤖 SUP")

    st.caption(
        "Your personal AI assistant"
    )

    st.divider()

    mode = st.selectbox(
        "Choose Mode",
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

    st.subheader("🎬 Video")

    video_chat_enabled = st.toggle(
        "Enable video generation in chat",
        value=True
    )

    video_aspect_ratio = st.selectbox(
        "Video aspect ratio",
        [
            "16:9",
            "9:16"
        ]
    )

    st.caption(
        "When enabled, messages such as "
        "'make a video of...' are sent to Veo."
    )

    st.divider()

    st.subheader("📚 Study")

    st.metric(
        "Study Points",
        st.session_state.study_points
    )

    st.divider()

    if st.button("🗑️ Clear Chat"):

        st.session_state.messages = []

        st.rerun()


# ============================================================
# MAIN HEADER
# ============================================================

st.title("🤖 SUP")

st.caption(
    "Smart AI Assistant • Study • Code • Create • Analyze"
)


# ============================================================
# TABS
# ============================================================

tab_chat, tab_studio, tab_study = st.tabs(
    [
        "💬 AI Assistant",
        "🎬 SUP Studio",
        "📚 Learning Dashboard"
    ]
)


# ============================================================
# AI ASSISTANT TAB
# ============================================================

with tab_chat:

    st.subheader(
        f"Assistant Mode: {mode}"
    )

    # --------------------------------------------------------
    # DISPLAY PREVIOUS MESSAGES
    # --------------------------------------------------------

    for message in st.session_state.messages:

        with st.chat_message(
            message["role"]
        ):

            if message.get("type") == "video":

                st.video(
                    message["content"]
                )

            else:

                st.markdown(
                    message["content"]
                )


    # --------------------------------------------------------
    # MODE INSTRUCTIONS
    # --------------------------------------------------------

    mode_instructions = {

        "Normal":
            "Answer normally and helpfully.",

        "Learn":
            """
            Teach the topic step by step.
            Assume the student may be a beginner.
            Use simple examples.
            """,

        "Exam":
            """
            Give exam-oriented answers.
            Include definitions, important points,
            algorithms and examples where appropriate.
            """,

        "Challenge":
            """
            Turn the topic into a small challenge or quiz.
            Ask questions and make it interactive.
            """,

        "Debug":
            """
            Focus on programming debugging.
            Explain the error and provide corrected code.
            """,

        "Viva":
            """
            Act like a viva examiner.
            Ask likely questions and explain the answers.
            """,

        "Revision":
            """
            Give concise revision notes,
            key points and important formulas.
            """,

        "Teacher":
            """
            Explain like a helpful teacher.
            Start from the basics and gradually increase difficulty.
            """,

        "Explain 3 Ways":
            """
            Explain the topic in three ways:
            1. Very simple
            2. Technical
            3. Real-world example
            """
    }

    current_instruction = (
        SYSTEM_INSTRUCTION
        + "\n\nCurrent mode:\n"
        + mode_instructions[mode]
    )


    # --------------------------------------------------------
    # CHAT INPUT
    # --------------------------------------------------------

    user_prompt = st.chat_input(
        "Ask me anything..."
    )


    if user_prompt:

        # ----------------------------------------------------
        # SAVE USER MESSAGE
        # ----------------------------------------------------

        st.session_state.messages.append(
            {
                "role": "user",
                "content": user_prompt
            }
        )

        with st.chat_message("user"):

            st.markdown(
                user_prompt
            )


        # ----------------------------------------------------
        # VIDEO REQUEST
        # ----------------------------------------------------

        if (
            video_chat_enabled
            and is_video_request(user_prompt)
        ):

            with st.chat_message("assistant"):

                st.info(
                    "🎬 I detected a video-generation request. "
                    "Sending it to Veo..."
                )

                try:

                    video_prompt = extract_video_prompt(
                        user_prompt
                    )

                    video_prompt = (
                        video_prompt
                        + "\n\n"
                        + "Create a polished cinematic video "
                        + "with realistic motion, detailed visuals, "
                        + "natural camera movement, appropriate "
                        + "lighting, and suitable ambient audio."
                    )

                    output_video = generate_video(
                        video_prompt,
                        video_aspect_ratio
                    )

                    st.success(
                        "🎬 Video generated successfully!"
                    )

                    st.video(
                        output_video
                    )

                    with open(
                        output_video,
                        "rb"
                    ) as video_file:

                        st.download_button(
                            label="⬇️ Download Video",
                            data=video_file.read(),
                            file_name="generated_video.mp4",
                            mime="video/mp4"
                        )

                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "type": "video",
                            "content": output_video
                        }
                    )

                except Exception as e:

                    error_text = str(e)

                    st.error(
                        "Video generation failed."
                    )

                    st.code(
                        error_text
                    )

                    st.info(
                        "If this is a temporary 503/high-demand "
                        "error, try again after a short wait."
                    )


        # ----------------------------------------------------
        # NORMAL TEXT CHAT
        # ----------------------------------------------------

        else:

            with st.chat_message("assistant"):

                with st.spinner(
                    "Thinking..."
                ):

                    try:

                        response_text = generate_text(
                            user_prompt,
                            current_instruction
                        )

                        st.markdown(
                            response_text
                        )

                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "content": response_text
                            }
                        )

                        # Award study points for learning modes.
                        if mode in [
                            "Learn",
                            "Exam",
                            "Revision",
                            "Viva"
                        ]:

                            st.session_state.study_points += 1

                    except Exception as e:

                        st.error(
                            "Something went wrong."
                        )

                        st.code(
                            str(e)
                        )


# ============================================================
# SUP STUDIO
# ============================================================

with tab_studio:

    st.header("🎬 SUP Studio")

    st.write(
        "Create, analyze and edit videos online."
    )

    if not check_ffmpeg():

        st.warning(
            "FFmpeg is not currently available. "
            "Make sure packages.txt contains: ffmpeg"
        )

    studio_option = st.selectbox(
        "Choose a Studio tool",
        [
            "Text → Video",
            "Image → Video",
            "Analyze Video",
            "Trim Video",
            "Merge Videos",
            "Resize Video",
            "Extract Audio"
        ]
    )


    # ========================================================
    # TEXT TO VIDEO
    # ========================================================

    if studio_option == "Text → Video":

        st.subheader(
            "🎬 Text → Video"
        )

        prompt = st.text_area(
            "Describe the video",
            placeholder=(
                "Example: A cinematic drone shot "
                "of a futuristic city at sunset, "
                "with flying vehicles moving between "
                "skyscrapers."
            ),
            height=150
        )

        aspect_ratio = st.selectbox(
            "Aspect ratio",
            [
                "16:9",
                "9:16"
            ],
            key="studio_text_ratio"
        )

        if st.button(
            "🎬 Generate Video",
            type="primary"
        ):

            if not prompt.strip():

                st.warning(
                    "Please enter a video description."
                )

            else:

                try:

                    video_path = generate_video(
                        prompt,
                        aspect_ratio
                    )

                    st.success(
                        "Video generated successfully!"
                    )

                    st.video(
                        video_path
                    )

                    with open(
                        video_path,
                        "rb"
                    ) as video_file:

                        st.download_button(
                            "⬇️ Download Video",
                            video_file.read(),
                            file_name="generated_video.mp4",
                            mime="video/mp4"
                        )

                except Exception as e:

                    st.error(
                        "Video generation failed."
                    )

                    st.code(
                        str(e)
                    )


    # ========================================================
    # IMAGE TO VIDEO
    # ========================================================

    elif studio_option == "Image → Video":

        st.subheader(
            "🖼️ Image → Video"
        )

        uploaded_image = st.file_uploader(
            "Upload an image",
            type=[
                "png",
                "jpg",
                "jpeg",
                "webp"
            ]
        )

        image_prompt = st.text_area(
            "Describe how the image should move",
            placeholder=(
                "Example: Slowly zoom toward the subject "
                "while the background moves naturally."
            ),
            height=120
        )

        aspect_ratio = st.selectbox(
            "Aspect ratio",
            [
                "16:9",
                "9:16"
            ],
            key="studio_image_ratio"
        )

        if st.button(
            "🎬 Animate Image",
            type="primary"
        ):

            if uploaded_image is None:

                st.warning(
                    "Please upload an image."
                )

            elif not image_prompt.strip():

                st.warning(
                    "Please describe the animation."
                )

            else:

                try:

                    video_path = generate_video_from_image(
                        uploaded_image.getvalue(),
                        uploaded_image.type,
                        image_prompt,
                        aspect_ratio
                    )

                    st.success(
                        "Video created successfully!"
                    )

                    st.video(
                        video_path
                    )

                    with open(
                        video_path,
                        "rb"
                    ) as video_file:

                        st.download_button(
                            "⬇️ Download Video",
                            video_file.read(),
                            file_name="image_video.mp4",
                            mime="video/mp4"
                        )

                except Exception as e:

                    st.error(
                        "Image-to-video generation failed."
                    )

                    st.code(
                        str(e)
                    )


    # ========================================================
    # ANALYZE VIDEO
    # ========================================================

    elif studio_option == "Analyze Video":

        st.subheader(
            "🔍 Analyze Video"
        )

        uploaded_video = st.file_uploader(
            "Upload a video",
            type=[
                "mp4",
                "mov",
                "avi",
                "mkv",
                "webm"
            ]
        )

        analysis_prompt = st.text_area(
            "What should I analyze?",
            value=(
                "Describe what happens in the video, "
                "identify important objects and actions, "
                "and summarize the video."
            ),
            height=130
        )

        if st.button(
            "🔍 Analyze",
            type="primary"
        ):

            if uploaded_video is None:

                st.warning(
                    "Please upload a video."
                )

            else:

                try:

                    video_path = save_uploaded_file(
                        uploaded_video
                    )

                    st.video(
                        video_path
                    )

                    with st.spinner(
                        "Analyzing video..."
                    ):

                        analysis = analyze_video(
                            video_path,
                            analysis_prompt
                        )

                    st.subheader(
                        "Analysis"
                    )

                    st.markdown(
                        analysis
                    )

                except Exception as e:

                    st.error(
                        "Video analysis failed."
                    )

                    st.code(
                        str(e)
                    )


    # ========================================================
    # TRIM VIDEO
    # ========================================================

    elif studio_option == "Trim Video":

        st.subheader(
            "✂️ Trim Video"
        )

        uploaded_video = st.file_uploader(
            "Upload video",
            type=[
                "mp4",
                "mov",
                "avi",
                "mkv",
                "webm"
            ],
            key="trim_upload"
        )

        start_time = st.number_input(
            "Start time (seconds)",
            min_value=0.0,
            value=0.0,
            step=1.0
        )

        duration = st.number_input(
            "Duration (seconds)",
            min_value=0.1,
            value=5.0,
            step=1.0
        )

        if st.button(
            "✂️ Trim Video",
            type="primary"
        ):

            if uploaded_video is None:

                st.warning(
                    "Please upload a video."
                )

            else:

                try:

                    input_path = save_uploaded_file(
                        uploaded_video
                    )

                    output_path = trim_video(
                        input_path,
                        start_time,
                        duration
                    )

                    st.success(
                        "Video trimmed successfully!"
                    )

                    st.video(
                        output_path
                    )

                    with open(
                        output_path,
                        "rb"
                    ) as video_file:

                        st.download_button(
                            "⬇️ Download Trimmed Video",
                            video_file.read(),
                            file_name="trimmed_video.mp4",
                            mime="video/mp4"
                        )

                except Exception as e:

                    st.error(
                        "Could not trim the video."
                    )

                    st.code(
                        str(e)
                    )


    # ========================================================
    # MERGE VIDEOS
    # ========================================================

    elif studio_option == "Merge Videos":

        st.subheader(
            "🔗 Merge Videos"
        )

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
            key="merge_upload"
        )

        if st.button(
            "🔗 Merge Videos",
            type="primary"
        ):

            if not uploaded_videos:

                st.warning(
                    "Please upload at least two videos."
                )

            elif len(uploaded_videos) < 2:

                st.warning(
                    "Please upload at least two videos."
                )

            else:

                try:

                    paths = []

                    for uploaded_video in uploaded_videos:

                        path = save_uploaded_file(
                            uploaded_video
                        )

                        paths.append(path)

                    output_path = merge_videos(
                        paths
                    )

                    st.success(
                        "Videos merged successfully!"
                    )

                    st.video(
                        output_path
                    )

                    with open(
                        output_path,
                        "rb"
                    ) as video_file:

                        st.download_button(
                            "⬇️ Download Merged Video",
                            video_file.read(),
                            file_name="merged_video.mp4",
                            mime="video/mp4"
                        )

                except Exception as e:

                    st.error(
                        "Could not merge the videos."
                    )

                    st.code(
                        str(e)
                    )


    # ========================================================
    # RESIZE VIDEO
    # ========================================================

    elif studio_option == "Resize Video":

        st.subheader(
            "📐 Resize Video"
        )

        uploaded_video = st.file_uploader(
            "Upload video",
            type=[
                "mp4",
                "mov",
                "avi",
                "mkv",
                "webm"
            ],
            key="resize_upload"
        )

        resolution = st.selectbox(
            "Choose resolution",
            [
                "1920x1080",
                "1280x720",
                "1080x1920",
                "720x1280",
                "854x480"
            ]
        )

        width, height = map(
            int,
            resolution.split("x")
        )

        if st.button(
            "📐 Resize Video",
            type="primary"
        ):

            if uploaded_video is None:

                st.warning(
                    "Please upload a video."
                )

            else:

                try:

                    input_path = save_uploaded_file(
                        uploaded_video
                    )

                    output_path = resize_video(
                        input_path,
                        width,
                        height
                    )

                    st.success(
                        "Video resized successfully!"
                    )

                    st.video(
                        output_path
                    )

                    with open(
                        output_path,
                        "rb"
                    ) as video_file:

                        st.download_button(
                            "⬇️ Download Resized Video",
                            video_file.read(),
                            file_name="resized_video.mp4",
                            mime="video/mp4"
                        )

                except Exception as e:

                    st.error(
                        "Could not resize the video."
                    )

                    st.code(
                        str(e)
                    )


    # ========================================================
    # EXTRACT AUDIO
    # ========================================================

    elif studio_option == "Extract Audio":

        st.subheader(
            "🎵 Extract Audio"
        )

        uploaded_video = st.file_uploader(
            "Upload video",
            type=[
                "mp4",
                "mov",
                "avi",
                "mkv",
                "webm"
            ],
            key="audio_upload"
        )

        if st.button(
            "🎵 Extract Audio",
            type="primary"
        ):

            if uploaded_video is None:

                st.warning(
                    "Please upload a video."
                )

            else:

                try:

                    input_path = save_uploaded_file(
                        uploaded_video
                    )

                    output_path = extract_audio(
                        input_path
                    )

                    st.success(
                        "Audio extracted successfully!"
                    )

                    with open(
                        output_path,
                        "rb"
                    ) as audio_file:

                        st.download_button(
                            "⬇️ Download MP3",
                            audio_file.read(),
                            file_name="extracted_audio.mp3",
                            mime="audio/mpeg"
                        )

                except Exception as e:

                    st.error(
                        "Could not extract audio."
                    )

                    st.code(
                        str(e)
                    )


# ============================================================
# LEARNING DASHBOARD
# ============================================================

with tab_study:

    st.header(
        "📚 Learning Dashboard"
    )

    st.metric(
        "Study Points",
        st.session_state.study_points
    )

    st.divider()

    st.subheader(
        "🎯 Suggested Study Activities"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.info(
            "📖 Learn\n\n"
            "Ask SUP to explain a difficult topic "
            "from the basics."
        )

    with col2:

        st.info(
            "📝 Exam\n\n"
            "Ask for exam-oriented answers "
            "and important questions."
        )

    with col3:

        st.info(
            "🎤 Viva\n\n"
            "Practice viva questions "
            "before your exam."
        )

    st.divider()

    st.subheader(
        "💡 Example Prompts"
    )

    st.markdown(
        """
        - Explain linked lists from the beginning.
        - Give me an exam answer for insertion sort.
        - Ask me 10 viva questions about Java.
        - Explain binary search with a simple example.
        - Debug this C program.
        - Make revision notes for discrete mathematics.
        """
    )
```
