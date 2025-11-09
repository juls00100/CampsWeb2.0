import pymysql
from flask import Flask, render_template, request, url_for, redirect, session, flash, g
import os
from functools import wraps
import json
from datetime import datetime

MYSQL_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '1234',
    'database': 'evaluation_system',
    'cursorclass': pymysql.cursors.DictCursor
}
SECRET_KEY = os.urandom(24)

app = Flask(__name__)
app.config.from_object(__name__)

def get_db():
    """Opens a new database connection if there is none yet for the current application context."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = pymysql.connect(**app.config['MYSQL_CONFIG'])
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Closes the database again at the end of the request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Initializes the database structure from schema.sql."""
    conn = pymysql.connect(
        host=app.config['MYSQL_CONFIG']['host'],
        user=app.config['MYSQL_CONFIG']['user'],
        password=app.config['MYSQL_CONFIG']['password']
    )
    
    with conn.cursor() as cursor:
        try:
            with open('schema.sql', 'r') as f:
                sql_script = f.read()
                # Split script by semicolon, filtering out empty strings
                statements = [s.strip() for s in sql_script.split(';') if s.strip()]
                for statement in statements:
                    cursor.execute(statement)
            conn.commit()
            print("Database initialized successfully.")
        except Exception as e:
            print(f"Error initializing database: {e}")
            conn.rollback()
        finally:
            conn.close()
def query_db(query, args=(), one=False):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(query, args)
    results = cursor.fetchall()
    db.commit() 
    return (results[0] if results else None) if one else results

def check_teachers_exist():
    """Checks if there is at least one teacher in the system."""
    return query_db("SELECT COUNT(*) AS count FROM tbl_teacher", one=True)['count'] > 0

def login_required(role='student'):
    """Decorator to check if a user is logged in with the specified role."""
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if role == 'student' and 'student_id' not in session:
                flash('You need to log in as a student to access this page.', 'danger')
                return redirect(url_for('index'))
            if role == 'admin' and 'admin_id' not in session:
                flash('You need to log in as an administrator to access this page.', 'danger')
                return redirect(url_for('admin_login'))
            if role == 'teacher' and 'teacher_id' not in session:
                flash('You need to log in as a teacher to access this page.', 'danger')
                return redirect(url_for('teacher_login'))
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

admin_required = login_required('admin')
teacher_required = login_required('teacher')

@app.route('/', methods=['GET', 'POST'])
def index():
    if session.get('student_id'):
        return redirect(url_for('dashboard'))
    if session.get('admin_id'):
        return redirect(url_for('admin_dashboard'))
    if session.get('teacher_id'):
        return redirect(url_for('teacher_dashboard'))
        
    teachers_empty = not check_teachers_exist()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'login':
            school_id = request.form['login_school_id']
            password = request.form['login_password']
            
            student = query_db(
                "SELECT s_schoolID, s_password, s_status, s_first_name FROM tbl_student WHERE s_schoolID = %s",
                (school_id,), one=True
            )
            
            if student and student['s_password'] == password:
                if student['s_status'] == 'Approved':
                    session['student_id'] = student['s_schoolID']
                    session['student_name'] = student['s_first_name']
                    flash('Login successful!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Your account is awaiting administrator approval.', 'warning')
            else:
                flash('Invalid School ID or Password.', 'danger')
                
        elif action == 'register':
            school_id = request.form['reg_school_id']
            password = request.form['reg_password']
            email = request.form['reg_email']
            first_name = request.form['reg_first_name']
            last_name = request.form['reg_last_name']
            year_level = request.form['reg_year_level']
            
            existing_student = query_db("SELECT s_schoolID FROM tbl_student WHERE s_schoolID = %s", (school_id,), one=True)
            if existing_student:
                flash('School ID already registered.', 'danger')
                return redirect(url_for('index', tab='register'))
            query_db(
                "INSERT INTO tbl_student (s_schoolID, s_password, s_email, s_first_name, s_last_name, s_year_level, s_status) VALUES (%s, %s, %s, %s, %s, %s, 'Pending')",
                (school_id, password, email, first_name, last_name, year_level)
            )
            flash('Registration successful! Please wait for administrator approval to log in.', 'success')
            return redirect(url_for('index', tab='login'))

    return render_template('index.html', teachers_empty=teachers_empty)

