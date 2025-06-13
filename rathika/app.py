from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import mysql.connector
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message


app = Flask(__name__)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'sathappanrathiga@gmail.com'      # Your email
app.config['MAIL_PASSWORD'] = 'qdnk eguo jgdk dgpe'         # App password (not your main password)
mail = Mail(app)



app.secret_key = "your_secret_key_here"

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Digidara1000',
    'database': 'login'
}
conn = mysql.connector.connect(
    host="localhost",
    user="root",        # Change this
    password="Digidara1000",# Change this
    database="login"       # Make sure this database exists
)
cursor = conn.cursor()
@app.route("/set_goal", methods=["GET", "POST"])
def set_goal():
    email = request.args.get("email")
    if not email:
        return "No email specified.", 400

    if request.method == "POST":
        title = request.form["goal_title"]
        area = request.form["skill_area"]
        target_date = request.form["target_date"]
        description = request.form["goal_description"]
        created_at = datetime.now()

        query = "INSERT INTO goals (title, skill_area, target_date, description, created_at, email) VALUES (%s, %s, %s, %s, %s, %s)"
        values = (title, area, target_date, description, created_at, email)
        cursor.execute(query, values)
        conn.commit()
          # Send notification email
        msg = Message(
            subject="Your Goal Has Been Set!",
            sender=app.config['MAIL_USERNAME'],
            recipients=[email],
            body=f"Hi,\n\nYour goal '{title}' in '{area}' has been set for {target_date}.\n\nDescription: {description}\n\nThank you for using Skill Development Tracker!"
        )
        mail.send(msg)

    cursor.execute("SELECT * FROM goals WHERE email=%s ORDER BY target_date ASC", (email,))
    goals = cursor.fetchall()
    return render_template("set_goal.html", goals=goals, email=email)
@app.route("/dash")
def dash():
    cursor.execute("SELECT * FROM goals ORDER BY target_date ASC")
    goals = cursor.fetchall()
    return render_template("dash.html", goals=goals)


def get_db_connection():
    return mysql.connector.connect(**db_config)

