
from flask import Flask, Blueprint,render_template, request, redirect, url_for, jsonify, session,flash
import mysql.connector
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from flask_apscheduler import APScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from shutil import copyfile
import os
app = Flask(__name__)
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()
scheduler.start()
admin_bp = Blueprint('admin', __name__)
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'sathappanrathiga@gmail.com'      
app.config['MAIL_PASSWORD'] = 'qdnk eguo jgdk dgpe'       
mail = Mail(app)
app.secret_key = "your_secret_key_here"
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Rathi@06',
    'database': 'login'
}
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()
conn = mysql.connector.connect(
    host="localhost",
    user="root",       
    password="Rathi@06",
    database="login"       
)
cursor = conn.cursor()
VALID_SUBSKILLS = {
    "Technical": ["programming","python" ,"cpp","c","java","data structures", "web development", "AI", "machine learning"],
    "Soft Skill": ["communication", "teamwork", "problem solving","active listening","organization","decision making"],
    "Professional": ["time management", "leadership", "critical thinking","confidence bulding","adaptability","creativity"]
}
from functools import wraps
from flask import session, redirect, url_for
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            flash("🔒 Admin access required.", "warning")
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return decorated_function
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print("SESSION:", session)  # Add this line
        if 'email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
@app.route('/additional_notes')
def additional_notes():
    conn = None
    cursor = None
    materials = []
    
    # Capture filter arguments for persistence and query
    skill_type = request.args.get('skill_type')
    sub_skill = request.args.get('sub_skill')
    # NEW: Capture author_name filter
    author_name = request.args.get('author_name') 

    try:
        conn = get_db_connection()
        if not conn:
            flash("Database connection failed.", "danger")
            return render_template("additional_notes.html", materials=[], skill_type=skill_type, sub_skill=sub_skill, author_name=author_name)
            
        cursor = conn.cursor(dictionary=True)

        # 1. Start with the base query for PDFs
        query = "SELECT * FROM learning_material WHERE filetype = 'pdf'"
        filters = []
        
        # 2. Add Skill Type filter
        if skill_type and skill_type != "":
            query += " AND skill_type = %s"
            filters.append(skill_type)
            
        # 3. Add Sub-skill search filter
        if sub_skill:
            query += " AND sub_skill LIKE %s"
            filters.append(f"%{sub_skill}%")
            
        # 4. NEW: Add Author Name search filter
        if author_name:
            # Assumes 'learning_material' table has an 'author' column
            query += " AND author LIKE %s"
            filters.append(f"%{author_name}%")
        
        # 5. Execute the query
        query += " ORDER BY title"
        
        cursor.execute(query, tuple(filters))
        materials = cursor.fetchall()

    except mysql.connector.Error as err:
        # Log the error for backend debugging
        print(f"[DB ERROR] {err}")
        flash("Failed to load notes due to a database error.", "danger")
        return redirect(url_for('admin_admin')) 

    finally:
        # 6. Database Cleanup
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    # 7. Render template, passing all current filter values
    return render_template(
        "additional_notes.html", 
        materials=materials,
        skill_type=skill_type,
        sub_skill=sub_skill,
        author_name=author_name, # NEW: Passed back to retain state
        email="user@example.com"
    )

@app.route('/materials/<email>')
def view_materials(email):
    skill_type = request.args.get('skill_type')
    sub_skill = request.args.get('sub_skill')
    # NEW: Get the author search parameter
    author = request.args.get('author')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Note: The existing logic searches 'title' using the 'sub_skill' input.
    # We will preserve that logic and add the new 'author' filter.
    query = "SELECT * FROM learning_material WHERE 1=1"
    params = []

    if skill_type:
        query += " AND skill_type = %s"
        params.append(skill_type)

    if sub_skill:
        # Searches material title using the sub_skill input
        query += " AND title LIKE %s"
        params.append(f"%{sub_skill}%")

    # NEW: Filter by author if provided
    if author:
        query += " AND author LIKE %s"
        params.append(f"%{author}%")

    cursor.execute(query, tuple(params))
    materials = cursor.fetchall()
    cursor.close()

    return render_template('view_materials.html', 
                           materials=materials, 
                           email=email,
                           # Pass search params back for sticky form state
                           skill_type=skill_type,
                           sub_skill=sub_skill,
                           author=author)