@app.route('/logout')
def logout():
    session.pop('student_id', None)
    session.pop('student_name', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required('student')
def dashboard():
    student_id = session['student_id']

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'edit_profile':
            new_password = request.form.get('s_password')
            first_name = request.form.get('s_first_name')
            last_name = request.form.get('s_last_name')
            email = request.form.get('s_email')
            year_level = request.form.get('s_year_level')
            
            if not new_password:
                flash('New Password field cannot be empty for an update.', 'danger')
                return redirect(url_for('dashboard'))
            query_db(
                "UPDATE tbl_student SET s_password = %s, s_first_name = %s, s_last_name = %s, s_email = %s, s_year_level = %s WHERE s_schoolID = %s",
                (new_password, first_name, last_name, email, year_level, student_id)
            )
            session['student_name'] = first_name
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('dashboard'))

    student_data = query_db(
        "SELECT s_schoolID, s_email, s_first_name, s_last_name, s_year_level, s_status FROM tbl_student WHERE s_schoolID = %s",
        (student_id,), one=True
    )

    total_teachers_query = query_db("SELECT COUNT(*) AS count FROM tbl_teacher", one=True)
    total_teachers = total_teachers_query['count'] if total_teachers_query else 0

    evaluations_count_query = query_db(
        "SELECT COUNT(DISTINCT t_id) AS count FROM tbl_evaluation WHERE s_schoolID = %s",
        (student_id,), one=True
    )
    evaluations_count = evaluations_count_query['count'] if evaluations_count_query else 0
    
    remaining_teachers = total_teachers - evaluations_count

    return render_template('dashboard.html', student=student_data, total_teachers=total_teachers, evaluations_count=evaluations_count, remaining_teachers=remaining_teachers)

@app.route('/evaluate', methods=['GET', 'POST'])
@login_required('student')
def evaluate():
    student_id = session['student_id']
    
    student_status = query_db("SELECT s_status FROM tbl_student WHERE s_schoolID = %s", (student_id,), one=True)
    if student_status and student_status['s_status'] != 'Approved':
        flash('Your account is pending approval. You cannot evaluate yet.', 'warning')
        return redirect(url_for('dashboard'))

    teachers_to_evaluate = query_db("""
        SELECT t_id, t_first_name, t_last_name, t_course
        FROM tbl_teacher
        WHERE t_id NOT IN (
            SELECT t_id FROM tbl_evaluation WHERE s_schoolID = %s
        )
        ORDER BY t_last_name
    """, (student_id,))

    all_teachers_count_query = query_db("SELECT COUNT(*) AS count FROM tbl_teacher", one=True)
    all_teachers = all_teachers_count_query['count']

    questions = query_db("SELECT q_id, q_text, q_order FROM tbl_evaluation_questions ORDER BY q_order")

    if request.method == 'POST':
        teacher_id = request.form.get('teacher')
        remarks = request.form.get('remarks')
        
        if not teacher_id:
            flash('Please select a teacher to evaluate.', 'danger')
            return redirect(url_for('evaluate'))
        
        already_evaluated = query_db("SELECT 1 FROM tbl_evaluation WHERE s_schoolID = %s AND t_id = %s", (student_id, teacher_id), one=True)
        if already_evaluated:
            flash('You have already evaluated this teacher.', 'danger')
            return redirect(url_for('evaluate'))

        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute(
                "INSERT INTO tbl_evaluation (s_schoolID, t_id, e_remarks, e_date_submitted) VALUES (%s, %s, %s, NOW())",
                (student_id, teacher_id, remarks)
            )
            e_id = cursor.lastrowid

            for q in questions:
                q_id = q['q_id']
                rating = request.form.get(f'q_{q_id}')
                if not rating:
                    raise ValueError("Missing rating for a question.") 
                
                cursor.execute(
                    "INSERT INTO tbl_evaluation_details (e_id, q_id, ed_value) VALUES (%s, %s, %s)",
                    (e_id, q_id, int(rating))
                )
            
            db.commit()
            flash('Evaluation submitted successfully!', 'success')
            return redirect(url_for('evaluate'))
            
        except Exception as e:
            db.rollback()
            flash(f'An error occurred during submission. Please try again. Error: {e}', 'danger')
            return redirect(url_for('evaluate'))

    return render_template('evaluate.html', teachers=teachers_to_evaluate, questions=questions, all_teachers=all_teachers)

