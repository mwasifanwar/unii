from flask import Flask, request, jsonify, render_template, redirect, session, url_for, flash
import os, json, uuid, logging
from werkzeug.utils import secure_filename
from math import ceil
from rapidfuzz import fuzz
from flask_cors import CORS
from flask import send_from_directory, abort
from deep_translator import GoogleTranslator
import re, spacy
nlp = spacy.load('en_core_web_sm')

app = Flask(__name__, static_folder='static')

CORS(app)
app.secret_key = 'your_secret_key'
app.config['SESSION_TYPE'] = 'filesystem'

UPLOAD_FOLDER = 'static/student_documents'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

TICKETS_FILE = 'tickets_db.json'
ADMIN_CREDENTIALS = {'admin': 'password123'}  # Admin credentials
PROFESSOR_CREDENTIALS = {'professor': 'pass123'} # Professor credentials
ALLOWED_EXTENSIONS = {'pdf', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER



logging.basicConfig(level=logging.DEBUG)

tokens = {}
STUDENT_DATA_DIR = 'student_data'
STUDENTS_FILE = os.path.join(STUDENT_DATA_DIR, 'students_db.json')
QUESTIONS_FILE = 'questions.json' 
DOCUMENT_REQUESTS_FILE = 'document_requests.json'

REMINDERS_FILE = 'reminders.json'


if os.path.exists(TICKETS_FILE):
    with open(TICKETS_FILE, 'r') as file:
        tickets_db = json.load(file)
else:
    tickets_db = {}


if not os.path.exists(STUDENT_DATA_DIR):
    os.makedirs(STUDENT_DATA_DIR)

if os.path.exists(STUDENTS_FILE):
    with open(STUDENTS_FILE, 'r') as f:
        students_db = json.load(f)
else:
    students_db = {}


if os.path.exists(QUESTIONS_FILE):
    with open(QUESTIONS_FILE, 'r') as f:
        questions_data = json.load(f)
else:
    questions_data = {}


if os.path.exists(DOCUMENT_REQUESTS_FILE):
    with open(DOCUMENT_REQUESTS_FILE, 'r') as f:
        document_requests_data = json.load(f)
else:
    document_requests_data = {}
    
# Load reminders data from JSON file
def load_reminders():
    if os.path.exists(REMINDERS_FILE):
        with open(REMINDERS_FILE, 'r') as file:
            reminders_data = json.load(file)
    else:
        reminders_data = {"professors": {}}
    return reminders_data

reminders_data = load_reminders()

# Save reminders data to JSON file
def save_reminders():
    with open(REMINDERS_FILE, 'w') as file:
        json.dump(reminders_data, file, indent=4)

# ------------------- Admin Routes and Functions -------------------


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if 'admin' not in session:
        return redirect('/admin-login')

    if request.method == 'POST':
        ticket_number = request.form.get('ticket_number')
        status = request.form.get('status')

        if 'file' in request.files:
            file = request.files['file']
            if file and allowed_file(file.filename):
                if ticket_number in tickets_db:
                    student_id = tickets_db[ticket_number]['student_id']
                    document_type = tickets_db[ticket_number]['document_type']

                    extension = file.filename.rsplit('.', 1)[1].lower()
                    filename = secure_filename(f"{document_type}_{ticket_number}.{extension}")

                    student_folder = os.path.join(app.config['UPLOAD_FOLDER'], student_id)
                    os.makedirs(student_folder, exist_ok=True)

                    file_path = os.path.join(student_folder, filename)
                    file.save(file_path)

                    tickets_db[ticket_number]['status'] = status
                    tickets_db[ticket_number]['file_path'] = file_path  
                    save_tickets_db()

                    flash('File uploaded and status updated successfully.', 'success')
                else:
                    flash('Invalid ticket number', 'danger')
            else:
                flash('Invalid file type. Only PDF and DOCX files are allowed.', 'danger')
        else:
            flash('No file uploaded.', 'danger')

    tickets_per_page = 10
    total_tickets = len(tickets_db)
    page = int(request.args.get('page', 1))
    total_pages = ceil(total_tickets / tickets_per_page)

    start = (page - 1) * tickets_per_page
    end = start + tickets_per_page
    tickets_on_page = dict(list(tickets_db.items())[start:end])

    return render_template('admin_panel.html', tickets_db=tickets_on_page, page=page, total_pages=total_pages)

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'password123':
            session['admin'] = True
            return redirect('/admin')
        else:
            flash('Invalid login credentials', 'danger')
    return render_template('admin_login.html')

@app.route('/admin-logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin-login')

def save_tickets_db():
    with open(TICKETS_FILE, 'w') as file:
        json.dump(tickets_db, file)



# ------------------- Professor Routes and Functions -------------------

@app.route('/professor-login', methods=['GET', 'POST'])
def professor_login():
    if request.method == 'POST':
        professor_id = request.form.get('professor_id')
        password = request.form.get('password')

        if professor_id in PROFESSOR_CREDENTIALS and PROFESSOR_CREDENTIALS[professor_id] == password:
            session['professor_id'] = professor_id
            session['active_bot'] = 'professor_reminders'
            return redirect('/professor-dashboard')
        else:
            flash('Invalid credentials, please try again.', 'danger')
    
    return render_template('professor_login.html')


@app.route('/professor-dashboard', methods=['GET', 'POST'])
def professor_dashboard():
    if 'professor_id' not in session:
        return redirect('/professor-login')
    
    professor_id = session['professor_id']
    
    if request.method == 'POST':
       
        reminder_type = request.form.get('reminder_type')
        description = request.form.get('description')
        due_date = request.form.get('due_date')
        
        new_reminder = {
            "type": reminder_type,
            "description": description,
            "due_date": due_date
        }
        
       
        if professor_id not in reminders_data['professors']:
            reminders_data['professors'][professor_id] = {'reminders': []}
        
        reminders_data['professors'][professor_id]['reminders'].append(new_reminder)
        save_reminders()
        flash('Reminder added successfully!', 'success')
    
  
    reminders = reminders_data['professors'].get(professor_id, {}).get('reminders', [])
    
    return render_template('professor_dashboard.html', reminders=reminders)


@app.route('/professor-reminders', methods=['GET', 'POST'])
def professor_reminders():
    if 'professor_id' not in session:
        return redirect('/professor-login')
    
    return render_template('professor_reminders.html')


@app.route('/professor-reminder-webhook', methods=['POST'])
def professor_reminder_webhook():
    try:
        req = request.get_json(silent=True, force=True)
        professor_id = session.get('professor_id')

        if not professor_id:
            return jsonify({'fulfillmentText': "Please login first to view your reminders."})

        message = req.get('queryResult', {}).get('queryText', '').lower()

       
        reminders = reminders_data['professors'].get(professor_id, {}).get('reminders', [])

    
        keywords = {
            'meeting': ['meeting', 'student meeting', 'do i have any meetings', 'scheduled meeting'],
            'exam review': ['exam review', 'exam', 'review'],
            'assignment grading': ['assignment grading', 'grading', 'assignment', 'grade'],
            'project presentation': ['project presentation', 'presentation', 'project'],
            'all reminders': ['all reminders', 'upcoming reminders', 'what are my reminders', 'tasks']
        }

       
        def find_reminder_type(reminder_type_keywords):
            for keyword in reminder_type_keywords:
                if keyword in message:
                    return keyword
            return None

     
        if any(kw in message for kw in keywords['all reminders']):
            if reminders:
                reminders_text = "\n".join(
                    [f"{reminder['type']}: {reminder['description']} (Due: {reminder['due_date']})"
                     for reminder in reminders]
                )
                return jsonify({'fulfillmentText': f"Here are your reminders:\n{reminders_text}"})
            else:
                return jsonify({'fulfillmentText': "You have no reminders at the moment."})

       
        for reminder in reminders:
            reminder_type_lower = reminder['type'].lower()

            if find_reminder_type(keywords['meeting']) and 'meeting' in reminder_type_lower:
                return jsonify({
                    'fulfillmentText': f"You have a meeting: {reminder['description']} (Due: {reminder['due_date']})."
                })

            if find_reminder_type(keywords['exam review']) and 'exam review' in reminder_type_lower:
                return jsonify({
                    'fulfillmentText': f"Your exam review is scheduled: {reminder['description']} (Due: {reminder['due_date']})."
                })

            if find_reminder_type(keywords['assignment grading']) and 'assignment grading' in reminder_type_lower:
                return jsonify({
                    'fulfillmentText': f"You need to grade an assignment: {reminder['description']} (Due: {reminder['due_date']})."
                })

            if find_reminder_type(keywords['project presentation']) and 'project presentation' in reminder_type_lower:
                return jsonify({
                    'fulfillmentText': f"You have a project presentation to review: {reminder['description']} (Due: {reminder['due_date']})."
                })

        
        return jsonify({'fulfillmentText': "I'm sorry, I couldn't find any relevant reminders."})

    except Exception as e:
        logging.error(f"Error processing professor reminder request: {e}")
        return jsonify({'fulfillmentText': 'Sorry, there was an error processing your request.'})



# ------------------- Main app Routes and Functions -------------------



def load_course_questions():
    json_path = 'coursequestions.json'
    with open(json_path, 'r', encoding='utf-8') as file:
        course_questions = json.load(file)
    logging.debug(f"Course questions loaded with {len(course_questions['intents'])} intents.")
    return course_questions


course_questions = load_course_questions()

@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        password = request.form.get('password')

        if student_id in students_db and students_db[student_id]['password'] == password:
            token = str(uuid.uuid4())
            tokens[token] = student_id
            session['student_id'] = student_id
            session['token'] = token
            
            
            if os.path.exists(f"{STUDENT_DATA_DIR}/{student_id}_page1.json"):
                return render_template('login.html', existing_user='true')
            else:
                return redirect('/options')
        else:
            return render_template('login.html', error="Invalid Student ID or Password")
    return render_template('login.html', existing_user='false')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            return render_template('signup.html', error="Passwords do not match")

        if student_id in students_db:
            return render_template('signup.html', error="Student ID already exists")

        students_db[student_id] = {
            'name': name,
            'email': email,
            'password': password
        }

        with open(STUDENTS_FILE, 'w') as f:
            json.dump(students_db, f)

        return redirect('/login')

    return render_template('signup.html')

@app.route('/options')
def options():
    if 'student_id' not in session:
        return redirect('/login')
    return render_template('options.html')

@app.route('/chatbot')
def chatbot():
    if 'student_id' not in session:
        return redirect('/login')
    return render_template('chatbot.html')


@app.route('/coursework-management')
def coursework_management():
    if 'student_id' not in session:
        return redirect('/login')

    session['active_bot'] = 'coursework' 
    return render_template('courseworkbot.html')  

@app.route('/questionsbot')
def questionsbot():
    if 'student_id' not in session:
        return redirect('/login')
    
    session['active_bot'] = 'questions'
    return render_template('questionsbot.html')

@app.route('/documentsbot')
def documentsbot():
    if 'student_id' not in session:
        return redirect('/login')
    
    session['active_bot'] = 'documents'
    return render_template('documentsbot.html')


@app.route('/translate', methods=['POST'])
def translate():
    data = request.json
    message = data.get('message')
    current_language = data.get('currentLanguage')  

    if not message:
        return jsonify({'error': 'No message provided'}), 400


    target_language = 'pt' if current_language == 'en' else 'en'

    try:
       
        translated_text = GoogleTranslator(source=current_language, target=target_language).translate(message)
        return jsonify({
            'translatedText': translated_text, 
            'newLanguage': target_language  
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        token = req.get('token')
        student_id = tokens.get(token)

        if not student_id:
            logging.error("Invalid token or session expired")
            raise ValueError("Invalid token or session expired")

       
        active_bot = session.get('active_bot', None)  
        
        message = req.get('queryResult', {}).get('queryText', '').lower()
        intent = req.get('queryResult', {}).get('intent', {}).get('displayName', '').lower()

        logging.debug(f"Received message: {message}")
        logging.debug(f"Determined intent: {intent}")
        
       
        if active_bot == 'questions':
            
            if message.strip().lower() in ['hello', 'hi', 'olá', 'oi']:
                return jsonify({'fulfillmentText': "Hello! How can I assist you with your questions today?"})
            return handle_question_query(message) 

        elif active_bot == 'documents':
           
            if message.strip().lower() in ['hello', 'hi', 'olá', 'oi']:
                session['greeted'] = True
                session['collecting_details'] = True
                session['details_step'] = 'name'
                return jsonify({'fulfillmentText': "Hi, welcome to ISLA University Documents Bot! Could you please provide your first name?"})

            
            if 'collecting_details' in session and session['collecting_details']:
                if session['details_step'] == 'name':
                    session['student_name'] = message
                    session['details_step'] = 'last_name'
                    return jsonify({'fulfillmentText': "Thank you! Could you please provide your last name?"})
                
                elif session['details_step'] == 'last_name':
                    session['student_last_name'] = message
                    session['details_step'] = 'student_id'
                    return jsonify({'fulfillmentText': "Got it! Now, please provide your Student ID."})
                
                elif session['details_step'] == 'student_id':
                    session['student_id'] = message
                    session['details_step'] = 'course'
                    return jsonify({'fulfillmentText': "Great! Which course are you enrolled in?"})
                
                elif session['details_step'] == 'course':
                    session['course'] = message
                    session['details_step'] = 'reason'
                    return jsonify({'fulfillmentText': "Finally, please provide the reason for your document request."})
                
                elif session['details_step'] == 'reason':
                    session['reason'] = message
                    session['collecting_details'] = False
                    response_text = "Thank you for providing your details! How can I assist you today?"
                    return jsonify({'fulfillmentText': response_text})

         
            if 'greeted' in session and 'student_name' in session:  
                if any(keyword in message for keyword in [
        'transcript', 'enrollment verification', 'certificate', 'documents', 'financial aid document', 
        'graduation documents', 'student ID replacement', 'academic probation letter', 
        'course completion certificate', 'internship verification', 'fee payment receipt', 
        'scholarship confirmation', 'visa letter', 'health insurance card', 'academic appeal form', 
        'disciplinary action notice', 'residency verification', 'research participation confirmation', 
        'letter of recommendation request', 'student housing application', 'enrollment/registration certificate', 
        'diploma/graduation certificate', 'attendance certificate', 'course syllabus', 'program description', 
        'financial aid or scholarship documentation', 'internship agreement forms', 'tuition payment receipt', 
        'proof of english proficiency', 'proof of portuguese proficiency', 'examination results', 
        'change of course request', 'request for academic leave', 'visa support letter','document','registration document'
    ]):
                    response_text = handle_document_request(message, session['student_id'])
                    return jsonify({'fulfillmentText': response_text})
                
                
                elif 'status' in message or 'track' in message or 'ticket' in message:
                    response_text = track_ticket_status(session['student_id'])
                    return jsonify({'fulfillmentText': response_text})
                
               
                if 'yes' in message or 'no' in message:
                    follow_up_response = handle_follow_up(message)
                    return jsonify({'fulfillmentText': follow_up_response})

            
            ticket_number = extract_ticket_number(message)
            if ticket_number:
                response_text = track_ticket_by_number(ticket_number, session['student_id'])
                return jsonify({'fulfillmentText': response_text})

           
            if 'document' in message or 'status' in message or 'track' in message:
                response_text = handle_general_request(message, session['student_id'])
                return jsonify({'fulfillmentText': response_text})
            
            
            return jsonify({'fulfillmentText': "I'm sorry, I couldn't process your request. Could you clarify what you need?"})


        elif active_bot == 'coursework':
            
            if message.strip().lower() in ['hello', 'hi', 'olá', 'oi']:
                return jsonify({'fulfillmentText': "Hello! How can I assist you with your coursework today?"})
            
           
            
            if any(keyword in message.lower() for keyword in ['instructor', 'teacher', 'professor', 'quem é o professor']):
                return handle_course_query(message)
            
            
            elif any(keyword in message.lower() for keyword in ['ects', 'credit', 'créditos']):
                return handle_course_query(message)
            
            
            elif any(keyword in message.lower() for keyword in ['contact hour', 'hours', 'horas', 'contacto']):
                return handle_course_query(message)
            
           
            elif any(keyword in message.lower() for keyword in ['syllabus', 'plano de estudos']):
                return handle_course_query(message)
            else:
                return jsonify({'fulfillmentText': "I didn't quite catch that. Can you ask about the instructor, ECTS, contact hours, or syllabus of a course?"})

        
        return jsonify({'fulfillmentText': "I'm sorry, I didn't understand your request. Could you please clarify?"})

    except Exception as e:
        logging.error(f"Error processing request: {e}")
        return jsonify({'fulfillmentText': 'Sorry, there was an error processing your request.'})

def extract_ticket_number(message):
   
    match = re.search(r'\b([A-F0-9]{8})\b', message.upper())  
    if match:
        return match.group(1) 
    return None


def track_ticket_by_number(ticket_number, student_id):
    ticket_number = ticket_number.upper().strip() 
    with open('tickets_db.json', 'r') as file:
        tickets_db = json.load(file)
    
   
    ticket_info = tickets_db.get(ticket_number)
    if ticket_info and ticket_info['student_id'] == student_id:
        return f"Your ticket {ticket_number} is {ticket_info['status']}."
    else:
        return "I couldn't find any request with that ticket number. Please check the number and try again."
    

def handle_document_request(message, student_id):
    best_match = None
    best_score = 0
    doc = nlp(message)

    
    keywords = ['transcript', 'certificate', 'enrollment verification', 'status', 'track', 'documents']

    for item in document_requests_data.get("intents", []):
        document_type = item.get("document_type", "").lower()

        
        if any(keyword in doc.text.lower() for keyword in keywords):
            score = fuzz.partial_ratio(message, document_type)
        else:
            score = fuzz.ratio(message, document_type)

        logging.debug(f"Matching '{message}' against '{document_type}' with score {score}")

        if score > best_score:
            best_score = score
            best_match = item

    if best_score > 75:
        
        for ticket in tickets_db.values():
            if ticket['student_id'] == student_id and ticket['document_type'] == best_match['document_type']:
                session['last_ticket'] = ticket['ticket_number']
                return (f"You already have an open request for {best_match['document_type']}. "
                        f"Your ticket number is {ticket['ticket_number']}. The status is: {ticket['status']}.")

        
        ticket_number = str(uuid.uuid4()).split('-')[0].upper()
        session['last_ticket'] = ticket_number

        request_data = {
            "student_id": student_id,
            "document_type": best_match['document_type'],
            "status": "pending",
            "ticket_number": ticket_number,
        }
        tickets_db[ticket_number] = request_data
        save_tickets_db()

        logging.debug(f"New ticket created: {ticket_number} for student {student_id}")
        return (f"Your request for {best_match['document_type']} has been received. "
                f"Your ticket number is {ticket_number}. {best_match['additional_info']}")
    else:
        logging.warning(f"No suitable match found for message: {message}")
        return "I'm sorry, I couldn't find the document you're looking for. Could you clarify?"



def track_ticket_status(student_id):
  
    logging.debug(f"track_ticket_status called for student ID: {student_id}")
    try:
       
        with open('tickets_db.json', 'r') as file:
            tickets_db = json.load(file)

        logging.debug(f"Loaded tickets from tickets_db.json: {tickets_db}")

        
        student_tickets = [ticket_info for ticket_info in tickets_db.values() if ticket_info.get('student_id') == student_id]

        logging.debug(f"Tickets found for student ID {student_id}: {student_tickets}")

        
        if not student_tickets:
            logging.debug(f"No tickets found for student ID: {student_id}")
            return "You don't have any open document requests."

       
        response_text = "\n".join([f"Document: {ticket.get('document_type', 'Unknown').capitalize()}, Status: {ticket.get('status', 'Unknown')}, Ticket ID: {ticket.get('ticket_number', 'Unknown')}"
                                   for ticket in student_tickets])

        logging.debug(f"Generated response text: {response_text}")

        return f"Here are the statuses of your requested documents:\n{response_text}"

    except FileNotFoundError:
        logging.error("Tickets database file not found.")
        return "The tickets database is currently unavailable."
    except Exception as e:
        logging.error(f"Error while tracking document status for student {student_id}: {e}")
        return "An error occurred while tracking your document requests."


def handle_general_request(message, student_id):
   
    status_keywords = [
        'status', 'track', 'progress', 'request', 'what is the status', 'check the status', 'my document requests',
        'document status', 'ticket status', 'document progress', 'document requests'
    ]
    
    
    if any(keyword in message.lower() for keyword in status_keywords):
        logging.debug(f"Query about documents or status detected. Processing status request for student ID: {student_id}")
        return track_ticket_status(student_id)
    
   
    ticket_number = extract_ticket_number(message)
    if ticket_number:
        logging.debug(f"Extracted ticket number: {ticket_number}. Tracking specific ticket.")
        return track_ticket_by_number(ticket_number, student_id)

    
    return "I'm sorry, I couldn't process your request. Could you clarify what you need?"




        
@app.route('/documents-portal')
def documents_portal():
    if 'student_id' not in session:
        return redirect('/login')

    student_id = session['student_id']
    student_documents_path = os.path.join(app.config['UPLOAD_FOLDER'], student_id)

    if os.path.exists(student_documents_path):
        documents = os.listdir(student_documents_path)
    else:
        documents = []

    return render_template('documents_portal.html', documents=documents)



@app.route('/download/<student_id>/<filename>')
def download_document_from_portal(student_id, filename):
    student_documents_path = os.path.join(app.config['UPLOAD_FOLDER'], student_id)
    try:
        return send_from_directory(student_documents_path, filename, as_attachment=True)
    except FileNotFoundError:
        return abort(404, description="File not found")


def handle_follow_up(message):
    last_document = session.get('last_document', None)

    if not last_document:
        return "I'm not sure which document you're referring to. Could you clarify?"

    if 'yes' in message:
        return (f"Great! You can submit your {last_document['document_type']} request via the student portal. "
                "Please have your student ID ready. If you encounter any issues, contact the "
                f"{last_document['location']} for assistance.")
    elif 'no' in message:
        return f"Alright. If you need more help with your {last_document['document_type']}, feel free to visit the {last_document['location']} directly."

    return "Could you please clarify your response?"


def save_tickets_db():
    with open('tickets_db.json', 'w') as file:
        json.dump(tickets_db, file)



def detect_language(text):
    if re.search(r'[áàâãéêíóôõúç]', text, re.IGNORECASE) or any(word in text.lower() for word in ['quem', 'quantos', 'horas']):
        return 'pt'
    return 'en'


def clean_text(text, language='en'):
    if not text:
        return ""
    
   
    if language == 'pt':
        return re.sub(r'[^\w\s]', '', text).strip().lower()
    
   
    accent_mapping = {
        'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o',
        'ú': 'u', 'ç': 'c', 'Á': 'a', 'À': 'a', 'Â': 'a', 'Ã': 'a', 'É': 'e', 'Ê': 'e', 'Í': 'i', 'Ó': 'o',
        'Ô': 'o', 'Õ': 'o', 'Ú': 'u', 'Ç': 'c', 'ü': 'u', 'ñ': 'n', 'ß': 's'
    }
    text_cleaned = ''.join([accent_mapping.get(c, c) for c in text])
    return re.sub(r'[^\w\s]', '', text_cleaned).strip().lower()


def fuzzy_match(query, choices, threshold=70):
    best_match = None
    highest_score = 0
    for choice in choices:
        score = fuzz.ratio(query, choice)
        if score > highest_score and score >= threshold:
            highest_score = score
            best_match = choice
    return best_match, highest_score


def token_match(query, choices, threshold=2):
    query_tokens = set(query.split())
    for choice in choices:
        choice_tokens = set(choice.split())
        
        if len(query_tokens & choice_tokens) >= threshold:
            return choice
    return None

def handle_course_query(message):
    logging.debug(f"Received query: {message}")
    
  
    language = detect_language(message)
    logging.debug(f"Detected language: {language}")
    
    
    cleaned_message = clean_text(message, language=language)
    logging.debug(f"Cleaned message for matching: {cleaned_message}")

   
    question_map = {}
    
    
    for intent in course_questions['intents']:
        cleaned_question = clean_text(intent['question'], language=language)
        question_map[cleaned_question] = intent['id']

   
    if cleaned_message in question_map:
        matched_id = question_map[cleaned_message]
        logging.debug(f"Exact match found with ID: {matched_id}")
        
        
        for intent in course_questions['intents']:
            if intent['id'] == matched_id:
                return jsonify({'fulfillmentText': intent['response']})

    
    logging.warning(f"No matching question found for: {message}")
    return jsonify({'fulfillmentText': "Sorry, I couldn't find the information you're asking for."})


def handle_question_query(message):
    message = message.lower()
    best_match = None
    best_score = 0

    for item in questions_data.get("intents", []):
        question = item.get("question", "").lower()
        score = fuzz.partial_ratio(message, question)
        
        if score > best_score:
            best_score = score
            best_match = item

    if best_score > 75:
        return jsonify({'fulfillmentText': best_match.get("response", "Sorry, I don't have an answer for that.")})
    
    return jsonify({'fulfillmentText': "I'm sorry, I didn't understand that. Could you please rephrase your question?"})


def load_student_data(student_id, page):
    try:
        with open(f"{STUDENT_DATA_DIR}/{student_id}_page{page}.json", "r") as file:
            data = json.load(file)
            logging.debug(f"Loaded data from page{page}.json: {data}")
            return data
    except FileNotFoundError:
        logging.error(f"File {student_id}_page{page}.json not found.")
        return {}
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON for {student_id}_page{page}.json: {e}")
        return {}



if __name__ == '__main__':
    app.run(debug=True)