@app.route('/search_progress', methods=['GET'])
@admin_required
def search_progress():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get search filters from query parameters
    search_email = request.args.get('email', '').strip().lower()
    search_skill = request.args.get('skill_type', '').strip()
    search_sub_skill = request.args.get('sub_skill', '').strip().lower()
    # NEW: Get the author search parameter
    search_author = request.args.get('author', '').strip().lower() 
    search_progress = request.args.get('progress_level', '').strip()

    # SQL query setup
    query = """
    SELECT wm.email, lm.skill_type, 
           ANY_VALUE(wm.sub_skill) AS sub_skill,
           ROUND(SUM((wm.watch_percentage / 100) * lm.duration) / SUM(lm.duration) * 100, 2) AS progress_percentage
    FROM watched_materials wm
    JOIN learning_material lm ON wm.material_id = lm.id
"""
    where_clauses = []
    params = []

    # Filter logic
    if search_email:
        where_clauses.append("LOWER(wm.email) = %s")
        params.append(search_email)

    if search_skill:
        where_clauses.append("lm.skill_type = %s")
        params.append(search_skill)

    if search_sub_skill:
        where_clauses.append("LOWER(lm.sub_skill) LIKE %s")
        params.append(f"%{search_sub_skill}%")
        
    # NEW: Filter by author
    if search_author:
        where_clauses.append("LOWER(lm.author) LIKE %s")
        params.append(f"%{search_author}%")

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " GROUP BY wm.email, lm.skill_type, lm.sub_skill"

    if search_progress:
        try:
            float_progress = float(search_progress)
            query += " HAVING progress_percentage = %s"
            params.append(float_progress)
        except ValueError:
            # Error handling for non-numeric progress input
            cursor.close()
            conn.close()
            return render_template('admin.html',
                                   materials=get_materials(),
                                   progress_users=[],
                                   search_email=search_email,
                                   search_skill=search_skill,
                                   search_sub_skill=search_sub_skill,
                                   search_progress=search_progress,
                                   search_author=search_author) # Pass new param back

    cursor.execute(query, params)
    progress_users = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin.html',
                           materials=get_materials(),
                           progress_users=progress_users,
                           search_email=search_email,
                           search_skill=search_skill,
                           search_sub_skill=search_sub_skill,
                           search_progress=search_progress,
                           search_author=search_author) # Pass new param back


@admin_bp.route('/admin/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email').lower()
        password = request.form.get('password')

        if email == 'rathika@gmail.com' and password == '123':
            session['admin_email'] = email

            session['role'] = 'admin'
            session['admin_email'] = email
            return redirect(url_for('admin.admin'))
        else:
            return render_template('admin_login.html', error="Invalid admin credentials")
    
    return render_template('admin_login.html')

from app import mail, scheduler 
from datetime import datetime
@app.route('/quiz/<int:material_id>')
def show_quiz(material_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM quiz_questions WHERE material_id = %s", (material_id,))
    questions = cursor.fetchall()
    conn.close()
    return render_template('quiz.html', questions=questions, material_id=material_id)
@app.route('/submit_quiz/<int:material_id>', methods=['POST'])
def submit_quiz(material_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM quiz_questions WHERE material_id = %s", (material_id,))
    questions = cursor.fetchall()

    score = 0
    for q in questions:
        user_answer = request.form.get(f'question_{q["id"]}')
        if user_answer and user_answer == q['correct_option']:
            score += 1

    status = 'passed' if score > 12 else 'failed'
    cursor.execute("""
        INSERT INTO quiz_attempts (email, material_id, score, status, attempt_date)
        VALUES (%s, %s, %s, %s, NOW())
    """, (session['email'], material_id, score, status))
    conn.commit()
    conn.close()

    if status == 'passed':
        flash(f'✅ You passed the quiz! Score: {score}/30. You can now generate your certificate.', 'success')
    else:
        flash(f'❌ You scored {score}/30. Please rewatch the video and try again.', 'danger')

    return redirect(url_for('dashboard'))

    return redirect(url_for('dashboard'))
@app.route('/logout')
def logout():
    login_time = session.get('login_time')
    email = session.get('email')
    
    if login_time and email:
        logout_time = datetime.now()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO login_sessions (email, login_time, logout_time)
            VALUES (%s, %s, %s)
        """, (email, login_time, logout_time))
        conn.commit()
        conn.close()
    
    session.clear()
    return redirect(url_for('home_page'))

def get_db_connection():
    return mysql.connector.connect(**db_config)
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'mp4', 'pdf'}
from moviepy.editor import VideoFileClip  # Add this at the top
# In your database setup (after get_db connection)
# Add these tables once manually (or via migration)
def init_new_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create quiz_questions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            material_id INT NOT NULL,
            question TEXT NOT NULL,
            option_a VARCHAR(255) NOT NULL,
            option_b VARCHAR(255) NOT NULL,
            option_c VARCHAR(255) NOT NULL,
            option_d VARCHAR(255) NOT NULL,
            correct_option CHAR(1) NOT NULL,
            FOREIGN KEY (material_id) REFERENCES learning_material(id)
        )
    """)

    # Create quiz_attempts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            material_id INT NOT NULL,
            score INT NOT NULL,
            status VARCHAR(10) NOT NULL,
            attempt_date DATETIME NOT NULL,
            FOREIGN KEY (material_id) REFERENCES learning_material(id),
            FOREIGN KEY (email) REFERENCES trainee_skills(email)
        )
    """)

    # Add author_name column to learning_material if not exists
    cursor.execute("""
        ALTER TABLE learning_material
        ADD COLUMN IF NOT EXISTS author_name VARCHAR(100) DEFAULT 'Unknown'
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Tables quiz_questions, quiz_attempts, and learning_material.author_name created or updated.")

def init_new_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Add author_name column to learning_materials if not exists
    cursor.execute("""
        ALTER TABLE learning_materials
        ADD COLUMN author_name VARCHAR(100) DEFAULT 'Unknown'
    """)

    # Create quiz_questions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            material_id INT,
            question TEXT,
            option_a VARCHAR(255),
            option_b VARCHAR(255),
            option_c VARCHAR(255),
            option_d VARCHAR(255),
            correct_option CHAR(1),
            FOREIGN KEY(material_id) REFERENCES learning_materials(id)
        )
    """)

    # Create quiz_attempts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(100),
            material_id INT,
            score INT,
            status VARCHAR(10),
            attempt_date DATETIME,
            FOREIGN KEY(material_id) REFERENCES learning_materials(id)
        )
    """)

    # Add quiz_score column to certificates table
    cursor.execute("""
        ALTER TABLE certificates
        ADD COLUMN quiz_score INT DEFAULT 0
    """)

    conn.commit()
    conn.close()