@app.route('/teacher_login', methods=['GET', 'POST'])
def teacher_login():
    if session.get('teacher_id'):
        return redirect(url_for('teacher_dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        teacher = query_db(
            "SELECT t_id, t_password, t_first_name, t_last_name, t_course FROM tbl_teacher WHERE t_username = %s",
            (username,), one=True
        )
        
        if teacher and teacher['t_password'] == password:
            session['teacher_id'] = teacher['t_id']
            session['teacher_name'] = f"{teacher['t_first_name']} {teacher['t_last_name']}"
            session['teacher_course'] = teacher['t_course']
            flash('Login successful!', 'success')
            return redirect(url_for('teacher_dashboard'))
        else:
            flash('Invalid Username or Password.', 'danger')
            
    return render_template('teacher_login.html')

@app.route('/teacher_logout')
def teacher_logout():
    session.pop('teacher_id', None)
    session.pop('teacher_name', None)
    session.pop('teacher_course', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/teacher/dashboard', methods=['GET', 'POST'])
@teacher_required # Using the corrected decorator name
def teacher_dashboard():
    teacher_id = session.get('teacher_id')
    
    # 1. Fetch Teacher Data
    teacher_data = query_db("SELECT t_id, t_username, t_email, t_first_name, t_last_name, t_course, t_password FROM tbl_teacher WHERE t_id = %s", (teacher_id,), one=True)
    
    if not teacher_data:
        flash('Teacher account not found.', 'danger')
        return redirect(url_for('teacher_logout'))

    # 2. Fetch Evaluation Count for this teacher
    evaluation_count_result = query_db("SELECT COUNT(DISTINCT s_schoolID) as evaluation_count FROM tbl_evaluation WHERE t_id = %s", (teacher_id,), one=True)
    evaluation_count = evaluation_count_result['evaluation_count']
    
    # 3. Fetch Total Approved Students (for context/comparison)
    total_approved_students_result = query_db("SELECT COUNT(s_id) as total_approved_students FROM tbl_student WHERE s_status = 'Approved'", one=True)
    total_approved_students = total_approved_students_result['total_approved_students']

    # 4. Calculate Overall Average Rating (The new logic you requested)
    overall_avg_result = query_db("""
        SELECT 
            ROUND(AVG(ted.ed_value), 2) AS overall_avg
        FROM 
            tbl_evaluation_details ted
        JOIN 
            tbl_evaluation te ON ted.e_id = te.e_id
        WHERE 
            te.t_id = %s
    """, (teacher_id,), one=True)
    
    overall_avg_value = overall_avg_result['overall_avg'] if overall_avg_result and overall_avg_result['overall_avg'] is not None else 'N/A'
    
    # Process POST request for profile update
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'edit_profile':
            new_username = request.form['t_username']
            new_email = request.form['t_email']
            new_first_name = request.form['t_first_name']
            new_last_name = request.form['t_last_name']
            new_course = request.form['t_course']
            
            # --- REFINEMENT FOR OPTIONAL PASSWORD UPDATE ---
            new_password = request.form.get('t_password')
            
            # Use the existing password if a new one was not entered.
            # NOTE: If your app uses password hashing, you must hash the new_password here 
            # or skip the update if it's empty. Assuming plain text for this simple update.
            password_to_save = new_password if new_password else teacher_data['t_password']

            try:
                query_db("""
                    UPDATE tbl_teacher SET 
                        t_username = %s, t_email = %s, t_first_name = %s, t_last_name = %s, 
                        t_course = %s, t_password = %s
                    WHERE t_id = %s
                """, (new_username, new_email, new_first_name, new_last_name, new_course, password_to_save, teacher_id))
                
                session['teacher_name'] = f"{new_first_name} {new_last_name}"
                flash('Profile updated successfully!', 'success')
                return redirect(url_for('teacher_dashboard'))
            
            except pymysql.err.IntegrityError:
                flash('Username or Email already taken.', 'danger')
            except Exception as e:
                flash(f'An unexpected error occurred during update.', 'danger')

    return render_template('teacher_dashboard.html', 
        teacher=teacher_data, 
        evaluation_count=evaluation_count,
        total_approved_students=total_approved_students,
        overall_avg=overall_avg_value,
    )
    
@app.route('/teacher_view_results')
@teacher_required
def teacher_view_results():
    teacher_id = session['teacher_id']
    
    teacher_data = query_db(
        "SELECT t_id, t_first_name, t_last_name, t_course FROM tbl_teacher WHERE t_id = %s",
        (teacher_id,), one=True
    )
    if not teacher_data:
        flash('Teacher data not found.', 'danger')
        return redirect(url_for('teacher_dashboard'))

    stats = query_db("""
        SELECT 
            q.q_text, 
            ROUND(AVG(ed.ed_value), 2) AS avg_rating,
            COUNT(e.e_id) AS total_responses
        FROM tbl_evaluation e
        JOIN tbl_evaluation_details ed ON e.e_id = ed.e_id
        JOIN tbl_evaluation_questions q ON ed.q_id = q.q_id
        WHERE e.t_id = %s
        GROUP BY q.q_id
        ORDER BY q.q_order
    """, (teacher_id,))

    remarks = query_db("""
        SELECT e.e_remarks, e.e_date_submitted AS e_timestamp
        FROM tbl_evaluation e
        WHERE e.t_id = %s AND e.e_remarks IS NOT NULL AND e.e_remarks != ''
        ORDER BY e.e_date_submitted DESC
    """, (teacher_id,))
        
    return render_template('teacher_view_results.html', teacher=teacher_data, stats=stats, remarks=remarks)

def admin_login_required(f):
    @wraps(f) # <--- THIS IS THE CRITICAL FIX
    def wrapper(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Admin access required.', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return wrapper
    
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_id'):
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        admin = query_db(
            "SELECT a_id, a_password, a_username FROM tbl_admin WHERE a_username = %s",
            (username,), one=True
        )
        
        if admin and admin['a_password'] == password:
            session['admin_id'] = admin['a_id']
            session['admin_name'] = admin['a_username']
            flash('Admin Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid Admin Username or Password.', 'danger')
            
    return render_template('admin_login.html')

@app.route('/admin_logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    flash('Admin has been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    total_teachers = query_db("SELECT COUNT(*) AS count FROM tbl_teacher", one=True)['count']
    total_students = query_db("SELECT COUNT(*) AS count FROM tbl_student", one=True)['count']
    total_questions = query_db("SELECT COUNT(*) AS count FROM tbl_evaluation_questions", one=True)['count']

    students = query_db("SELECT s_schoolID, s_first_name, s_last_name, s_email, s_year_level, s_id FROM tbl_student WHERE s_status = 'Pending' ORDER BY s_id DESC")
    
    return render_template(
        'admin_dashboard.html', 
        total_teachers=total_teachers, 
        total_students=total_students, 
        total_questions=total_questions,
        students=students
    )

@app.route('/admin/approve_student/<string:student_id>')
@admin_required
def approve_student(student_id):
    query_db("UPDATE tbl_student SET s_status = 'Approved' WHERE s_schoolID = %s AND s_status = 'Pending'", (student_id,))
    if query_db("SELECT ROW_COUNT()", one=True)['ROW_COUNT()'] > 0:
        flash(f'Student {student_id} approved successfully!', 'success')
    else:
        flash(f'Student {student_id} not found or already approved.', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/manage_teachers_courses', methods=['GET', 'POST'])
@admin_required
def admin_manage_teachers_courses():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            username = request.form.get('t_username')
            password = request.form.get('t_password')
            first_name = request.form.get('t_first_name')
            last_name = request.form.get('t_last_name')
            email = request.form.get('t_email')
            course = request.form.get('t_course')

            try:
                query_db(
                    "INSERT INTO tbl_teacher (t_username, t_password, t_email, t_first_name, t_last_name, t_course) VALUES (%s, %s, %s, %s, %s, %s)",
                    (username, password, email, first_name, last_name, course)
                )
                flash(f'Teacher/Course ({course}) added successfully!', 'success')
            except pymysql.err.IntegrityError:
                flash('Username already exists. Please choose a different one.', 'danger')
            except Exception as e:
                flash(f'An error occurred: {e}', 'danger')
            return redirect(url_for('admin_manage_teachers_courses'))

        elif action == 'delete':
            t_id = request.form.get('t_id')
            try:
                evaluation_count = query_db("SELECT COUNT(*) AS count FROM tbl_evaluation WHERE t_id = %s", (t_id,), one=True)['count']
                if evaluation_count > 0:
                    flash('Cannot delete teacher: existing evaluations must be removed first.', 'danger')
                else:
                    query_db("DELETE FROM tbl_teacher WHERE t_id = %s", (t_id,))
                    flash('Teacher account deleted successfully!', 'success')
            except Exception as e:
                flash(f'An error occurred during deletion: {e}', 'danger')
            return redirect(url_for('admin_manage_teachers_courses'))

    teachers = query_db("SELECT t_id, t_username, t_email, t_first_name, t_last_name, t_course FROM tbl_teacher ORDER BY t_course, t_last_name")
    return render_template('admin_manage_teachers_courses.html', teachers=teachers)

@app.route('/admin/edit_user/<user_type>/<user_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_type, user_id):
    table = f'tbl_{user_type}'
    pk_col = 's_schoolID' if user_type == 'student' else 't_id'
    
    if user_type == 'student':
        user_data = query_db(f"SELECT * FROM {table} WHERE {pk_col} = %s", (user_id,), one=True)
    elif user_type == 'teacher':
        user_data = query_db(f"SELECT * FROM {table} WHERE {pk_col} = %s", (user_id,), one=True)
    else:
        flash('Invalid user type.', 'danger')
        return redirect(url_for('admin_dashboard'))

    if not user_data:
        flash(f'{user_type.capitalize()} not found.', 'danger')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        new_password = request.form.get('t_password' if user_type == 'teacher' else 's_password')
        
        if not new_password:
            flash('Password field cannot be empty for an update.', 'danger')
            return redirect(url_for('admin_edit_user', user_type=user_type, user_id=user_id))

        try:
            if user_type == 'student':
                query = f"""
                    UPDATE {table} SET 
                        s_password = %s, s_first_name = %s, s_last_name = %s, 
                        s_email = %s, s_year_level = %s, s_status = %s
                    WHERE s_schoolID = %s
                """
                args = (
                    new_password, request.form['s_first_name'], request.form['s_last_name'], 
                    request.form['s_email'], request.form['s_year_level'], request.form['s_status'], user_id
                )
            else: 
                query = f"""
                    UPDATE {table} SET 
                        t_username = %s, t_password = %s, t_email = %s, 
                        t_first_name = %s, t_last_name = %s, t_course = %s
                    WHERE t_id = %s
                """
                args = (
                    request.form['t_username'], new_password, request.form['t_email'], 
                    request.form['t_first_name'], request.form['t_last_name'], request.form['t_course'], user_id
                )

            query_db(query, args)
            flash(f'{user_type.capitalize()} account updated successfully!', 'success')
            return redirect(url_for('admin_edit_user', user_type=user_type, user_id=user_id))
            
        except pymysql.err.IntegrityError:
             flash('Username or School ID already exists.', 'danger')
        except Exception as e:
            flash(f'An error occurred: {e}', 'danger')
            
        if user_type == 'student':
            user_data = query_db(f"SELECT * FROM {table} WHERE {pk_col} = %s", (user_id,), one=True)
        else:
            user_data = query_db(f"SELECT * FROM {table} WHERE {pk_col} = %s", (user_id,), one=True)

    return render_template('admin_edit_user.html', user_type=user_type, user_data=user_data)


@app.route('/admin/view_evaluations/<int:teacher_id>')
@admin_required
def admin_view_evaluations(teacher_id):
    teacher = query_db(
        "SELECT t_first_name, t_last_name, t_course FROM tbl_teacher WHERE t_id = %s",
        (teacher_id,), one=True
    )
    if not teacher:
        flash('Teacher not found.', 'danger')
        return redirect(url_for('admin_manage_teachers_courses'))

    stats = query_db("""
        SELECT 
            q.q_text, 
            ROUND(AVG(ed.ed_value), 2) AS avg_rating,
            COUNT(e.e_id) AS total_responses
        FROM tbl_evaluation e
        JOIN tbl_evaluation_details ed ON e.e_id = ed.e_id
        JOIN tbl_evaluation_questions q ON ed.q_id = q.q_id
        WHERE e.t_id = %s
        GROUP BY q.q_id
        ORDER BY q.q_order
    """, (teacher_id,))

    remarks = query_db("""
        SELECT e.e_remarks, e.e_date_submitted AS e_timestamp, s.s_year_level
        FROM tbl_evaluation e
        JOIN tbl_student s ON e.s_schoolID = s.s_schoolID
        WHERE e.t_id = %s AND e.e_remarks IS NOT NULL AND e.e_remarks != ''
        ORDER BY e.e_date_submitted DESC
    """, (teacher_id,))
        
    return render_template('admin_view_evaluations.html', teacher=teacher, stats=stats, remarks=remarks)

@app.route('/admin/manage_questions', methods=['GET', 'POST'])
@admin_required
def admin_manage_questions():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_question':
            new_q_text = request.form.get('new_q_text')
            
            max_order_query = query_db("SELECT MAX(q_order) AS max_order FROM tbl_evaluation_questions", one=True)
            new_order = (max_order_query['max_order'] or 0) + 1
            
            query_db("INSERT INTO tbl_evaluation_questions (q_text, q_order) VALUES (%s, %s)", (new_q_text, new_order))
            flash('New question added successfully!', 'success')
            return redirect(url_for('admin_manage_questions'))
            
        elif action == 'update_questions':
            questions = query_db("SELECT q_id FROM tbl_evaluation_questions")
            
            for q in questions:
                q_id = q['q_id']
                new_text = request.form.get(f'q_text_{q_id}')
                if new_text:
                    query_db("UPDATE tbl_evaluation_questions SET q_text = %s WHERE q_id = %s", (new_text, q_id))
            
            flash('All questions updated successfully!', 'success')
            return redirect(url_for('admin_manage_questions'))

        elif action == 'delete_question':
            q_id_to_delete = request.form.get('q_id_to_delete')
            
            try:
                query_db("DELETE FROM tbl_evaluation_questions WHERE q_id = %s", (q_id_to_delete,))
                
                remaining_questions = query_db("SELECT q_id FROM tbl_evaluation_questions ORDER BY q_order")
                for index, q in enumerate(remaining_questions, 1):
                    query_db("UPDATE tbl_evaluation_questions SET q_order = %s WHERE q_id = %s", (index, q['q_id']))
                    
                flash('Question deleted and remaining questions re-ordered successfully!', 'success')
            except pymysql.err.IntegrityError:
                flash('Cannot delete question: existing evaluations depend on it.', 'danger')
            except Exception as e:
                flash(f'An error occurred: {e}', 'danger')
            
            return redirect(url_for('admin_manage_questions'))

    questions = query_db("SELECT q_id, q_text, q_order FROM tbl_evaluation_questions ORDER BY q_order")
    return render_template('admin_manage_questions.html', questions=questions)

@app.route('/admin/manage-students')
@login_required(role='admin') 
def admin_manage_students():
    """
    Handles the Admin 'Manage Student Accounts' page.
    """
    conn = get_db()
    
    # Query all student data, ordered by status (Pending first)
    students = query_db(
        "SELECT * FROM tbl_student ORDER BY FIELD(s_status, 'Pending', 'Approved')"
    )
    
    return render_template('admin_manage_students.html', students=students)

if __name__ == '__main__':
    with app.app_context():
        #init_db() 

        pass
    app.run(debug=True)