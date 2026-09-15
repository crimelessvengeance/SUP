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
# API KEY
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
# GEMINI CLIENT
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
    """
    Generate text using Gemini.

    Includes automatic retries for temporary 503/high-demand
    errors.
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
# FFMPEG
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
# SAVE STREAMLIT UPLOAD TO CLOUD TEMPORARY STORAGE
# ============================================================

def save_uploaded_file(uploaded_file, suffix=None):

    if suffix is None:
        suffix = Path(uploaded_file.name).suffix

    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix
    )

    temp_file.write(uploaded_file.getbuffer())
    temp_file.close()

    return temp_file.name


# ============================================================
# VIDEO EDITING FUNCTIONS
# ============================================================

def trim_video(input_path, start_time, duration):

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

        # Fallback if stream-copy doesn't work
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


def resize_video(input_path, width, height):

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


def merge_videos(video_paths):

    list_file = tempfile.NamedTemporaryFile(
        delete=False,
        mode="w",
        suffix=".txt"
    )

    for path in video_paths:
        list_file.write(
            f"file '{path.replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39)}'\n"
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

        # Fallback re-encoding
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
# GEMINI VIDEO ANALYSIS
# ============================================================

def analyze_video(video_path, prompt):

    uploaded_file = client.files.upload(
        file=video_path
    )

    # Wait until Gemini finishes processing the video.
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
# AI VIDEO GENERATION
# ============================================================

def generate_video(prompt, aspect_ratio):

    operation = client.models.generate_videos(
        model=VIDEO_MODEL,
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio
        )
    )

    progress_placeholder = st.empty()

    while not operation.done:

        progress_placeholder.info(
            "🎬 Generating your video... Please wait."
        )

        time.sleep(10)

        operation = client.operations.get(
            operation
        )

    progress_placeholder.empty()

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
# IMAGE → VIDEO
# ============================================================

def generate_video_from_image(
    image_bytes,
    mime_type,
    prompt,
    aspect_ratio
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

st.sidebar.title("🤖 SUP")

st.sidebar.markdown(
    """
### AI Assistant

