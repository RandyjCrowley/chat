import asyncio
import websockets
import speech_recognition as sr
import io
from pydub import AudioSegment
from gtts import gTTS
import base64
import json
from ollama import Client  # Make sure to install the ollama package: pip install ollama

# Initialize recognizer
r = sr.Recognizer()

# Initialize Ollama client
ollama_client = Client(host='http://localhost:11434')  # Adjust the host if needed

# Initialize conversation history
conversation_history = []

async def get_ai_response(text):
    global conversation_history
    try:
        # Add user message to conversation history
        conversation_history.append({"role": "user", "content": text})
        
        # Get response from Ollama
        response = ollama_client.chat(model='llama2', messages=conversation_history)
        
        ai_message = response['message']['content']
        
        # Add AI response to conversation history
        conversation_history.append({"role": "assistant", "content": ai_message})
        
        return ai_message
    except Exception as e:
        print(f"Error getting AI response: {e}")
        return "Sorry, I couldn't process that request."

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
                print("Received audio") 
                
                with sr.AudioFile(wav_io) as source:
                    audio = r.record(source)
                    try:
                        text = r.recognize_google(audio)
                        print(f"User said: {text}")
                        
                        # Get AI response
                        ai_response = await get_ai_response(text)
                        print(f"AI response: {ai_response}")
                        
                        # Convert AI response to speech
                        tts = gTTS(text=ai_response, lang='en')
                        mp3_fp = io.BytesIO()
                        tts.write_to_fp(mp3_fp)
                        mp3_fp.seek(0)
                        
                        # Encode audio to base64
                        audio_base64 = base64.b64encode(mp3_fp.read()).decode('utf-8')
                        
                        # Send both text and audio back to the client, along with the full conversation history
                        response = json.dumps({
                            'text': ai_response,
                            'audio': audio_base64,
                            'history': conversation_history
                        })
                        await websocket.send(response)
                        
                    except sr.UnknownValueError:
                        await websocket.send(json.dumps({'text': "Could not understand audio"}))
                    except sr.RequestError as e:
                        await websocket.send(json.dumps({'text': f"Could not request results; {e}"}))
    except websockets.exceptions.ConnectionClosed:
        print("Connection closed")

async def main():
    server = await websockets.serve(handle_audio, "0.0.0.0", 8765)
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
