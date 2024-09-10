import asyncio
import websockets
import speech_recognition as sr
import io
from pydub import AudioSegment  # You'll need to install pydub

# Install pydub if not already installed
# pip install pydub

# Initialize recognizer
r = sr.Recognizer()

async def handle_audio(websocket, path):
    try:
        while True:
            audio_data = await websocket.recv()
            # Convert audio to WAV format
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))
            # Export to WAV
            with io.BytesIO() as wav_io:
                audio_segment.export(wav_io, format="wav")
                wav_io.seek(0)  # Reset stream position to the beginning
                print("got audio") 
                with sr.AudioFile(wav_io) as source:
                    audio = r.record(source)
                    try:
                        text = r.recognize_google(audio)
                        print(text)
                        await websocket.send(text)
                    except sr.UnknownValueError:
                        await websocket.send("Could not understand audio")
                    except sr.RequestError as e:
                        await websocket.send(f"Could not request results; {e}")
    except websockets.exceptions.ConnectionClosed:
        print("Connection closed")

start_server = websockets.serve(handle_audio, "localhost", 8765)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
