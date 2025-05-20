from flask import Flask, request, jsonify
import os
import asyncio
import base64
import io
import traceback
import cv2
import pyaudio
import PIL.Image
import mss
import threading
import queue
import time
from google import genai
from google.genai import types
from flask_cors import CORS
from dotenv import load_dotenv

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Audio settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

MODEL = "models/gemini-2.0-flash-live-001"

# Initialize the Gemini client
load_dotenv()

client = genai.Client(
    http_options={"api_version": "v1beta"},
    api_key=os.environ.get("GEMINI_API_KEY"),
)

# Configure the response modalities
CONFIG = types.LiveConnectConfig(
    response_modalities=[
        "audio",
    ],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
        )
    ),
)

# Initialize PyAudio
pya = pyaudio.PyAudio()

# Global variables
session = None
session_ctx = None  # Store context manager for proper cleanup
main_loop = None  # Store the main event loop
audio_in_queue = queue.Queue()
image_queue = queue.Queue(maxsize=5)
audio_out_queue = queue.Queue()
active_tasks = []
session_active = False
video_mode = "none"

# Function to get a frame from the camera
def get_camera_frame():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return None
    
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        return None
    
    # Convert BGR to RGB
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = PIL.Image.fromarray(frame_rgb)
    img.thumbnail([1024, 1024])
    
    image_io = io.BytesIO()
    img.save(image_io, format="jpeg")
    image_io.seek(0)
    
    mime_type = "image/jpeg"
    image_bytes = image_io.read()
    return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

# Function to get a screenshot
def get_screen_capture():
    sct = mss.mss()
    monitor = sct.monitors[0]
    
    i = sct.grab(monitor)
    
    mime_type = "image/jpeg"
    image_bytes = mss.tools.to_png(i.rgb, i.size)
    img = PIL.Image.open(io.BytesIO(image_bytes))
    
    image_io = io.BytesIO()
    img.save(image_io, format="jpeg")
    image_io.seek(0)
    
    image_bytes = image_io.read()
    return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

# Thread function to handle all async operations
def async_handler():
    global session, session_ctx, main_loop, session_active

    # Create a new event loop for this thread
    main_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(main_loop)
    
    try:
        # Run the event loop
        main_loop.run_forever()
    except Exception as e:
        print(f"Event loop error: {e}")
    finally:
        main_loop.close()
        main_loop = None

# Function to run a coroutine in the main event loop
def run_coroutine(coro):
    global main_loop
    if main_loop and main_loop.is_running():
        future = asyncio.run_coroutine_threadsafe(coro, main_loop)
        try:
            return future.result(timeout=10)  # 10 seconds timeout
        except Exception as e:
            print(f"Error running coroutine: {e}")
            return None
    return None

# Thread function to capture images
def capture_images():
    global video_mode, image_queue, session_active
    while session_active:
        try:
            if video_mode == "camera":
                frame = get_camera_frame()
            elif video_mode == "screen":
                frame = get_screen_capture()
            else:
                time.sleep(1)
                continue
            
            if frame:
                if image_queue.full():
                    image_queue.get()  # Remove oldest item if queue is full
                image_queue.put(frame)
            
            time.sleep(1)  # Capture every second
        except Exception as e:
            print(f"Error capturing images: {e}")
            time.sleep(1)

# Thread function to send images to Gemini
def send_images():
    global session, image_queue, session_active
    
    async def send_image(frame):
        if session:
            await session.send(input=frame)
    
    while session_active:
        try:
            if not image_queue.empty() and session:
                frame = image_queue.get()
                run_coroutine(send_image(frame))
            time.sleep(0.1)
        except Exception as e:
            print(f"Error sending images: {e}")
            time.sleep(1)

# Thread function to record audio
def record_audio():
    global audio_out_queue, session_active
    try:
        mic_info = pya.get_default_input_device_info()
        audio_stream = pya.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        
        while session_active:
            data = audio_stream.read(CHUNK_SIZE, exception_on_overflow=False)
            audio_packet = {"data": data, "mime_type": "audio/pcm"}
            if audio_out_queue.qsize() > 10:  # Limit queue size
                audio_out_queue.get()  # Remove oldest item if queue is too large
            audio_out_queue.put(audio_packet)
            
        audio_stream.close()
    except Exception as e:
        print(f"Error recording audio: {e}")

# Thread function to send audio to Gemini
def send_audio():
    global session, audio_out_queue, session_active
    
    async def send_audio_data(audio_data):
        if session:
            await session.send(input=audio_data)
    
    while session_active:
        try:
            if not audio_out_queue.empty() and session:
                audio_data = audio_out_queue.get()
                run_coroutine(send_audio_data(audio_data))
            time.sleep(0.01)  # Small sleep to prevent CPU overload
        except Exception as e:
            print(f"Error sending audio: {e}")
            time.sleep(0.1)

# Thread function to receive responses from Gemini
def receive_responses():
    global session, audio_in_queue, session_active
    
    async def process_responses():
        if not session:
            return
            
        try:
            response_gen = session.receive()
            async for response in response_gen:
                if hasattr(response, 'data') and response.data:
                    audio_in_queue.put(response.data)
                if hasattr(response, 'text') and response.text:
                    print(f"Received text: {response.text}")
        except Exception as e:
            print(f"Error in receive operation: {e}")
    
    while session_active:
        try:
            run_coroutine(process_responses())
            time.sleep(0.1)  # Small sleep between receive operations
        except Exception as e:
            print(f"Error in receive responses thread: {e}")
            time.sleep(0.1)

