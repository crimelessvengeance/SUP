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
# GEMINI TEXT GENERATION
# ============================================================

def generate_text(
    contents,
    system_instruction=SYSTEM_INSTRUCTION
):

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
# FFmpeg CHECK
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

def save_uploaded_file(
    uploaded_file,
    suffix=None
):

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
# MERGE VIDEOS
# ============================================================

def merge_videos(video_paths):

    list_file = tempfile.NamedTemporaryFile(
        delete=False,
        mode="w",
        suffix=".txt"
    )

    for path in video_paths:

        # Convert path to Linux-style path
        # for Streamlit Cloud.

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

    # First try stream copying.

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

        # If videos have different codecs/settings,
        # re-encode them.

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
# GENERATE VIDEO FROM TEXT
# ============================================================

def generate_video(
    prompt,
    aspect_ratio
):

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

    generated_video = (
        operation.response.generated_videos[0]
    )

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
# GENERATE VIDEO FROM IMAGE
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

    generated_video = (
        operation.response.generated_videos[0]
    )

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
# ANALYZE VIDEO
# ============================================================

def analyze_video(
    video_path,
    prompt
):

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
# SESSION STATE
# ============================================================

if "messages" not in st.session_state:

    st.session_state.messages = []


if "study_points" not in st.session_state:

    st.session_state.study_points = 0


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("🤖 SUP")

    st.caption(
        "Your smart AI assistant"
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

    st.subheader("📚 Learning Dashboard")

    st.metric(
        "Study Points",
        st.session_state.study_points
    )

    if st.button("Reset Study Points"):

        st.session_state.study_points = 0

        st.rerun()

    st.divider()

    if st.button("🗑️ Clear Chat"):

        st.session_state.messages = []

        st.rerun()


# ============================================================
# MAIN HEADER
# ============================================================

st.title("🤖 SUP")

st.write(
    "Your smart, friendly and slightly witty AI assistant."
)


# ============================================================
# TABS
# ============================================================

chat_tab, studio_tab = st.tabs(
    [
        "💬 AI Assistant",
        "🎬 SUP Studio"
    ]
)


# ============================================================
# AI CHAT TAB
# ============================================================

with chat_tab:

    st.subheader(
        f"Mode: {mode}"
    )

    # Display previous messages

    for message in st.session_state.messages:

        with st.chat_message(
            message["role"]
        ):

            st.markdown(
                message["content"]
            )


    # --------------------------------------------------------
    # FILE UPLOAD
    # --------------------------------------------------------

    uploaded_study_file = st.file_uploader(
        "📎 Upload a study file",
        type=[
            "pdf",
            "txt",
            "docx",
            "pptx",
            "csv",
            "py",
            "c",
            "cpp",
            "java",
            "html",
            "css",
            "js",
            "json"
        ],
        help="Upload a file and ask questions about it."
    )


    # --------------------------------------------------------
    # CHAT INPUT
    # --------------------------------------------------------

    user_prompt = st.chat_input(
        "Ask me anything..."
    )


    if user_prompt:

        # Add user message

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
        # MODE INSTRUCTIONS
        # ----------------------------------------------------

        mode_instructions = {

            "Normal":
                "Answer normally and naturally.",

            "Learn":
                "Teach the topic step by step in simple language. Assume the student may be a beginner.",

            "Exam":
                "Answer from an exam point of view. Give accurate, concise, easy-to-write answers.",

            "Challenge":
                "Challenge the student with questions and small problems. Do not reveal the answer immediately.",

            "Debug":
                "Focus on finding programming errors and explaining exactly how to fix them.",

            "Viva":
                "Act like a teacher conducting a viva. Ask one question at a time and evaluate answers.",

            "Revision":
                "Give quick revision notes, key points, formulas and important concepts.",

            "Teacher":
                "Explain like a helpful teacher. Use examples and simple explanations.",

            "Explain 3 Ways":
                "Explain the concept in three ways: simple explanation, example, and technical explanation."
        }


        current_instruction = mode_instructions[
            mode
        ]


        # ----------------------------------------------------
        # BUILD PROMPT
        # ----------------------------------------------------

        final_prompt = f"""
Current mode:
{mode}

Mode instructions:
{current_instruction}

User question:
{user_prompt}
"""


        # ----------------------------------------------------
        # HANDLE UPLOADED FILE
        # ----------------------------------------------------

        if uploaded_study_file:

            try:

                file_path = save_uploaded_file(
                    uploaded_study_file
                )

                uploaded_gemini_file = client.files.upload(
                    file=file_path
                )

                while (
                    uploaded_gemini_file.state.name
                    == "PROCESSING"
                ):

                    time.sleep(2)

                    uploaded_gemini_file = client.files.get(
                        name=uploaded_gemini_file.name
                    )


                final_prompt = f"""
The user uploaded this file:

{uploaded_study_file.name}

Use the uploaded file as the main source when answering.

Current mode:
{mode}

Mode instructions:
{current_instruction}

User question:
{user_prompt}

If the answer is not present in the file, clearly say so
and then provide useful general knowledge if appropriate.
"""


                contents = [
                    uploaded_gemini_file,
                    final_prompt
                ]


            except Exception as e:

                st.error(
                    f"Could not process the file: {e}"
                )

                contents = final_prompt

        else:

            contents = final_prompt


        # ----------------------------------------------------
        # GENERATE RESPONSE
        # ----------------------------------------------------

        with st.chat_message("assistant"):

            try:

                answer = generate_text(
                    contents
                )

                st.markdown(
                    answer
                )

                # Increase study points for learning modes

                if mode in [
                    "Learn",
                    "Exam",
                    "Revision",
                    "Teacher",
                    "Viva"
                ]:

                    st.session_state.study_points += 10


            except Exception as e:

                answer = (
                    "Sorry, I ran into an error.\n\n"
                    f"`{e}`"
                )

                st.error(
                    answer
                )


        # Save assistant response

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer
            }
        )