def ensure_skills_table():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS skills
                     (id INTEGER PRIMARY KEY AUTO_INCREMENT,
                      user_id INTEGER,
                      skill_type VARCHAR(50),
                      sub_skill VARCHAR(100),
                      progress INTEGER,
                      hours FLOAT,
                      date_added DATE)''')
        conn.commit()
        conn.close()
    except mysql.connector.Error as e:
        print(f"Error creating skills table: {e}")

# Helper function to get weekly progress data
def get_weekly_progress(email):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        four_weeks_ago = (datetime.now() - timedelta(weeks=4)).strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT skill_type, progress, date_added
            FROM skills
            WHERE email = %s AND date_added >= %s
        ''', (email, four_weeks_ago))
        rows = cursor.fetchall()
        conn.close()

        weeks = [(datetime.now() - timedelta(weeks=i)).strftime('Week %W') for i in range(3, -1, -1)]
        technical = [0] * 4
        soft = [0] * 4
        professional = [0] * 4

        for skill_type, progress, date_added in rows:
            # Convert date_added if it's datetime.date or datetime.datetime
            if isinstance(date_added, (datetime,)):
                date_added = date_added.date()
            week_index = min(3, max(0, (datetime.now().date() - date_added).days // 7))
            skill_type_lower = skill_type.lower()
            if skill_type_lower == 'technical':
                technical[week_index] = max(technical[week_index], progress)
            elif skill_type_lower == 'soft':
                soft[week_index] = max(soft[week_index], progress)
            elif skill_type_lower == 'professional':
                professional[week_index] = max(professional[week_index], progress)

        return {
            'weeks': weeks,
            'technical': technical,
            'soft': soft,
            'professional': professional
        }
    except Exception as e:
        print(f"Error in get_weekly_progress: {e}")
        return None

# Routes

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

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/contact')
def contact_page():
    return render_template('contact.html')

@app.route('/student')
def student_page():
    return render_template('student.html')

@app.route('/employee')
def employee_page():
    return render_template('employee.html')

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

# Login POST
@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')

    tables = ['student_skills', 'employee_skills', 'trainee_skills']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        for table in tables:
            print(f"Checking table: {table}")
            query = f"SELECT * FROM {table} WHERE email = %s"
            cursor.execute(query, (email,))
            user = cursor.fetchone()
            print(f"User found: {user}")

   
        if user and check_password_hash(user['password'], password):
                 # Use the actual primary key ID if available, else fallback
                user_id = user.get('id')
                if not user_id:
                    # If ID field doesn't exist, fallback to using email (not recommended)
                    conn.close()
                    return "User ID missing in database, please check schema.", 500

                session['user_id'] = user_id     # Correctly store numeric ID
                session['email'] = user['email'] # Store email separately
                session['user_type'] = table
                conn.close()
                return redirect(url_for('track'))

        conn.close()
        return "Invalid email or password", 401
    except Exception as e:
        print(f"Login error: {e}")
        return "Internal server error", 500


@app.route('/trainee_skill', methods=['POST'])
def trainee_skill():
    email = request.form['email']
    password = request.form['password']
    hashed_password = generate_password_hash(password)
    institute = request.form['institute']
    skill_name = request.form['skill_name']
    skill_type = request.form['skill_type']
    trainee_name = request.form['trainee_name']
    level = request.form['level']
    source = request.form['source']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM trainee_skills WHERE email = %s", (email,))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return "Error: This email has already been registered.", 400

        cursor.execute("""
            INSERT INTO trainee_skills 
            (trainee_name, email, institute, skill_name, skill_type, level, source, password)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (trainee_name, email, institute, skill_name, skill_type, level, source, hashed_password))
        conn.commit()
        conn.close()
        session['email'] = email
        # If you have a user_id, set session['user_id'] as well

        return redirect(url_for('track'))  # <-- Redirect to track page after registration

        return "registered successfully", 200
    except Exception as e:
        print(f"trainee_skill error: {e}")
        return "Internal server error", 500


@app.route('/track', methods=['GET', 'POST'])
def track():
    user_id = session.get('user_id', 1)
    if request.method == 'POST':
        email = session['email']
        date_added = datetime.now().strftime('%Y-%m-%d')
        errors = []

        try:
            # Find all skill indices present in the form
            skill_indices = []
            for key in request.form.keys():
                if key.startswith('skills[') and key.endswith('][skill_type]'):
                    idx = key.split('[')[1].split(']')[0]
                    if idx.isdigit():
                        skill_indices.append(int(idx))
            skill_indices = sorted(set(skill_indices))

            conn = get_db_connection()
            c = conn.cursor()

            for i in skill_indices:
                skill_type = request.form.get(f'skills[{i}][skill_type]')
                sub_skill = request.form.get(f'skills[{i}][sub_skill]')
                progress = request.form.get(f'skills[{i}][progress]')
                hours = request.form.get(f'skills[{i}][hours]')

                if not all([skill_type, sub_skill, progress, hours]):
                    errors.append(f"Missing fields for skill entry {i+1}")
                    continue
                try:
                    progress = int(progress)
                    hours = float(hours)
                    if not (0 <= progress <= 100):
                        errors.append(f"Progress for {sub_skill} must be 0-100")
                        continue
                    if hours < 0:
                        errors.append(f"Hours for {sub_skill} cannot be negative")
                        continue
                except ValueError:
                    errors.append(f"Invalid progress or hours for {sub_skill}")
                    continue

                try:
                    c.execute('''INSERT INTO skills (user_id, skill_type, sub_skill, progress, hours, date_added, email)
                                 VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                              (user_id, skill_type, sub_skill, progress, hours, date_added, email))
                except mysql.connector.Error as e:
                    errors.append(f"Database error for {sub_skill}: {str(e)}")
                    continue
            conn.commit()
            conn.close()

            if errors:
                return render_template('track.html', user_id=user_id, error='; '.join(errors))
            return redirect(url_for('dashboard', user_id=user_id))
        except mysql.connector.Error as e:
            return render_template('track.html', user_id=user_id, error=f"Database error: {str(e)}")
        except Exception as e:
            return render_template('track.html', user_id=user_id, error=f"Error saving skills: {str(e)}")

    return render_template('track.html', user_id=user_id)

@app.route('/dashboard')
def dashboard():
    email = session.get('email') or request.args.get('email')
    if not email:
        return redirect(url_for('login_page'))  # Redirect to login if not logged in
 # Always use session user_id
    progress = get_weekly_progress(email)
    return render_template('dashboard.html', email=email, weekly_data=progress)
    # user_id = session.get('user_id', request.args.get('user_id', 1, type=int))
    # progress = get_weekly_progress(user_id)
    # return render_template('dashboard.html', user_id=user_id, weekly_data=progress)

@app.route('/api/progress/<email>')
def get_progress(email):
    try:
    
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''SELECT skill_type, MAX(progress)
                     FROM skills
                     WHERE email = %s
                     GROUP BY skill_type''', (email,))
        rows = c.fetchall()
        conn.close()

        progress_data = {'technical': 0, 'soft': 0, 'professional': 0}
        for skill_type, progress in rows:
            if skill_type.lower() == 'technical':
                progress_data['technical'] = progress
            elif skill_type.lower() == 'soft':
                progress_data['soft'] = progress
            elif skill_type.lower() == 'professional':
                progress_data['professional'] = progress

        weekly_data = get_weekly_progress(email)

        return jsonify({
            'progress_data': progress_data,
            'weekly_data': weekly_data
        })
    except mysql.connector.Error as e:
        return jsonify({'error': f"Database error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/activity/<email>')
def get_activity(email):
    try:

        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''SELECT sub_skill, hours, date_added
                     FROM skills
                     WHERE email = %s
                     ORDER BY date_added DESC
                     LIMIT 5''', (email,))
        rows = c.fetchall()
        conn.close()

        activities = [
            {
                'skill_name': row[0],
                'hours_logged': row[1],
                'last_updated': row[2].strftime('%Y-%m-%d') if row[2] else ''
            } for row in rows
        ]
        return jsonify(activities)
    except mysql.connector.Error as e:
        return jsonify({'error': f"Database error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    ensure_skills_table()
    app.run(debug=True)