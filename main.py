import asyncio
import base64
import io
import json
import os
import sqlite3
from typing import Dict, List, Optional, Tuple, Union

import speech_recognition as sr
import websockets
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from openai import AsyncOpenAI
from pydub import AudioSegment
from websockets.server import WebSocketServerProtocol

load_dotenv()


DATABASE_NAME = os.getenv("DATABASE_NAME")
WEBSOCKET_HOST =  os.getenv("WEBSOCKET_HOST")
WEBSOCKET_PORT = os.getenv("WEBSOCKET_PORT")

# Initialize clients
# TODO: Use environment variables for API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")


client = ElevenLabs(
    api_key=ELEVENLABS_API_KEY
)


openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


# Voice IDs for different characters
VOICE_IDS: Dict[str, str] = {
    "Santa": "Gqe8GJJLg3haJkTwYj2L",
    "Scientist": "Mg1264PmwVoIedxsF9nu",
    "Benny": "INHnGXKnJqauobZLfeOV",
    "BestFriend": "0m2tDjDewtOfXrhxqgrJ",
}

# Initialize speech recognizer
recognizer = sr.Recognizer()

# Database connection
conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()


async def get_prompt(character: str) -> Optional[str]:
    """Fetch the prompt for a given character from the database."""
    cursor.execute("SELECT prompt FROM prompts WHERE character=?", (character,))
    prompt = cursor.fetchone()
    return prompt[0] if prompt else None


async def get_ai_response(text: str, character: str, user_id: int) -> str:
    """Generate an AI response based on the user's input and conversation history."""
    try:
        conversation_history = await get_conversation(user_id, character)
        conversation_history.append({"role": "user", "content": text})

        prompt_template = await get_prompt(character)
        if prompt_template:
            conversation_history[0]["content"] = prompt_template

        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo", messages=conversation_history
        )

        ai_message = response.choices[0].message.content

        conversation_history.append({"role": "assistant", "content": ai_message})

        # Save the conversation history in the database
        cursor.executemany(
            "INSERT INTO history (user_id, character, role, content) VALUES (?, ?, ?, ?)",
            [
                (user_id, character, "user", text),
                (user_id, character, "assistant", ai_message),
            ],
        )
        conn.commit()

        return ai_message
    except Exception as e:
        print(f"Error getting AI response: {e}")
        return "Sorry, I couldn't process that request."


async def get_user_by_ip(ip_address: str) -> Optional[Tuple[int, str]]:
    """Fetch user information based on IP address."""
    cursor.execute(
        "SELECT id, selected_character FROM users WHERE ip_address = ?", (ip_address,)
    )
    return cursor.fetchone()


async def create_user(ip_address: str) -> None:
    """Create a new user entry in the database."""
    cursor.execute("INSERT INTO users (ip_address) VALUES (?)", (ip_address,))
    conn.commit()


async def update_selected_character(ip_address: str, character: str) -> None:
    """Update the selected character for a user."""
    cursor.execute(
        "UPDATE users SET selected_character = ? WHERE ip_address = ?",
        (character, ip_address),
    )
    conn.commit()


async def save_conversation(
    user_id: int, role: str, content: str, character: str
) -> None:
    """Save a conversation entry to the database."""
    cursor.execute(
        "INSERT INTO conversation_history (user_id, role, content, character) VALUES (?, ?, ?, ?)",
        (user_id, role, content, character),
    )
    conn.commit()


async def get_conversation(user_id: int, character: str) -> List[Dict[str, str]]:
    """Fetch the conversation history for a user and character."""
    cursor.execute(
        "SELECT role, content FROM conversation_history WHERE user_id = ? AND character = ?",
        (user_id, character),
    )
    rows = cursor.fetchall()

    conversation_history = [{"role": "system", "content": ""}]
    conversation_history.extend([{"role": row[0], "content": row[1]} for row in rows])

    return conversation_history


async def handle_audio(websocket: WebSocketServerProtocol, path: str) -> None:
    """Handle WebSocket connections and process audio/text messages."""
    try:
        ip_address = websocket.remote_address[0]

        while True:
            data = await websocket.recv()
            user = await get_user_by_ip(ip_address)
            if not user:
                await create_user(ip_address)
                user = await get_user_by_ip(ip_address)

            user_id, selected_character = user

            if isinstance(data, bytes):
                # Process audio data
                audio_segment = AudioSegment.from_file(io.BytesIO(data))
                wav_io = io.BytesIO()
                audio_segment.export(wav_io, format="wav")
                wav_io.seek(0)

                with sr.AudioFile(wav_io) as source:
                    audio = recognizer.record(source)
                    text = recognizer.recognize_google(audio)

                await save_conversation(user_id, "user", text, selected_character)
                ai_response = await get_ai_response(text, selected_character, user_id)
                await save_conversation(
                    user_id, "assistant", ai_response, selected_character
                )

                # Generate audio response
                audio_generator = client.generate(
                    text=ai_response,
                    voice=VOICE_IDS[selected_character],
                    model="eleven_multilingual_v2",
                )
                audio_buffer = io.BytesIO()
                for chunk in audio_generator:
                    audio_buffer.write(chunk)

                audio_buffer.seek(0)
                audio_base64 = base64.b64encode(audio_buffer.getvalue()).decode("utf-8")

                conversation_history = await get_conversation(
                    user_id, selected_character
                )

                response = json.dumps(
                    {
                        "text": ai_response,
                        "audio": audio_base64,
                        "history": conversation_history,
                    }
                )

                await websocket.send(response)

            else:
                # Process JSON data (text message)
                parsed_data = json.loads(data)
                if parsed_data["type"] == "get_history":
                    conversation = await get_conversation(user_id, selected_character)
                    response = json.dumps(
                        {"type": "conversation", "history": conversation}
                    )
                    await websocket.send(response)
                else:
                    character = parsed_data.get("character", "Santa")
                    await update_selected_character(ip_address, character)
                    conversation = await get_conversation(user_id, character)
                    response = json.dumps(
                        {"type": "conversation", "history": conversation}
                    )
                    await websocket.send(response)

    except websockets.exceptions.ConnectionClosed:
        print("Connection closed")


async def main() -> None:
    """Start the WebSocket server."""
    server = await websockets.serve(handle_audio, WEBSOCKET_HOST, WEBSOCKET_PORT)
    print(f"WebSocket server started on {WEBSOCKET_HOST}:{WEBSOCKET_PORT}")
    await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())