def get_weekly_progress(email):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                DATE(date_added) AS day,
                SUM(hours_spent) AS hours
            FROM skill_s
            WHERE user_email = %s
              AND date_added >= CURDATE() - INTERVAL 6 DAY
            GROUP BY DATE(date_added)
            ORDER BY DATE(date_added)
        """, (email,))

        rows = cursor.fetchall()
        conn.close()
        progress = [
            {
                'day': row['day'].strftime('%Y-%m-%d'),
                'hours': row['hours']
            } for row in rows
        ]
        return progress

    except mysql.connector.Error as e:
        print(f"Database error in get_weekly_progress(): {str(e)}")
        return []
    except Exception as e:
        print(f"Unexpected error in get_weekly_progress(): {str(e)}")
        return []
from flask import request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os
from moviepy.editor import VideoFileClip
@app.route('/upload_material', methods=['POST'])
def upload_material():
    title = request.form.get('title', '').strip()
    skill_type = request.form.get('skill_type', '').strip()
    sub_skill = request.form.get('sub_skill', '').strip()
    author_name = request.form.get('author_name', '').strip()  # 🆕 NEW FIELD

    # Basic validations
    if not title or not skill_type or not sub_skill or not author_name:
        flash("⚠ All fields (including Author Name) are required.", "danger")
        return redirect(url_for('admin.admin'))

    if sub_skill not in VALID_SUBSKILLS.get(skill_type, []):
        flash(f"❌ Invalid sub-skill '{sub_skill}' for skill type '{skill_type}'.", "danger")
        return redirect(url_for('admin.admin'))

    if 'material_file' not in request.files:
        flash("No file part in the request.", "danger")
        return redirect(url_for('admin.admin'))

    file = request.files['material_file']
    if file.filename == '':
        flash("No selected file.", "danger")
        return redirect(url_for('admin.admin'))

    if not allowed_file(file.filename):
        flash("Only .mp4 and .pdf files are allowed.", "danger")
        return redirect(url_for('admin.admin'))

    # Save the uploaded file
    filename = secure_filename(file.filename)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # Determine file type and video duration
    filetype = filename.rsplit('.', 1)[1].lower()
    duration = 0.0
    if filetype == 'mp4':
        try:
            clip = VideoFileClip(filepath)
            duration = round(clip.duration / 3600, 2)
            clip.reader.close()
            if clip.audio:
                clip.audio.reader.close_proc()
        except Exception as e:
            print(f"[ERROR] Failed to extract video duration: {e}")
            flash("Could not read video duration. Ensure ffmpeg is installed.", "danger")
            return redirect(url_for('admin.admin'))

    # Insert data into the database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO learning_material 
            (title, skill_type, sub_skill, author_name, filename, filetype, duration)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (title, skill_type, sub_skill, author_name, filename, filetype, duration))
        conn.commit()
        cursor.close()
        conn.close()
        flash("✅ Material uploaded successfully with author name!", "success")

    except mysql.connector.Error as e:
        print(f"[DB ERROR] {e}")
        flash(f"❌ Database error: {e}", "danger")

    return redirect(url_for('admin.admin'))

@app.route('/')
def home_page():
    return render_template('home.html')

@app.route('/about')
def about_page():
    return render_template("about.html")

@app.route('/skills.html')
def skills_page():
    return render_template("skill.html")

@app.route('/learn')
def learn_page():
    return render_template('learn.html')

@app.route('/terms')
def terms_page():
    return render_template('terms.html')

@app.route('/privacy')
def privacy_page():
    return render_template('privacy.html')

@app.route('/contact')
def contact_page():
    return render_template('contact.html')

@app.route('/trainees')
def trainees_page():
    return render_template('trainees.html')

@app.route('/soft')
def soft_page():
    return render_template('soft.html')

@app.route('/technical')
def technical_page():
    return render_template('technical.html')

@app.route('/professional')
def professional_page():
    return render_template('professional.html')
@app.route('/generate_certificate_download')
def generate_certificate_download():
    email = request.args.get('email')
    skill = request.args.get('skill')
    material_id = request.args.get('material_id')

    if not email or not skill or not material_id:
        return "Invalid request: missing email, skill, or material ID", 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT score FROM quiz_attempts
        WHERE email = %s AND material_id = %s
        ORDER BY attempt_date DESC LIMIT 1
    """, (email, material_id))
    quiz_result = cursor.fetchone()
    conn.close()

    if not quiz_result or quiz_result['score'] <= 12:
        return "❌ You must pass the quiz with a score greater than 12/30 to download the certificate.", 403

    quiz_score = quiz_result['score']
    cert_path = generate_certificate(email, skill, quiz_score)

    if cert_path is None:
        return "Certificate generation failed. Please ensure the template exists.", 500

    filename = os.path.basename(cert_path)
    return redirect(url_for('static', filename=f'generated_certificates/{filename}'))