# Thread function to play audio responses
def play_audio():
    global audio_in_queue, session_active
    try:
        output_stream = pya.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        
        while session_active:
            try:
                if not audio_in_queue.empty():
                    bytestream = audio_in_queue.get()
                    output_stream.write(bytestream)
                else:
                    time.sleep(0.01)  # Small sleep to prevent CPU overload
            except Exception as e:
                print(f"Error playing audio: {e}")
                time.sleep(0.1)
                
        output_stream.close()
    except Exception as e:
        print(f"Error setting up audio playback: {e}")

# Start the session and all threads
def start_session_threads(session_mode):
    global session, session_ctx, active_tasks, session_active, video_mode, main_loop
    
    # Start Gemini session
    session_active = True
    video_mode = session_mode
    
    # Start the async handler thread if not running
    if main_loop is None:
        async_thread = threading.Thread(target=async_handler)
        async_thread.daemon = True
        async_thread.start()
        time.sleep(0.5)  # Give time for the event loop to start
    
    # Connect to Gemini
    async def connect_async():
        global session, session_ctx
        try:
            session_ctx = client.aio.live.connect(model=MODEL, config=CONFIG)
            session = await session_ctx.__aenter__()
            print("Connected to Gemini session successfully!")
            return True
        except Exception as e:
            print(f"Error in async connection: {e}")
            traceback.print_exc()
            return False
    
    connection_success = run_coroutine(connect_async())
    
    if not connection_success:
        session_active = False
        return False
    
    # Start all threads
    threads = [
        threading.Thread(target=capture_images),
        threading.Thread(target=send_images),
        threading.Thread(target=record_audio),
        threading.Thread(target=send_audio),
        threading.Thread(target=receive_responses),
        threading.Thread(target=play_audio),
    ]
    
    for thread in threads:
        thread.daemon = True
        thread.start()
        active_tasks.append(thread)
        
    return True

# Stop all threads and close the session
def stop_session_threads():
    global session, session_ctx, active_tasks, session_active, main_loop
    
    if not session_active:
        return True
    
    # Signal threads to stop
    session_active = False
    
    # Wait for threads to finish
    for thread in active_tasks:
        if thread.is_alive():
            thread.join(timeout=1)
    
    # Clear active tasks
    active_tasks = []
    
    # Close session
    if session and session_ctx:
        async def close_session_async():
            global session, session_ctx
            try:
                await session_ctx.__aexit__(None, None, None)
                session = None
                session_ctx = None
                print("Session closed successfully")
            except Exception as e:
                print(f"Error closing session: {e}")
        
        run_coroutine(close_session_async())
    
    return True

# API endpoints
@app.route('/api/start', methods=['POST'])
def start_session():
    global video_mode, session_active
    
    if session_active:
        return jsonify({"status": "error", "message": "Session already active"}), 400
    
    data = request.json
    video_mode = data.get('mode', 'none')
    
    if video_mode not in ['camera', 'screen', 'none']:
        return jsonify({"status": "error", "message": "Invalid mode"}), 400
    
    # Start the session and threads
    try:
        success = start_session_threads(video_mode)
        if success:
            return jsonify({"status": "success", "message": "Session started", "mode": video_mode})
        else:
            return jsonify({"status": "error", "message": "Failed to start session"}), 500
    except Exception as e:
        print(f"Exception when starting session: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/stop', methods=['POST'])
def stop_session():
    global session_active
    
    if not session_active:
        return jsonify({"status": "error", "message": "No active session"}), 400
    
    # Stop the session and threads
    try:
        success = stop_session_threads()
        if success:
            return jsonify({"status": "success", "message": "Session stopped"})
        else:
            return jsonify({"status": "error", "message": "Failed to stop session"}), 500
    except Exception as e:
        print(f"Exception when stopping session: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/send_text', methods=['POST'])
def send_text():
    global session, session_active
    
    if not session_active or not session:
        return jsonify({"status": "error", "message": "No active session"}), 400
    
    data = request.json
    text = data.get('text', '')
    
    if not text:
        return jsonify({"status": "error", "message": "No text provided"}), 400
    
    try:
        async def send_text_async():
            nonlocal text
            print(f"Sending text: {text}")
            await session.send(input=text, end_of_turn=True)
        
        run_coroutine(send_text_async())
        return jsonify({"status": "success", "message": "Text sent"})
    except Exception as e:
        print(f"Error sending text: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    global session_active, video_mode
    
    return jsonify({
        "status": "active" if session_active else "inactive",
        "mode": video_mode
    })

@app.route('/api/change_mode', methods=['POST'])
def change_mode():
    global video_mode, session_active
    
    if not session_active:
        return jsonify({"status": "error", "message": "No active session"}), 400
    
    data = request.json
    new_mode = data.get('mode', 'none')
    
    if new_mode not in ['camera', 'screen', 'none']:
        return jsonify({"status": "error", "message": "Invalid mode"}), 400
    
    video_mode = new_mode
    return jsonify({"status": "success", "message": f"Mode changed to {video_mode}"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)