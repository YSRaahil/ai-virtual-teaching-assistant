import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai  # Using Gemini API

# Load environment variables
load_dotenv()

# Get API Key from .env file
gemini_api_key = os.getenv("GEMINI_API_KEY")

if not gemini_api_key:
    print("❌ ERROR: Gemini API key not found. Check your .env file!")
else:
    print("🔑 Gemini Key Loaded Successfully")

# Configure Gemini API
genai.configure(api_key=gemini_api_key)

# List available models for debugging
try:
    print("🔍 Available Gemini Models:")
    models = genai.list_models()
    for model in models:
        print(f"➡️ {model.name}")  # Prints available models
except Exception as e:
    print(f"⚠️ Error fetching models: {e}")

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

@app.route("/")
def home():
    return "BODH AI Backend is Running!"

@app.route("/chat", methods=["POST"])
def chat():
    """
    Handles chatbot requests from the frontend.
    """
    try:
        data = request.json
        user_message = data.get("message", "").strip()
        chat_context = data.get("context", [])

        print(f"📩 User Message: {user_message}")  # Debugging log

        if not user_message:
            return jsonify({"status": "error", "response": "No message provided"}), 400

        # Call Gemini API to get response
        model = genai.GenerativeModel("gemini-pro")  # Use a valid model
        response = model.generate_content(user_message)

        print("🛠 AI Response:", response.text)  # Debugging log

        return jsonify({"status": "success", "response": response.text})
    
    except Exception as e:
        print("🚨 Error in chat endpoint:", str(e))
        return jsonify({"status": "error", "response": "Server error"}), 500

if __name__ == "__main__":
    app.run(debug=True)
