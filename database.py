import sqlite3
import json
from config import DATABASE_NAME

def reset_database():
    """Reset the database by dropping all tables and recreating them"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Drop all tables if they exist
    cursor.execute("DROP TABLE IF EXISTS developer_messages")
    cursor.execute("DROP TABLE IF EXISTS interview_requests")
    cursor.execute("DROP TABLE IF EXISTS test_submissions")
    cursor.execute("DROP TABLE IF EXISTS users")
    
    conn.commit()
    conn.close()
    
    # Reinitialize the database
    init_db()
    print("Database has been reset successfully.")

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Create users table to track progress
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        unlocked_stages TEXT,
        current_test_results TEXT,
        registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create table for test submissions
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS test_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        test_type TEXT,
        submission_data TEXT,
        status TEXT DEFAULT 'pending',
        feedback TEXT,
        submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')
    
    # Create table for interview scheduling
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS interview_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        preferred_day TEXT,
        preferred_time TEXT,
        status TEXT DEFAULT 'pending',
        recruiter_response TEXT,
        request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')
    
    # Create table for developer messages
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS developer_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        user_name TEXT,
        message TEXT,
        timestamp TIMESTAMP,
        status TEXT DEFAULT 'unread',
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')
    
    conn.commit()
    conn.close()

def register_user(user_id, username, first_name, last_name):
    """Register a new user or update existing user information"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        # Initial unlocked stages - only first two options are unlocked
        unlocked_stages = json.dumps([
            'about_company',
            'primary_file'
        ])
        
        cursor.execute(
            'INSERT INTO users (user_id, username, first_name, last_name, unlocked_stages) VALUES (?, ?, ?, ?, ?)',
            (user_id, username, first_name, last_name, unlocked_stages)
        )
    else:
        cursor.execute(
            'UPDATE users SET username = ?, first_name = ?, last_name = ? WHERE user_id = ?',
            (username, first_name, last_name, user_id)
        )
    
    conn.commit()
    conn.close()

def get_user_unlocked_stages(user_id):
    """Get the list of unlocked stages for a user"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT unlocked_stages FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result and result[0]:
        return json.loads(result[0])
    return []

def get_user_test_results(user_id):
    """Get the test results for a user"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT current_test_results FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result and result[0]:
        try:
            return json.loads(result[0])
        except json.JSONDecodeError:
            return {}  # Default empty test results
    else:
        return {}  # Default empty test results

def unlock_stage(user_id, stage_name):
    """Unlock a new stage for the user"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Get current unlocked stages
    cursor.execute('SELECT unlocked_stages FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if result and result[0]:
        unlocked_stages = json.loads(result[0])
        if stage_name not in unlocked_stages:
            unlocked_stages.append(stage_name)
            
            cursor.execute(
                'UPDATE users SET unlocked_stages = ? WHERE user_id = ?',
                (json.dumps(unlocked_stages), user_id)
            )
            conn.commit()
    
    conn.close()

def save_test_submission(user_id, test_type, submission_data):
    """Save a test submission and return the submission ID"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT INTO test_submissions (user_id, test_type, submission_data) VALUES (?, ?, ?)',
        (user_id, test_type, json.dumps(submission_data))
    )
    
    # Get the last inserted ID
    submission_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return submission_id

def update_test_result(user_id, test_name, passed):
    """Update a user's test result"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Get current test results
    cursor.execute('SELECT current_test_results FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if result:
        try:
            test_results = json.loads(result[0]) if result[0] else {}
        except json.JSONDecodeError:
            test_results = {}
    else:
        test_results = {}
    
    # Update the test result
    test_results[test_name] = passed
    
    # Save back to database
    cursor.execute(
        'UPDATE users SET current_test_results = ? WHERE user_id = ?',
        (json.dumps(test_results), user_id)
    )
    
    conn.commit()
    conn.close()

def update_test_submission(submission_id, status, feedback):
    """Update a test submission with recruiter feedback"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        'UPDATE test_submissions SET status = ?, feedback = ? WHERE id = ?',
        (status, feedback, submission_id)
    )
    
    # Get the user_id and test_type for this submission
    cursor.execute('SELECT user_id, test_type FROM test_submissions WHERE id = ?', (submission_id,))
    result = cursor.fetchone()
    
    conn.commit()
    conn.close()
    
    if result:
        return {'user_id': result[0], 'test_type': result[1], 'status': status}
    return None

def get_pending_submissions():
    """Get all pending test submissions"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        '''SELECT ts.id, ts.user_id, u.first_name, u.last_name, ts.test_type, ts.submission_data 
           FROM test_submissions ts 
           JOIN users u ON ts.user_id = u.user_id 
           WHERE ts.status = 'pending' 
           ORDER BY ts.submission_date DESC'''
    )
    
    submissions = [{
        'id': row[0],
        'user_id': row[1],
        'candidate_name': f"{row[2]} {row[3]}",
        'test_type': row[4],
        'submission_data': json.loads(row[5]) if row[5] else None
    } for row in cursor.fetchall()]
    
    conn.close()
    return submissions

def save_interview_request(user_id, preferred_day, preferred_time):
    """Save an interview request and return the request ID"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT INTO interview_requests (user_id, preferred_day, preferred_time) VALUES (?, ?, ?)',
        (user_id, preferred_day, preferred_time)
    )
    
    # Get the last inserted ID
    request_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return request_id

def update_interview_request(request_id, status, recruiter_response):
    """Update an interview request with recruiter response"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        'UPDATE interview_requests SET status = ?, recruiter_response = ? WHERE id = ?',
        (status, recruiter_response, request_id)
    )
    
    # Get the user_id for this request
    cursor.execute('SELECT user_id FROM interview_requests WHERE id = ?', (request_id,))
    result = cursor.fetchone()
    
    conn.commit()
    conn.close()
    
    if result:
        return {'user_id': result[0], 'status': status}
    return None

def get_pending_interview_requests():
    """Get all pending interview requests"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        '''SELECT ir.id, ir.user_id, u.first_name, u.last_name, ir.preferred_day, ir.preferred_time 
           FROM interview_requests ir 
           JOIN users u ON ir.user_id = u.user_id 
           WHERE ir.status = 'pending' 
           ORDER BY ir.request_date DESC'''
    )
    
    requests = [{
        'id': row[0],
        'user_id': row[1],
        'candidate_name': f"{row[2]} {row[3]}",
        'preferred_day': row[4],
        'preferred_time': row[5]
    } for row in cursor.fetchall()]
    
    conn.close()
    return requests

def get_test_result(user_id, test_type):
    """Get the latest test result for a user and test type"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        '''SELECT status, feedback FROM test_submissions 
           WHERE user_id = ? AND test_type = ? 
           ORDER BY submission_date DESC LIMIT 1''',
        (user_id, test_type)
    )
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {'status': result[0], 'feedback': result[1]}
    return None

def get_interview_status(user_id):
    """Get the latest interview status for a user"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        '''SELECT status, preferred_day, preferred_time, recruiter_response FROM interview_requests 
           WHERE user_id = ? 
           ORDER BY request_date DESC LIMIT 1''',
        (user_id,)
    )
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'status': result[0],
            'preferred_day': result[1],
            'preferred_time': result[2],
            'recruiter_response': result[3]
        }
    return None