def generate_certificate(email, skill_name, quiz_score):
    """Generate the certificate with trainee name, skill, date, and quiz score."""
    from PIL import Image, ImageDraw, ImageFont
    from datetime import datetime

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT trainee_name FROM trainee_skills WHERE email = %s", (email,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            print("❌ No trainee name found for this email.")
            return None

        trainee_name = result[0]
    except Exception as e:
        print("❌ Database error:", e)
        return None

    template_path = os.path.join(app.root_path, 'static', 'certificate_template.jpg')
    output_dir = os.path.join(app.root_path, 'static', 'generated_certificates')
    os.makedirs(output_dir, exist_ok=True)

    try:
        image = Image.open(template_path)
        draw = ImageDraw.Draw(image)

        try:
            name_font = ImageFont.truetype("arialbd.ttf", 60)
            skill_font = ImageFont.truetype("arial.ttf", 40)
            date_font = ImageFont.truetype("ariali.ttf", 30)
        except Exception as font_err:
            print("⚠ Font load failed, using default fonts.", font_err)
            name_font = ImageFont.load_default()
            skill_font = ImageFont.load_default()
            date_font = ImageFont.load_default()

        def center_text(text, y, font):
            bbox = draw.textbbox((0, 0), text, font=font)
            x = (image.width - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), text, fill="white", font=font)

        center_text(trainee_name.upper(), 370, name_font)
        center_text(f"For completing {skill_name}", 440, skill_font)
        center_text(f"Quiz Score: {quiz_score}/30", 490, skill_font)
        center_text(f"Date: {datetime.now().strftime('%Y-%m-%d')}", 540, date_font)

        safe_email = email.replace('@', '_').replace('.', '_')
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{safe_email}_{skill_name.replace(' ', '_')}_{timestamp}.png"
        filepath = os.path.join(output_dir, filename)

        image.save(filepath)
        print("✅ Certificate generated at:", filepath)
        return filepath

    except Exception as e:
        print("❌ Image error:", e)
        return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        if not email or not password:
            return render_template('login.html', error="Please enter both email and password.")

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT * FROM trainee_skills WHERE email = %s", (email,))
            user = cursor.fetchone()
            conn.close()

            if not user:
                return render_template('login.html', error="Email not found. Please register first.")

            if not check_password_hash(user['password'], password):
                return render_template('login.html', error="Incorrect password.")
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['user_type'] = 'trainee'
            session['login_time'] = datetime.now()


            if user['email'] == 'rathika@gmail.com':
                session['role'] = 'admin'
                session['admin_email'] = user['email']
                return redirect(url_for('admin.admin'))

            return redirect(url_for('dashboard'))

        except mysql.connector.Error as db_err:
            print(f"Database error during login: {db_err}")
            return render_template('login.html', error="Database error. Try again later.")
        except Exception as e:
            print(f"Unexpected login error: {e}")
            return render_template('login.html', error="An unexpected error occurred.")

    return render_template('login.html')
@admin_bp.route('/admin')
@admin_required
def admin():
    materials = get_materials()
    return render_template('admin.html', materials=materials)
