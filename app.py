
from flask import Flask, render_template, request, jsonify, session, send_file
from openai import OpenAI
import azure.cognitiveservices.speech as speechsdk
import os
import re
from dotenv import load_dotenv
import requests
import uuid 

app = Flask(__name__)
app.secret_key = "aadu-tina-secret"

load_dotenv()
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_REGION = os.getenv("AZURE_REGION")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_KEY)

VOICE_MAP = {
    "English": "en-IN-NeerjaNeural",
    "Hindi": "hi-IN-SwaraNeural",
    "Bengali": "bn-IN-TanishaaNeural",
    "Malayalam": "ml-IN-SobhanaNeural",
    "Tamil": "ta-IN-PallaviNeural",
    "Telugu": "te-IN-ShrutiNeural",
    "Kannada": "kn-IN-SapnaNeural"
}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/books')
def list_books():
    book_folder = 'static/pdf/books'
    try:
        book_files = [f for f in os.listdir(book_folder) if f.endswith('.pdf')]
        return jsonify({"books": book_files})
    except Exception as e:
        print("Book folder error:", e)
        return jsonify({"books": []})

@app.route('/start', methods=['POST'])
def start():
    data = request.json
    session['child_name'] = data.get("child_name", "Child")
    session['topic'] = data.get("topic", "ABCD")
    session['book_name'] = data.get("book_name", "Gruffalo.pdf")
    session['language'] = data.get("language", "English")
    session['current_page'] = 1

    child_name = session['child_name']
    topic = session['topic']
    book_name = session['book_name']

    intro_prompt = f"You are Tina Aunty, a cheerful, loving teacher for {child_name}. Respond in {session['language']}. "

    if topic == "ABCD":
        intro_prompt += "We are learning ABCD. Go one letter at a time. Say the letter and a word for it."
    elif topic == "Numbers 1-10":
        intro_prompt += "We are learning numbers. Make it playful and age-appropriate."
    elif topic == "Rhymes":
        intro_prompt += "Only sing rhymes like Twinkle Twinkle or Baby Shark. Don’t talk about any books."
    elif topic == "Books":
        intro_prompt += f"We are reading the book '{book_name}'. Only read one page at a time and say 'Let's read Page X'. Ask the child questions and wait for a reply."
    elif topic == "Talk Heart to Heart":
        intro_prompt += "This is a free conversation with the child. Listen, respond gently and make the child feel loved."

    session['chat_history'] = [{"role": "system", "content": intro_prompt}]
    return jsonify({"message": f"Welcome {child_name}! Tina Aunty is ready to chat about {topic}!"})

@app.route('/talk', methods=['POST'])
def talk():
    user_input = request.json.get("message")
    if not user_input:
        return jsonify({"response": "Tina Aunty didn’t hear that. Can you try again?"})

    if session.get("language") != "English":
        try:
            translation = translate_to_english(user_input)
            user_input = translation
        except:
            pass

    chat_history = session.get('chat_history', [])
    chat_history.append({"role": "user", "content": user_input})

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=chat_history,
            temperature=0.6,
            max_tokens=300
        )
        bot_message = response.choices[0].message.content
    except Exception as e:
        print("OpenAI error:", e)
        bot_message = "Oops! Tina Aunty had a hiccup!"

    chat_history.append({"role": "assistant", "content": bot_message})
    session['chat_history'] = chat_history

    image_name = None
    if session.get("topic") == "ABCD":
        match = re.search(r"\b([A-Z])\b", bot_message)
        if match:
            letter = match.group(1)
            image_path = f"static/img/alphabets/{letter}.png"
            if os.path.exists(image_path):
                image_name = f"/static/img/alphabets/{letter}.png"

    return jsonify({"response": bot_message, "image_url": image_name})

def translate_to_english(text):
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_SPEECH_KEY,
        'Ocp-Apim-Subscription-Region': AZURE_REGION,
        'Content-type': 'application/json'
    }
    body = [{"text": text}]
    params = "?api-version=3.0&to=en"
    response = requests.post(
        f"https://api.cognitive.microsofttranslator.com/translate{params}",
        headers=headers,
        json=body
    )
    result = response.json()
    return result[0]['translations'][0]['text']

@app.route('/check_timeout', methods=['POST'])
def check_timeout():
    data = request.json
    message = data.get("message", "")

    if session.get("language") != "English":
        try:
            message = translate_to_english(message)
        except:
            pass

    chat = [
        {"role": "system", "content": "You are a helpful assistant that decides if the user is requesting a timeout (e.g., going to toilet, being called by mom or any other requirement to take an indefinite break). Reply only 'true' or 'false'."},
        {"role": "user", "content": f"Is the following a timeout request? '{message}'"}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=chat,
            temperature=0,
            max_tokens=5
        )
        result = response.choices[0].message.content.strip().lower()
        is_timeout = "true" in result
    except Exception as e:
        print("Timeout check failed:", e)
        is_timeout = False

    return jsonify({"is_timeout": is_timeout})

@app.route('/pdf/<book>')
def show_book(book):
    path = f"static/pdf/books/{book}"
    if os.path.exists(path):
        return send_file(path, mimetype="application/pdf")
    else:
        return "Book not found", 404
#New

@app.route('/speak', methods=['POST'])
def speak():
    text = request.json.get("text")
    language = session.get("language", "English")
    voice_name = VOICE_MAP.get(language, "en-IN-NeerjaNeural")
    ssml = (
        f"<speak version='1.0' xml:lang='en-IN'>"
        f"<voice name='{voice_name}'>"
        f"<express-as style='cheerful'>"
        f"<prosody rate='medium' pitch='+15%'>"
        f"{text}"
        f"</prosody>"
        f"</express-as>"
        f"</voice>"
        f"</speak>"
    )
    try:
        speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_REGION)
        speech_config.speech_synthesis_voice_name = voice_name
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
        )
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
        result = synthesizer.speak_ssml_async(ssml).get()
        audio_stream = speechsdk.AudioDataStream(result)
        # New starts
        unique_filename = f"output_{uuid.uuid4().hex}.mp3"
        output_path = f"static/{unique_filename}"
        audio_stream.save_to_wav_file(output_path)
        return jsonify({"status": "spoken", "url": f"/{output_path}"})
        # New ends
    except Exception as e:
        print("Azure TTS error:", e)
        return jsonify({"status": "error", "message": str(e)})
        


#New ends


    except Exception as e:
        print("Azure TTS error:", e)
        return jsonify({"status": "error", "message": str(e)})
@app.route('/reset', methods=['POST'])
def reset():
    session.clear()
    return jsonify({"message": "Session reset."})

if __name__ == '__main__':
    #app.run(debug=True, port=5001)
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