# ============================================================
# SUP STUDIO
# ============================================================

with studio_tab:

    st.header("🎬 SUP Studio")

    st.write(
        "Generate, analyze and edit videos using online AI and FFmpeg."
    )

    if not check_ffmpeg():

        st.warning(
            "FFmpeg is not currently available. "
            "Make sure `packages.txt` contains `ffmpeg`."
        )


    studio_option = st.selectbox(
        "Choose a Studio Tool",
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
            "Describe the video you want",
            placeholder=(
                "Example: A cinematic drone shot flying "
                "over a futuristic city at sunset."
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
            "Generate Video",
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

                    st.video(
                        video_path
                    )

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
                        f"Video generation failed:\n\n{e}"
                    )


    # ========================================================
    # IMAGE TO VIDEO
    # ========================================================

    elif studio_option == "Image → Video":

        st.subheader(
            "🖼️ Image → Video"
        )

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
                "Example: Slowly zoom toward the subject "
                "while the background moves naturally."
            ),
            height=120
        )

        aspect_ratio = st.selectbox(
            "Aspect Ratio",
            [
                "16:9",
                "9:16"
            ],
            key="image_video_ratio"
        )


        if st.button(
            "Generate From Image",
            type="primary"
        ):

            if image_file is None:

                st.warning(
                    "Please upload an image first."
                )

            elif not prompt.strip():

                st.warning(
                    "Please describe the desired motion."
                )

            else:

                try:

                    image_bytes = image_file.getvalue()

                    mime_type = (
                        image_file.type
                        or "image/png"
                    )

                    with st.spinner(
                        "Creating video from image..."
                    ):

                        video_path = generate_video_from_image(
                            image_bytes,
                            mime_type,
                            prompt,
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
                            video_file,
                            file_name="image_to_video.mp4",
                            mime="video/mp4"
                        )

                except Exception as e:

                    st.error(
                        f"Image-to-video failed:\n\n{e}"
                    )


    # ========================================================
    # ANALYZE VIDEO
    # ========================================================

    elif studio_option == "Analyze Video":

        st.subheader(
            "🔍 Analyze Video"
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
            key="analysis_video"
        )

        analysis_prompt = st.text_area(
            "What should I analyze?",
            value=(
                "Describe what happens in this video "
                "and identify the important events."
            ),
            height=120
        )


        if st.button(
            "Analyze Video",
            type="primary"
        ):

            if video_file is None:

                st.warning(
                    "Please upload a video."
                )

            else:

                try:

                    video_path = save_uploaded_file(
                        video_file
                    )

                    with st.spinner(
                        "Analyzing video..."
                    ):

                        result = analyze_video(
                            video_path,
                            analysis_prompt
                        )

                    st.success(
                        "Analysis complete!"
                    )

                    st.markdown(
                        result
                    )

                except Exception as e:

                    st.error(
                        f"Video analysis failed:\n\n{e}"
                    )


    # ========================================================
    # TRIM VIDEO
    # ========================================================

    elif studio_option == "Trim Video":

        st.subheader(
            "✂️ Trim Video"
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
            key="trim_video"
        )

        start_time = st.number_input(
            "Start time (seconds)",
            min_value=0.0,
            value=0.0,
            step=0.5
        )

        duration = st.number_input(
            "Duration (seconds)",
            min_value=0.1,
            value=5.0,
            step=0.5
        )


        if st.button(
            "Trim Video",
            type="primary"
        ):

            if video_file is None:

                st.warning(
                    "Please upload a video."
                )

            else:

                try:

                    input_path = save_uploaded_file(
                        video_file
                    )

                    with st.spinner(
                        "Trimming video..."
                    ):

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
                    ) as output_file:

                        st.download_button(
                            "⬇️ Download Trimmed Video",
                            output_file,
                            file_name="trimmed_video.mp4",
                            mime="video/mp4"
                        )

                except Exception as e:

                    st.error(
                        f"Video trimming failed:\n\n{e}"
                    )


    # ========================================================
    # MERGE VIDEOS
    # ========================================================

    elif studio_option == "Merge Videos":

        st.subheader(
            "🔗 Merge Videos"
        )

        video_files = st.file_uploader(
            "Upload multiple videos",
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

        if video_files:

            st.write(
                f"{len(video_files)} video(s) selected."
            )

            for file in video_files:

                st.write(
                    f"• {file.name}"
                )


        if st.button(
            "Merge Videos",
            type="primary"
        ):

            if not video_files:

                st.warning(
                    "Please upload at least two videos."
                )

            elif len(video_files) < 2:

                st.warning(
                    "Please upload at least two videos to merge."
                )

            else:

                try:

                    video_paths = []

                    for file in video_files:

                        path = save_uploaded_file(
                            file
                        )

                        video_paths.append(
                            path
                        )


                    with st.spinner(
                        "Merging videos..."
                    ):

                        output_path = merge_videos(
                            video_paths
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
                    ) as output_file:

                        st.download_button(
                            "⬇️ Download Merged Video",
                            output_file,
                            file_name="merged_video.mp4",
                            mime="video/mp4"
                        )


                except Exception as e:

                    st.error(
                        f"Video merging failed:\n\n{e}"
                    )


    # ========================================================
    # RESIZE VIDEO
    # ========================================================

    elif studio_option == "Resize Video":

        st.subheader(
            "📐 Resize Video"
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
            key="resize_video"
        )


        preset = st.selectbox(
            "Choose Resolution",
            [
                "1920x1080",
                "1280x720",
                "1080x1920",
                "720x1280",
                "854x480",
                "640x360"
            ]
        )


        width, height = map(
            int,
            preset.split("x")
        )


        if st.button(
            "Resize Video",
            type="primary"
        ):

            if video_file is None:

                st.warning(
                    "Please upload a video."
                )

            else:

                try:

                    input_path = save_uploaded_file(
                        video_file
                    )

                    with st.spinner(
                        "Resizing video..."
                    ):

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
                    ) as output_file:

                        st.download_button(
                            "⬇️ Download Resized Video",
                            output_file,
                            file_name="resized_video.mp4",
                            mime="video/mp4"
                        )

                except Exception as e:

                    st.error(
                        f"Video resizing failed:\n\n{e}"
                    )


    # ========================================================
    # EXTRACT AUDIO
    # ========================================================

    elif studio_option == "Extract Audio":

        st.subheader(
            "🎵 Extract Audio"
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
            key="audio_video"
        )


        if st.button(
            "Extract Audio",
            type="primary"
        ):

            if video_file is None:

                st.warning(
                    "Please upload a video."
                )

            else:

                try:

                    input_path = save_uploaded_file(
                        video_file
                    )

                    with st.spinner(
                        "Extracting audio..."
                    ):

                        audio_path = extract_audio(
                            input_path
                        )

                    st.success(
                        "Audio extracted successfully!"
                    )


                    with open(
                        audio_path,
                        "rb"
                    ) as audio_file:

                        st.download_button(
                            "⬇️ Download Audio",
                            audio_file,
                            file_name="extracted_audio.mp3",
                            mime="audio/mpeg"
                        )

                except Exception as e:

                    st.error(
                        f"Audio extraction failed:\n\n{e}"
                    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "AI assistant • Study tools • AI video generation • Video tools"
)