@app.route('/trainee_skills', methods=['POST'])
def trainee_skills():
    try:
        trainee_name = request.form.get('trainee_name')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone')

        if not all([trainee_name, email, password, phone]):
            flash("Please fill all fields.", "danger")
            return redirect(url_for('trainees_page'))

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO trainee_skills (trainee_name, password, phone, email)
            VALUES (%s, %s, %s, %s)
        """, (trainee_name, hashed_password, phone, email))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Trainee registered successfully!", "success")
        return redirect(url_for('login'))

    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        flash("Database error during registration.", "danger")
        return redirect(url_for('trainees_page'))
@app.route('/dashboard')
@login_required
def dashboard():
    email = session['email']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    has_quiz = None
    # 1. Get progress for EVERY material the user has started (or available material)
    cursor.execute("""
        SELECT lm.id AS material_id, lm.skill_type, lm.sub_skill, lm.duration,
               COALESCE(wm.watch_percentage, 0) AS watched_percentage,
               (COALESCE(wm.watch_percentage, 0) / 100) * lm.duration AS watched_duration
        FROM learning_material lm
        LEFT JOIN watched_materials wm ON lm.id = wm.material_id AND wm.email = %s
    """, (email,))
    material_progress = cursor.fetchall()
    
    # 2. Structure progress data by Sub-Skill
    sub_skill_progress = {
        'Technical': {},
        'Professional': {},
        'Soft Skill': {}
    }
    
    # Used to calculate overall category progress
    skill_category_totals = {
        'Technical': {'total_duration': 0.0, 'watched_duration': 0.0},
        'Professional': {'total_duration': 0.0, 'watched_duration': 0.0},
        'Soft Skill': {'total_duration': 0.0, 'watched_duration': 0.0}
    }
    
    total_watched_overall = 0.0
    total_possible_overall = 0.0

    for row in material_progress:
        skill_type = row['skill_type']
        sub_skill = row['sub_skill']
        material_id = row['material_id']
        watched_duration = row['watched_duration']
        total_duration = row['duration']

        # Skip if material has no duration (e.g., PDF with 0.0 hours)
        if total_duration == 0.0:
            continue

        # Aggregate for overall category progress
        if skill_type in skill_category_totals:
            skill_category_totals[skill_type]['total_duration'] += total_duration
            skill_category_totals[skill_type]['watched_duration'] += watched_duration
            
        total_watched_overall += watched_duration
        total_possible_overall += total_duration

        # Calculate percentage for THIS material
        percentage = min((watched_duration / total_duration) * 100, 100)

        # 3. Store the material data under its sub-skill
        # If there are multiple videos per sub-skill, we track them all here.
        if sub_skill not in sub_skill_progress[skill_type]:
            sub_skill_progress[skill_type][sub_skill] = {
                'total_duration': 0.0,
                'watched_duration': 0.0,
                'materials': [], # List to hold individual material details
                'quiz_material': None # To store the material_id that unlocks the quiz
            }

        # Check for quiz completion (This is checked per material)
        quiz_passed = False
        if percentage >= 99.99:
            cursor.execute("""
                SELECT score FROM quiz_attempts
                WHERE email = %s AND material_id = %s
                ORDER BY attempt_date DESC LIMIT 1
            """, (email, material_id))
            quiz_result = cursor.fetchone()
            
            # Check if there is a quiz for this material at all
            cursor.execute("SELECT id FROM quiz_questions WHERE material_id = %s LIMIT 1", (material_id,))
            has_quiz = cursor.fetchone()
            
            if has_quiz:
                # If a quiz exists and the video is complete, this is the one we link to
                sub_skill_progress[skill_type][sub_skill]['quiz_material'] = {
                    'material_id': material_id,
                    'is_complete': True
                }
                if quiz_result and quiz_result['score'] > 12: # Using the original pass score logic
                    quiz_passed = True

        sub_skill_progress[skill_type][sub_skill]['materials'].append({
            'percentage': percentage,
            'material_id': material_id,
            'quiz_passed': quiz_passed,
            'has_quiz': has_quiz is not None
        })
        
        sub_skill_progress[skill_type][sub_skill]['total_duration'] += total_duration
        sub_skill_progress[skill_type][sub_skill]['watched_duration'] += watched_duration
    
    # 4. Finalize Sub-Skill and Category Percentages
    progress_percentages = {'Technical': 0.0, 'Professional': 0.0, 'Soft Skill': 0.0}
    final_sub_skill_progress = {}
    
    for skill_type in ['Technical', 'Professional', 'Soft Skill']:
        final_sub_skill_progress[skill_type] = {}
        
        # Calculate Category Percentage
        cat_total = skill_category_totals[skill_type]['total_duration']
        cat_watched = skill_category_totals[skill_type]['watched_duration']
        if cat_total > 0:
            progress_percentages[skill_type] = min((cat_watched / cat_total) * 100, 100)
            
        # Finalize Sub-Skill Data
        for sub_skill, data in sub_skill_progress[skill_type].items():
            sub_total = data['total_duration']
            sub_watched = data['watched_duration']
            sub_percentage = 0.0
            
            if sub_total > 0:
                sub_percentage = min((sub_watched / sub_total) * 100, 100)

            # Determine quiz status: True if ANY quiz material for this sub-skill is passed
            overall_quiz_passed = any(m['quiz_passed'] for m in data['materials'])
            
            # Find the ID for the quiz link:
            # - If a specific quiz_material was marked (single video completion), use its ID.
            # - Otherwise, use the ID of the first material that has a quiz defined, 
            #   or just the ID of the first material listed.
            quiz_id_to_use = None
            if data['quiz_material']:
                quiz_id_to_use = data['quiz_material']['material_id']
            elif data['materials']:
                 # Fallback: Find the ID of the first material that HAS a quiz defined
                for m in data['materials']:
                    if m['has_quiz']:
                        quiz_id_to_use = m['material_id']
                        break
                if quiz_id_to_use is None:
                    # Final fallback: Just use the ID of the first material
                    quiz_id_to_use = data['materials'][0]['material_id']

            final_sub_skill_progress[skill_type][sub_skill] = {
                'percentage': sub_percentage,
                'material_id': quiz_id_to_use, # The ID used for the quiz link
                'quiz_passed': overall_quiz_passed,
                'is_complete_for_quiz': sub_percentage >= 99.99 # Use the aggregate percentage for display logic
            }

    overall_percentage = (total_watched_overall / total_possible_overall * 100) if total_possible_overall > 0 else 0

    # 5. Prepare data for the Chart
    radar_data = {'labels': [], 'datasets': []}
    labels = []
    total_durations = []
    watched_durations = []
    
    for skill_type, sub_skills in final_sub_skill_progress.items():
        for sub_skill, data in sub_skills.items():
            labels.append(f"{skill_type} - {sub_skill}")
            total_durations.append(sub_skill_progress[skill_type][sub_skill]['total_duration'])
            watched_durations.append(sub_skill_progress[skill_type][sub_skill]['watched_duration'])


    certificates_dir = os.path.join(app.root_path, 'static', 'generated_certificates')
    certificates = []
    if os.path.exists(certificates_dir):
        for filename in os.listdir(certificates_dir):
            if filename.endswith('.png'):
                # Heuristic parsing of filename for display (less reliable)
                parts = filename.replace('.png', '').split('_')
                if len(parts) >= 3:
                    # Reconstruct email (first part) and skill (parts 1 up to last part - 1 for timestamp)
                    cert_email = parts[0]
                    cert_skill = ' '.join(parts[1:-1]) 
                    
                    if cert_email == email.replace('@', '_').replace('.', '_'):
                        certificates.append({'email': email, 'skill': cert_skill.replace('_', ' '), 'filename': filename})


    conn.close()

    return render_template('dashboard.html',
                           progress_percentages=progress_percentages,
                           sub_skill_progress=final_sub_skill_progress, # Use the finalized structure
                           overall_percentage=round(overall_percentage, 2),
                           radar_data=radar_data,
                           labels=labels,
                           email=email,
                           certificates=certificates,
                           total_durations=total_durations,
                           watched_durations=watched_durations)
@app.route('/take_quiz/<sub_skill>')
@login_required
def take_quiz(sub_skill):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM learning_material WHERE sub_skill = %s LIMIT 1", (sub_skill,))
    material = cursor.fetchone()
    conn.close()
    
    if not material:
        flash("No quiz available for this sub-skill.", "danger")
        return redirect(url_for('dashboard'))
    
    return redirect(url_for('show_quiz', material_id=material['id']))

@app.route('/analytics')
@login_required
def analytics():
    email = session['email']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            lm.skill_type,
            SUM((wm.watch_percentage / 100) * lm.duration) AS total_hours
        FROM watched_materials wm
        JOIN learning_material lm ON wm.material_id = lm.id
        WHERE wm.email = %s
        GROUP BY lm.skill_type
    """, (email,))
    skill_summary = cursor.fetchall()
    cursor.execute("""
        SELECT DATE(watched_at) AS day,
               SUM((watch_percentage / 100) * duration) AS hours
        FROM watched_materials wm
        JOIN learning_material lm ON wm.material_id = lm.id
        WHERE wm.email = %s AND watched_at >= CURDATE() - INTERVAL 6 DAY
        GROUP BY DATE(watched_at)
        ORDER BY DATE(watched_at)
    """, (email,))
    weekly_data = cursor.fetchall()
    cursor.execute("""
        SELECT 
            SUM(TIMESTAMPDIFF(SECOND, login_time, logout_time)) / 3600 AS login_hours
        FROM login_sessions
        WHERE email = %s
    """, (email,))
    login_hours = cursor.fetchone()['login_hours'] or 0
    cursor.execute("""
        SELECT lm.title AS sub_skill, 
               SUM((wm.watch_percentage / 100) * lm.duration) AS hours_logged, 
               MAX(wm.watched_at) AS submitted_at
        FROM watched_materials wm
        JOIN learning_material lm ON wm.material_id = lm.id
        WHERE wm.email = %s
        GROUP BY lm.title
        ORDER BY MAX(wm.watched_at) DESC
        LIMIT 5
    """, (email,))
    recent_activity = cursor.fetchall()

    conn.close()

    return render_template('analytics.html',
                           skill_summary=skill_summary,
                           weekly_data=weekly_data,
                           login_hours=round(login_hours, 2),
                           recent_activity=recent_activity,
                           email=email)
