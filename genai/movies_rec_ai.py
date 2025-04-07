from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import ast

load_dotenv()

api_key = os.getenv('GEMINI_API_KEY')
client = genai.Client(api_key=api_key)


def get_instructions(file_path):

    """Reads and returns instructions for GenAI from the specified file. Returns None if the file is not found."""

    try:
        with open(file_path, 'r') as file:
            instructions = file.read()
            return instructions
    except FileNotFoundError as e:
        print(f"File was not found: {e}")
        return None


def open_chat(instructions):

    """Creates and returns a new chat session using the provided system instructions."""

    return client.chats.create(model="gemini-2.0-flash", config=types.GenerateContentConfig(
            max_output_tokens=200,
            temperature=1.0,
            system_instruction=instructions
        ))


def get_chat_ai_recommendations(chat, contents):

    """Sends a message to the chat session, extracts a list of recommendations from the response text,
    and returns the parsed result or None on error."""

    response = chat.send_message(contents)
    result = response.text
    first_index = result.find('[')
    last_index = result.find(']')
    try:
        result = result[first_index:last_index + 1]
        result = ast.literal_eval(result)
        if not result:
            return None
        return result
    except (IndexError, SyntaxError) as e:
        print(f"Error: {e}")
        return None