Choose what you want to do.
"""
)

mode = st.sidebar.selectbox(
    "Mode",
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

st.sidebar.divider()

st.sidebar.metric(
    "Study Points",
    st.session_state.study_points
)


# ============================================================
# MAIN HEADER
# ============================================================

st.title("🤖 SUP")
st.caption(
    "Your smart AI assistant"
)


# ============================================================
# SUP STUDIO
# ============================================================

with st.expander("🎬 SUP Studio — Video Tools"):

    studio_tab1, studio_tab2, studio_tab3 = st.tabs(
        [
            "✨ Generate",
            "🎞️ Edit",
            "🔍 Analyze"
        ]
    )

    # --------------------------------------------------------
    # GENERATE TAB
    # --------------------------------------------------------

    with studio_tab1:

        st.subheader("✨ AI Video Generation")

        generation_type = st.radio(
            "Generation type",
            [
                "Text → Video",
                "Image → Video"
            ],
            horizontal=True
        )

        aspect_ratio = st.selectbox(
            "Aspect ratio",
            [
                "16:9",
                "9:16"
            ]
        )

        if generation_type == "Text → Video":

            prompt = st.text_area(
                "Describe the video you want",
                placeholder=(
                    "Example: A cinematic drone shot flying "
                    "over a futuristic city at sunset, "
                    "realistic lighting, smooth camera movement."
                ),
                height=150
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

                        with st.spinner(
                            "Generating video..."
                        ):

                            video_path = generate_video(
                                prompt,
                                aspect_ratio
                            )

                        st.success(
                            "Video generated successfully!"
                        )

                        st.video(video_path)

                        with open(
                            video_path,
                            "rb"
                        ) as video_file:

                            st.download_button(
                                "⬇️ Download Video",
                                video_file,
                                file_name="generated_video.mp4",
                                mime="video/mp4"
                            )

                    except Exception as e:

                        st.error(
                            f"Video generation failed:\n{e}"
                        )

        else:

            image_file = st.file_uploader(
                "Upload an image",
                type=[
                    "png",
                    "jpg",
                    "jpeg",
                    "webp"
                ]
            )

            prompt = st.text_area(
                "Describe how the image should move",
                placeholder=(
                    "Example: Slowly zoom into the scene "
                    "while the trees move naturally in the wind."
                ),
                height=150
            )

            if image_file:

                st.image(
                    image_file,
                    caption="Input image",
                    use_container_width=True
                )

            if st.button(
                "🎬 Generate From Image",
                type="primary"
            ):

                if image_file is None:

                    st.warning(
                        "Please upload an image."
                    )

                elif not prompt.strip():

                    st.warning(
                        "Please describe the motion."
                    )

                else:

                    try:

                        with st.spinner(
                            "Creating video..."
                        ):

                            video_path = generate_video_from_image(
                                image_file.getvalue(),
                                image_file.type,
                                prompt,
                                aspect_ratio
                            )

                        st.success(
                            "Video generated successfully!"
                        )

                        st.video(video_path)

                        with open(
                            video_path,
                            "rb"
                        ) as video_file:

                            st.download_button(
                                "⬇️ Download Video",
                                video_file,
                                file_name="image_to_video.mp4",
                                mime="video/mp4"
                            )

                    except Exception as e:

                        st.error(
                            f"Image-to-video failed:\n{e}"
                        )


    # --------------------------------------------------------
    # EDIT TAB
    # --------------------------------------------------------

    with studio_tab2:

        st.subheader("🎞️ Online Video Editor")

        if not check_ffmpeg():

            st.error(
                "FFmpeg is not available on the Streamlit Cloud server."
            )

            st.info(
                "Make sure packages.txt contains: ffmpeg"
            )

        video_file = st.file_uploader(
            "Upload a video",
            type=[
                "mp4",
                "mov",
                "avi",
                "mkv",
                "webm"
            ],
            key="editor_video"
        )

        if video_file:

            st.video(video_file)

            editing_operation = st.selectbox(
                "Choose editing operation",
                [
                    "Trim Video",
                    "Resize Video",
                    "Extract Audio",
                    "Merge Videos"
                ]
            )

            # ------------------------------------------------
            # TRIM
            # ------------------------------------------------

            if editing_operation == "Trim Video":

                col1, col2 = st.columns(2)

                with col1:

                    start_time = st.number_input(
                        "Start time (seconds)",
                        min_value=0.0,
                        value=0.0,
                        step=1.0
                    )

                with col2:

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

                    try:

                        input_path = save_uploaded_file(
                            video_file
                        )

                        with st.spinner(
                            "Trimming video on the cloud..."
                        ):

                            output_path = trim_video(
                                input_path,
                                start_time,
                                duration
                            )

                        st.success(
                            "Video trimmed successfully!"
                        )

                        st.video(output_path)

                        with open(
                            output_path,
                            "rb"
                        ) as output_file:

                            st.download_button(
                                "⬇️ Download Trimmed Video",
                                output_file,
                                file_name="trimmed_video.mp4",
                                mime="video/mp4"
                            )

                    except Exception as e:

                        st.error(
                            f"Trimming failed:\n{e}"
                        )


            # ------------------------------------------------
            # RESIZE
            # ------------------------------------------------

            elif editing_operation == "Resize Video":

                resolution = st.selectbox(
                    "Resolution",
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

                    try:

                        input_path = save_uploaded_file(
                            video_file
                        )

                        with st.spinner(
                            "Resizing video on the cloud..."
                        ):

                            output_path = resize_video(
                                input_path,
                                width,
                                height
                            )

                        st.success(
                            "Video resized successfully!"
                        )

                        st.video(output_path)

                        with open(
                            output_path,
                            "rb"
                        ) as output_file:

                            st.download_button(
                                "⬇️ Download Resized Video",
                                output_file,
                                file_name="resized_video.mp4",
                                mime="video/mp4"
                            )

                    except Exception as e:

                        st.error(
                            f"Resize failed:\n{e}"
                        )


            # ------------------------------------------------
            # EXTRACT AUDIO
            # ------------------------------------------------

            elif editing_operation == "Extract Audio":

                if st.button(
                    "🎵 Extract Audio",
                    type="primary"
                ):

                    try:

                        input_path = save_uploaded_file(
                            video_file
                        )

                        with st.spinner(
                            "Extracting audio on the cloud..."
                        ):

                            output_path = extract_audio(
                                input_path
                            )

                        st.success(
                            "Audio extracted successfully!"
                        )

                        st.audio(output_path)

                        with open(
                            output_path,
                            "rb"
                        ) as output_file:

                            st.download_button(
                                "⬇️ Download Audio",
                                output_file,
                                file_name="extracted_audio.mp3",
                                mime="audio/mpeg"
                            )

                    except Exception as e:

                        st.error(
                            f"Audio extraction failed:\n{e}"
                        )


            # ------------------------------------------------
            # MERGE
            # ------------------------------------------------

            elif editing_operation == "Merge Videos":

                second_video = st.file_uploader(
                    "Upload the second video",
                    type=[
                        "mp4",
                        "mov",
                        "avi",
                        "mkv",
                        "webm"
                    ],
                    key="second_video"
                )

                if second_video:

                    if st.button(
                        "🔗 Merge Videos",
                        type="primary"
                    ):

                        try:

                            first_path = save_uploaded_file(
                                video_file
                            )

                            second_path = save_uploaded_file(
                                second_video
                            )

                            with st.spinner(
                                "Merging videos on the cloud..."
                            ):

                                output_path = merge_videos(
                                    [
                                        first_path,
                                        second_path
                                    ]
                                )

                            st.success(
                                "Videos merged successfully!"
                            )

                            st.video(output_path)

                            with open(
                                output_path,
                                "rb"
                            ) as output_file:

                                st.download_button(
                                    "⬇️ Download Merged Video",
                                    output_file,
                                    file_name="merged_video.mp4",
                                    mime="video/mp4"
                                )

                        except Exception as e:

                            st.error(
                                f"Merge failed:\n{e}"
                            )


    # --------------------------------------------------------
    # ANALYZE TAB
    # --------------------------------------------------------

    with studio_tab3:

        st.subheader("🔍 AI Video Analysis")

        analysis_video = st.file_uploader(
            "Upload a video to analyze",
            type=[
                "mp4",
                "mov",
                "avi",
                "mkv",
                "webm"
            ],
            key="analysis_video"
        )

        analysis_prompt = st.text_area(
            "What should I analyze?",
            value=(
                "Describe what happens in this video. "
                "Identify important events, objects, "
                "actions and notable details."
            ),
            height=120
        )

        if analysis_video:

            st.video(analysis_video)

        if st.button(
            "🔎 Analyze Video",
            type="primary"
        ):

            if analysis_video is None:

                st.warning(
                    "Please upload a video first."
                )

            else:

                try:

                    input_path = save_uploaded_file(
                        analysis_video
                    )

                    with st.spinner(
                        "Analyzing video with Gemini..."
                    ):

                        result = analyze_video(
                            input_path,
                            analysis_prompt
                        )

                    st.success(
                        "Analysis complete!"
                    )

                    st.markdown(result)

                except Exception as e:

                    st.error(
                        f"Video analysis failed:\n{e}"
                    )


# ============================================================
# LEARNING MODES
# ============================================================

mode_instructions = {

    "Normal": """