@app.route('/api/progress/video/<email>')
def api_progress_video(email):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                lm.skill_type, 
                wm.watch_percentage,
                lm.duration
            FROM watched_materials wm
            JOIN learning_material lm ON wm.material_id = lm.id
            WHERE wm.email = %s
        """, (email,))
        rows = cursor.fetchall()

        progress = {'Technical': 0, 'Soft': 0, 'Professional': 0}
        duration_total = {'Technical': 0, 'Soft': 0, 'Professional': 0}

        for row in rows:
            skill_type = row['skill_type']
            duration = row['duration'] or 0
            percent = row['watch_percentage'] or 0

            watched = (percent / 100) * duration
            progress[skill_type] += watched
            duration_total[skill_type] += duration
        graph_data = {}
        for skill in progress:
            total = duration_total[skill]
            graph_data[skill.lower()] = round((progress[skill] / total) * 100, 2) if total > 0 else 0

        return jsonify(graph_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/track_watch/<int:material_id>/<email>', methods=['POST'])
def track_watch(material_id, email):
    data = request.get_json()
    current_seconds = data.get('seconds', 0)

    if current_seconds <= 0:
        return jsonify({'status': 'ignored'})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT skill_type, sub_skill, duration FROM learning_material WHERE id = %s", (material_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        return jsonify({'error': 'Invalid material ID'}), 400

    skill_type = result['skill_type']
    sub_skill = result['sub_skill']
    duration_hours = result['duration'] or 0
    duration_seconds = duration_hours * 3600
    cursor.execute("""
        INSERT INTO watched_sessions (email, material_id, skill_type, watched_seconds)
        VALUES (%s, %s, %s, %s)
    """, (email, material_id, skill_type, current_seconds))
    cursor.execute("""
        SELECT SUM(watched_seconds) AS total_seconds
        FROM watched_sessions
        WHERE email = %s AND material_id = %s
    """, (email, material_id))
    total_seconds = cursor.fetchone()['total_seconds'] or 0
    watch_percentage = min((total_seconds / duration_seconds) * 100, 100)
    cursor.execute("""
    INSERT INTO watched_materials (email, material_id, skill_type, sub_skill, watch_percentage, watched_at)
    VALUES (%s, %s, %s, %s, %s, NOW())
    ON DUPLICATE KEY UPDATE
        sub_skill = VALUES(sub_skill),
        watch_percentage = VALUES(watch_percentage),
        watched_at = NOW()
