import os
import sqlite3

from dotenv import load_dotenv

load_dotenv()
# Connect to your SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect(os.getenv("DATABASE_NAME"))
cursor = conn.cursor()

# Create the users table
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_address VARCHAR(45) UNIQUE,
    selected_character VARCHAR(255) DEFAULT 'Santa'
)
''')

# Create the conversation_history table
cursor.execute('''
CREATE TABLE IF NOT EXISTS conversation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    role TEXT, -- 'user' or 'assistant'
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    character VARCHAR(255),
    FOREIGN KEY (user_id) REFERENCES users (id)
)
''')

# Create the prompts table
cursor.execute('''
CREATE TABLE IF NOT EXISTS prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character TEXT,
    prompt TEXT
)
''')

# Commit the changes and close the connection
conn.commit()
conn.close()