Answer the user's question naturally and directly.
""",

    "Learn": """
Teach the topic step by step.
Assume the user may be a beginner.
Use simple explanations and examples.
""",

    "Exam": """
Give an exam-oriented answer.
Focus on definitions, important points,
steps, examples and likely marks.
""",

    "Challenge": """
Turn the topic into a short challenge or quiz.
Ask questions one at a time.
""",

    "Debug": """
Help debug programming code.
Identify the error, explain why it happens,
then provide the corrected code.
""",

    "Viva": """
Act like a teacher conducting a viva.
Ask one question at a time and evaluate the answer.
""",

    "Revision": """
Create concise revision notes.
Focus on the most important concepts.
""",

    "Teacher": """
Explain the topic like a good teacher.
Use examples and check understanding.
""",

    "Explain 3 Ways": """
Explain the answer in three ways:
1. Very simple
2. Normal
3. Technical
"""
}


# ============================================================
# CHAT DISPLAY
# ============================================================

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])


# ============================================================
# CHAT INPUT
# ============================================================

user_prompt = st.chat_input(
    "Ask me anything..."
)


if user_prompt:

    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_prompt
        }
    )

    with st.chat_message("user"):

        st.markdown(user_prompt)

    mode_instruction = mode_instructions.get(
        mode,
        mode_instructions["Normal"]
    )

    conversation = []

    for message in st.session_state.messages:

        conversation.append(
            f'{message["role"].upper()}: {message["content"]}'
        )

    full_prompt = f"""
Current mode: {mode}

Mode instructions:
{mode_instruction}

Conversation:
{chr(10).join(conversation)}

Respond to the latest user message.
"""

    with st.chat_message("assistant"):

        try:

            response = generate_text(
                full_prompt
            )

            st.markdown(response)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": response
                }
            )

            st.session_state.study_points += 1

        except Exception as e:

            error_message = (
                "I couldn't generate a response right now.\n\n"
                f"Error: {e}"
            )

            st.error(error_message)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": error_message
                }
            )