""", (email, material_id, skill_type, sub_skill, watch_percentage))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'status': 'tracked', 'watch_percentage': round(watch_percentage, 2)})
def get_materials():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM learning_material")
    materials = cursor.fetchall()
    cursor.close()
    conn.close()
    return materials

import os
from flask import redirect, url_for, flash
from werkzeug.utils import secure_filename
@app.route('/delete_material/<int:material_id>', methods=['POST'])
def delete_material(material_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT filename FROM learning_material WHERE id = %s", (material_id,))
        material = cursor.fetchone()
        if material:
            filename = material['filename']
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))

            if os.path.exists(file_path):
                os.remove(file_path)

            cursor.execute("DELETE FROM learning_material WHERE id = %s", (material_id,))
            conn.commit()
            flash("Material deleted successfully!", "success")
        else:
            flash("Material not found.", "danger")

        cursor.close()
        conn.close()

    except Exception as e:
        print("Error deleting material:", e)
        flash("An error occurred while deleting the material.", "danger")

    return redirect(url_for('admin.admin'))  
@app.route('/set_goal', methods=['GET', 'POST'])
@login_required
def set_goal():
    email = session['email']
    try:
        with get_db_connection() as db:
            with db.cursor(dictionary=True) as cursor:
                if request.method == 'POST':
                    goal_title = request.form['title']
                    description = request.form['description']
                    target_date = request.form['target_date']
                    material_id = request.form.get('material_id')

                    if not all([goal_title, description, target_date, material_id]):
                        flash("All fields are required.", "danger")
                        return redirect(url_for('set_goal'))

                    try:
                        cursor.execute("""
                            INSERT INTO goals (title, description, target_date, created_at, email, status, material_id)
                            VALUES (%s, %s, %s, NOW(), %s, 'Pending', %s)
                        """, (goal_title, description, target_date, email, material_id))
                        db.commit()
                        flash("Goal set successfully!", "success")
                    except mysql.connector.Error as e:
                        db.rollback()
                        flash(f"Database error while setting goal: {e}", "danger")
                        print(f"Error inserting goal: {e}")
                cursor.execute("SELECT id, title, duration * 60 AS duration FROM learning_material WHERE filetype = 'mp4'")
                videos = cursor.fetchall()
                print(f"Fetched videos: {videos}")
                cursor.execute("""
                    SELECT g.*, lm.title AS material_title, lm.duration * 60 AS video_duration,
                           SUM((wm.watch_percentage / 100) * lm.duration * 60) AS watched_duration
                    FROM goals g
                    LEFT JOIN learning_material lm ON g.material_id = lm.id
                    LEFT JOIN watched_materials wm ON g.material_id = wm.material_id AND g.email = wm.email
                    WHERE g.email = %s
                    GROUP BY g.id, lm.id
                    ORDER BY g.created_at DESC
                """, (email,))
                goals = cursor.fetchall()
                print(f"Fetched goals: {goals}") 

        return render_template('set_goal.html', videos=videos, email=email, goals=goals)

    except mysql.connector.Error as e:
        print(f"Database connection error: {e}")
        flash("Failed to load videos due to a database error.", "danger")
        return render_template('set_goal.html', videos=[], email=email, goals=[])
    except Exception as e:
        print(f"Unexpected error: {e}")
        flash("An unexpected error occurred.", "danger")
        return render_template('set_goal.html', videos=[], email=email, goals=[])
def send_goal_reminders():
    try:
        with get_db_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                today = datetime.now().strftime('%Y-%m-%d')
                cursor.execute("""
                    SELECT g.title, g.target_date, g.email, lm.duration, wm.watch_percentage 
                    FROM goals g
                    JOIN learning_material lm ON g.material_id = lm.id
                    LEFT JOIN watched_materials wm ON g.material_id = wm.material_id AND g.email = wm.email
                    WHERE g.status = 'Pending'
                """)
                goals = cursor.fetchall()
                print(f"[send_goal_reminders] Goals for reminders: {goals}")

                for goal in goals:
                    target_date = goal['target_date'].strftime('%Y-%m-%d') if isinstance(goal['target_date'], datetime) else goal['target_date']
                    if target_date < today:
                        print(f"[send_goal_reminders] Skipping goal '{goal['title']}' (past due: {target_date})")
                        continue
                    watched = goal['watch_percentage'] or 0
                    if watched >= 100:
                        print(f"[send_goal_reminders] Skipping goal '{goal['title']}' (already completed: {watched}%)")
                        continue
                    print(f"[send_goal_reminders] Sending reminder for goal '{goal['title']}' to {goal['email']}")
                    msg = Message(
                        subject="Reminder: Goal Pending",
                        sender=app.config['MAIL_USERNAME'],
                        recipients=[goal['email']],
                        body=f"Reminder: You have not completed your goal '{goal['title']}'. Deadline: {target_date}."
                    )
                    mail.send(msg)
                    print(f"[send_goal_reminders] Reminder sent to {goal['email']} for goal: {goal['title']}")
    except mysql.connector.Error as e:
        print(f"[send_goal_reminders] Database error: {e}")
    except Exception as e:
        print(f"[send_goal_reminders] Error sending reminder: {e}")
def update_goal_statuses():
    try:
        with get_db_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                today = datetime.now().strftime('%Y-%m-%d')
                cursor.execute("""
                    SELECT g.id, g.title, g.email, lm.duration, wm.watch_percentage 
                    FROM goals g
                    JOIN learning_material lm ON g.material_id = lm.id
                    LEFT JOIN watched_materials wm ON g.material_id = wm.material_id AND g.email = wm.email
                    WHERE g.status = 'Pending' AND g.target_date < %s
                """, (today,))
                goals = cursor.fetchall()
                print(f"[update_goal_statuses] Goals for status update: {goals}")

                for goal in goals:
                    watched = goal['watch_percentage'] or 0
                    if watched < 100:
                        cursor.execute("UPDATE goals SET status = 'Failed' WHERE id = %s", (goal['id'],))
                        print(f"[update_goal_statuses] Updating goal '{goal['title']}' to Failed for {goal['email']}")
                        msg = Message(
                            subject="Goal Failed",
                            sender=app.config['MAIL_USERNAME'],
                            recipients=[goal['email']],
                            body=f"Unfortunately, you failed to achieve the goal: '{goal['title']}' by the deadline."
                        )
                        mail.send(msg)
                        print(f"[update_goal_statuses] Failure notification sent to {goal['email']} for goal: {goal['title']}")
                conn.commit()
    except mysql.connector.Error as e:
        print(f"[update_goal_statuses] Database error: {e}")
    except Exception as e:
        print(f"[update_goal_statuses] Error updating goal status: {e}")
scheduler.add_job(
    func=send_goal_reminders,
    trigger=CronTrigger(hour=9, minute=0),
    id='daily_reminder',
    replace_existing=True
)
scheduler.add_job(
    func=update_goal_statuses,
    trigger=CronTrigger(hour=0, minute=0),
    id='deadline_checker',
    replace_existing=True
)
@app.route('/admin/manage_quiz/<int:material_id>', methods=['GET', 'POST'])
@admin_required
def manage_quiz(material_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Fetch material details
        cursor.execute("SELECT id, title, sub_skill, author_name FROM learning_material WHERE id = %s", (material_id,))
        material = cursor.fetchone()

        if not material:
            flash("Material not found.", "danger")
            return redirect(url_for('dashboard')) 
        
        # 2. Handle Form Submission (POST) - Overwrites ALL questions
        if request.method == 'POST':
            questions_to_save = []
            
            # Loop up to 30 potential questions (based on HTML design)
            for i in range(1, 31):
                question_text = request.form.get(f'question_{i}')
                
                # Check for question text and non-empty content
                if question_text and question_text.strip(): 
                    q_data = {
                        'material_id': material_id,
                        'question': question_text.strip(),
                        'option_a': request.form.get(f'option_a_{i}', '').strip(),
                        'option_b': request.form.get(f'option_b_{i}', '').strip(),
                        'option_c': request.form.get(f'option_c_{i}', '').strip(),
                        'option_d': request.form.get(f'option_d_{i}', '').strip(),
                        'correct_option': request.form.get(f'correct_option_{i}', '').strip().upper()
                    }
                    
                    # Ensure all required fields for this question are present
                    required_fields = ['question', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_option']
                    if all(q_data[key] for key in required_fields):
                        questions_to_save.append(q_data)
                    else:
                        flash(f"Question {i} was incomplete and skipped.", "warning")

            # CRITICAL STEP: Delete all previous questions for this material
            cursor.execute("DELETE FROM quiz_questions WHERE material_id = %s", (material_id,))
            
            # Insert the newly submitted questions (which includes newly added ones and excludes client-side removed ones)
            if questions_to_save:
                insert_data = [
                    (q['material_id'], q['question'], q['option_a'], q['option_b'], q['option_c'], q['option_d'], q['correct_option'])
                    for q in questions_to_save
                ]
                insert_query = """
                    INSERT INTO quiz_questions (material_id, question, option_a, option_b, option_c, option_d, correct_option)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.executemany(insert_query, insert_data)
                flash(f"Successfully saved {len(questions_to_save)} quiz questions.", "success")
            else:
                flash("All existing quiz questions were deleted, and no new questions were saved.", "info")

            conn.commit()
            # Redirect to GET to see the updated list (the standard refresh)
            return redirect(url_for('manage_quiz', material_id=material_id))

        # 3. Handle Initial Page Load (GET)
        cursor.execute("SELECT * FROM quiz_questions WHERE material_id = %s ORDER BY id", (material_id,))
        existing_questions = cursor.fetchall()
        
        return render_template('manage_quiz.html', 
                               material=material, 
                               material_id=material_id, 
                               existing_questions=existing_questions)

    except NotImplementedError:
        flash("Database connection is not configured.", "danger")
        return redirect(url_for('dashboard'))
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error managing quiz: {e}")
        flash("An unexpected error occurred while processing the quiz.", "danger")
        return redirect(url_for('dashboard'))
    finally:
        if conn:
            conn.close()
