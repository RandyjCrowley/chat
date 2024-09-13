import sqlite3

# Connect to SQLite database
conn = sqlite3.connect('conversations.db')
cursor = conn.cursor()

# Create tables for users, prompts, and conversation history
cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS prompts (id INTEGER PRIMARY KEY, character TEXT, prompt TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, user_id INTEGER, character TEXT, role TEXT, content TEXT, FOREIGN KEY(user_id) REFERENCES users(id))''')

# Insert default prompts for Santa and Tooth Fairy
cursor.execute("INSERT OR IGNORE INTO prompts (character, prompt) VALUES ('Santa', 'DO NOT INCLUDE WORDS SIMILAR OR LIKE...')")
conn.commit()