@app.route('/update_goal/<int:goal_id>', methods=['POST'])
@login_required
def update_goal(goal_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        new_status = request.form.get('status')
        valid_statuses = ['Pending', 'Achieved', 'Failed']
        if new_status not in valid_statuses:
            flash("Invalid status selected.", "danger")
            return redirect(url_for('set_goal'))
        cursor.execute("""
            UPDATE goals
            SET status = %s
            WHERE id = %s AND email = %s
        """, (new_status, goal_id, session['email']))
        if cursor.rowcount == 0:
            flash("Goal not found or you do not have permission to update it.", "danger")
        else:
            conn.commit()
            flash("Goal status updated successfully!", "success")

        cursor.close()
        conn.close()

        return redirect(url_for('set_goal'))

    except mysql.connector.Error as e:
        print(f"Database error: {e}")
        flash("Database error occurred while updating goal.", "danger")
        return redirect(url_for('set_goal'))
    except Exception as e:
        print(f"Unexpected error: {e}")
        flash("An unexpected error occurred.", "danger")
        return redirect(url_for('set_goal'))

if __name__ == '__main__':
    app.register_blueprint(admin_bp)
    scheduler.add_job(
        func=update_goal_statuses,
        trigger=IntervalTrigger(hours=1),
        id='update_goal_status_job',
        replace_existing=True
    )
    app.run(debug=True)

