import psycopg2
import json
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, BOT_PREFIX

def get_connection():
    """Get a connection to the PostgreSQL database"""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def init_database():
    """Initialize the database tables if they don't exist"""
    print("Initializing database tables...")
    init_db()
    print("Database tables have been initialized.")

def reset_database():
    """Reset the database by dropping all tables and recreating them"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Drop all tables if they exist
    cursor.execute(f"DROP TABLE IF EXISTS {BOT_PREFIX}developer_messages")
    cursor.execute(f"DROP TABLE IF EXISTS {BOT_PREFIX}interview_requests")
    cursor.execute(f"DROP TABLE IF EXISTS {BOT_PREFIX}test_submissions")
    cursor.execute(f"DROP TABLE IF EXISTS {BOT_PREFIX}users")
    
    conn.commit()
    conn.close()
    
    # Reinitialize the database
    init_db()
    print("Database has been reset successfully.")

def init_db():
    """Initialize the database with required tables"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create users table to track progress
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS {BOT_PREFIX}users (
        user_id BIGINT PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        unlocked_stages TEXT,
        current_test_results TEXT,
        registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create table for test submissions
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS {BOT_PREFIX}test_submissions (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        test_type TEXT,
        submission_data TEXT,
        status TEXT DEFAULT 'pending',
        feedback TEXT,
        submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES {BOT_PREFIX}users(user_id)
    )
    ''')
    
    # Create table for interview scheduling
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS {BOT_PREFIX}interview_requests (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        preferred_day TEXT,
        preferred_time TEXT,
        status TEXT DEFAULT 'pending',
        recruiter_response TEXT,
        request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES {BOT_PREFIX}users(user_id)
    )
    ''')
    
    # Create table for developer messages
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS {BOT_PREFIX}developer_messages (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        user_name TEXT,
        message TEXT,
        timestamp TIMESTAMP,
        status TEXT DEFAULT 'unread',
        FOREIGN KEY (user_id) REFERENCES {BOT_PREFIX}users(user_id)
    )
    ''')
    
    conn.commit()
    conn.close()

def register_user(user_id, username, first_name, last_name):
    """Register a new user or update existing user information"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute(f'SELECT user_id FROM {BOT_PREFIX}users WHERE user_id = %s', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        # Initial unlocked stages - only first two options are unlocked
        unlocked_stages = json.dumps([
            'about_company',
            'primary_file'
        ])
        
        cursor.execute(
            f'INSERT INTO {BOT_PREFIX}users (user_id, username, first_name, last_name, unlocked_stages) VALUES (%s, %s, %s, %s, %s)',
            (user_id, username, first_name, last_name, unlocked_stages)
        )
    else:
        cursor.execute(
            f'UPDATE {BOT_PREFIX}users SET username = %s, first_name = %s, last_name = %s WHERE user_id = %s',
            (username, first_name, last_name, user_id)
        )
    
    conn.commit()
    conn.close()

def get_user_unlocked_stages(user_id):
    """Get the list of unlocked stages for a user"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(f'SELECT unlocked_stages FROM {BOT_PREFIX}users WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result and result[0]:
        return json.loads(result[0])
    return []

def get_user_test_results(user_id):
    """Get the test results for a user"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(f'SELECT current_test_results FROM {BOT_PREFIX}users WHERE user_id = %s', (user_id,))
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
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current unlocked stages
    cursor.execute(f'SELECT unlocked_stages FROM {BOT_PREFIX}users WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()
    
    if result and result[0]:
        unlocked_stages = json.loads(result[0])
        if stage_name not in unlocked_stages:
            unlocked_stages.append(stage_name)
            
            cursor.execute(
                f'UPDATE {BOT_PREFIX}users SET unlocked_stages = %s WHERE user_id = %s',
                (json.dumps(unlocked_stages), user_id)
            )
            conn.commit()
    
    conn.close()

def save_test_submission(user_id, test_type, submission_data):
    """Save a test submission and return the submission ID"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        f'INSERT INTO {BOT_PREFIX}test_submissions (user_id, test_type, submission_data) VALUES (%s, %s, %s) RETURNING id',
        (user_id, test_type, json.dumps(submission_data))
    )
    
    # Get the last inserted ID
    submission_id = cursor.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    return submission_id

def update_test_result(user_id, test_name, passed):
    """Update a user's test result"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current test results
    cursor.execute(f'SELECT current_test_results FROM {BOT_PREFIX}users WHERE user_id = %s', (user_id,))
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
        f'UPDATE {BOT_PREFIX}users SET current_test_results = %s WHERE user_id = %s',
        (json.dumps(test_results), user_id)
    )
    
    conn.commit()
    conn.close()

def update_test_submission(submission_id, status, feedback):
    """Update a test submission with recruiter feedback"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        f'UPDATE {BOT_PREFIX}test_submissions SET status = %s, feedback = %s WHERE id = %s',
        (status, feedback, submission_id)
    )
    
    # Get the user_id and test_type for this submission
    cursor.execute(f'SELECT user_id, test_type FROM {BOT_PREFIX}test_submissions WHERE id = %s', (submission_id,))
    result = cursor.fetchone()
    
    conn.commit()
    conn.close()
    
    if result:
        return {'user_id': result[0], 'test_type': result[1], 'status': status}
    return None

def get_pending_submissions():
    """Get all pending test submissions"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        f'''SELECT ts.id, ts.user_id, u.first_name, u.last_name, ts.test_type, ts.submission_data 
           FROM {BOT_PREFIX}test_submissions ts 
           JOIN {BOT_PREFIX}users u ON ts.user_id = u.user_id 
           WHERE ts.status = 'pending' 
           ORDER BY ts.submission_date DESC'''
    )
    
    submissions = []
    for row in cursor.fetchall():
        submissions.append({
            'id': row[0],
            'user_id': row[1],
            'candidate_name': f"{row[2] or ''} {row[3] or ''}".strip(),
            'test_type': row[4],
            'submission_data': json.loads(row[5]) if row[5] else {}
        })
    
    conn.close()
    return submissions

def save_interview_request(user_id, preferred_day, preferred_time):
    """Save an interview request from a candidate"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if there's an existing pending request
    cursor.execute(f'SELECT id FROM {BOT_PREFIX}interview_requests WHERE user_id = %s AND status = %s', (user_id, 'pending'))
    existing = cursor.fetchone()
    
    if existing:
        # Update existing request
        cursor.execute(
            f'UPDATE {BOT_PREFIX}interview_requests SET preferred_day = %s, preferred_time = %s, request_date = CURRENT_TIMESTAMP WHERE id = %s',
            (preferred_day, preferred_time, existing[0])
        )
        request_id = existing[0]
    else:
        # Create new request
        cursor.execute(
            f'INSERT INTO {BOT_PREFIX}interview_requests (user_id, preferred_day, preferred_time) VALUES (%s, %s, %s) RETURNING id',
            (user_id, preferred_day, preferred_time)
        )
        request_id = cursor.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    return request_id

def update_interview_request(request_id, status, recruiter_response):
    """Update an interview request with recruiter feedback"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        f'UPDATE {BOT_PREFIX}interview_requests SET status = %s, recruiter_response = %s WHERE id = %s',
        (status, recruiter_response, request_id)
    )
    
    # Get the user_id for this request
    cursor.execute(f'SELECT user_id FROM {BOT_PREFIX}interview_requests WHERE id = %s', (request_id,))
    result = cursor.fetchone()
    
    conn.commit()
    conn.close()
    
    if result:
        return {'user_id': result[0], 'status': status}
    return None

def get_pending_interview_requests():
    """Get all pending interview requests"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        f'''SELECT ir.id, ir.user_id, u.first_name, u.last_name, ir.preferred_day, ir.preferred_time 
           FROM {BOT_PREFIX}interview_requests ir 
           JOIN {BOT_PREFIX}users u ON ir.user_id = u.user_id 
           WHERE ir.status = 'pending' 
           ORDER BY ir.request_date DESC'''
    )
    
    requests = []
    for row in cursor.fetchall():
        requests.append({
            'id': row[0],
            'user_id': row[1],
            'candidate_name': f"{row[2] or ''} {row[3] or ''}".strip(),
            'preferred_day': row[4],
            'preferred_time': row[5]
        })
    
    conn.close()
    return requests

def get_test_result(user_id, test_type):
    """Get the result of a specific test for a user"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        f'SELECT status, feedback FROM {BOT_PREFIX}test_submissions WHERE user_id = %s AND test_type = %s ORDER BY submission_date DESC LIMIT 1',
        (user_id, test_type)
    )
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {'status': result[0], 'feedback': result[1]}
    return None

def get_interview_status(user_id):
    """Get the status of a user's interview request"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        f'''SELECT status, recruiter_response, preferred_day, preferred_time 
           FROM {BOT_PREFIX}interview_requests 
           WHERE user_id = %s 
           ORDER BY request_date DESC LIMIT 1''',
        (user_id,)
    )
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'status': result[0],
            'response': result[1],
            'preferred_day': result[2],
            'preferred_time': result[3]
        }
    return None

def user_exists(user_id):
    """Check if a user exists in the database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(f'SELECT user_id FROM {BOT_PREFIX}users WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    return result is not None

def create_user(user_id, username):
    """Create a new user in the database with minimal information"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Initial unlocked stages - only first two options are unlocked
    unlocked_stages = json.dumps([
        'about_company',
        'primary_file'
    ])
    
    cursor.execute(
        f'INSERT INTO {BOT_PREFIX}users (user_id, username, unlocked_stages) VALUES (%s, %s, %s)',
        (user_id, username, unlocked_stages)
    )
    
    conn.commit()
    conn.close()

def get_metrics():
    """Get recruitment metrics from the database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get total number of candidates
    cursor.execute(f'SELECT COUNT(*) FROM {BOT_PREFIX}users')
    total_candidates = cursor.fetchone()[0]
    
    # Get number of candidates who completed the primary test
    cursor.execute(f'''
        SELECT COUNT(DISTINCT user_id) 
        FROM {BOT_PREFIX}test_submissions 
        WHERE test_type = 'primary_test'
    ''')
    primary_completions = cursor.fetchone()[0]
    
    # Get number of candidates who completed the logic test
    cursor.execute(f'''
        SELECT COUNT(DISTINCT user_id) 
        FROM {BOT_PREFIX}test_submissions 
        WHERE test_type = 'logic_test'
    ''')
    logic_completions = cursor.fetchone()[0]
    
    # Get number of candidates who requested an interview
    cursor.execute(f'SELECT COUNT(DISTINCT user_id) FROM {BOT_PREFIX}interview_requests')
    interview_requests = cursor.fetchone()[0]
    
    # Get number of approved interviews
    cursor.execute(f'''
        SELECT COUNT(DISTINCT user_id) 
        FROM {BOT_PREFIX}interview_requests 
        WHERE status = 'approved'
    ''')
    approved_interviews = cursor.fetchone()[0]
    
    # Get test pass rates
    cursor.execute(f'''
        SELECT test_type, status, COUNT(*) 
        FROM {BOT_PREFIX}test_submissions 
        GROUP BY test_type, status
    ''')
    
    test_stats = {}
    for row in cursor.fetchall():
        test_type, status, count = row
        if test_type not in test_stats:
            test_stats[test_type] = {'passed': 0, 'failed': 0, 'pending': 0}
        
        if status in test_stats[test_type]:
            test_stats[test_type][status] = count
    
    # Calculate pass rates and format the results
    pass_rates = {}
    for test_type, stats in test_stats.items():
        total = stats['passed'] + stats['failed']
        if total > 0:
            pass_rate = (stats['passed'] / total) * 100
        else:
            pass_rate = 0
        
        pass_rates[test_type] = {
            'pass_rate': round(pass_rate, 2),
            'total_submitted': total,
            'passed': stats['passed'],
            'failed': stats['failed'],
            'pending': stats['pending']
        }
    
    conn.close()
    
    return {
        'total_candidates': total_candidates,
        'primary_test_completions': primary_completions,
        'logic_test_completions': logic_completions,
        'interview_requests': interview_requests,
        'approved_interviews': approved_interviews,
        'test_stats': pass_rates
    }

def get_user_info(user_id):
    """Get user information from the database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(f'SELECT username, first_name, last_name FROM {BOT_PREFIX}users WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'username': result[0],
            'first_name': result[1],
            'last_name': result[2]
        }
    
    return {
        'username': None,
        'first_name': None,
        'last_name': None
    }

def send_developer_message(user_id, user_name, message):
    """Save a message from a user to the developers"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        f'INSERT INTO {BOT_PREFIX}developer_messages (user_id, user_name, message, timestamp) VALUES (%s, %s, %s, CURRENT_TIMESTAMP)',
        (user_id, user_name, message)
    )
    
    conn.commit()
    conn.close()

def get_developer_messages():
    """Get all unread messages for developers"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        f'SELECT id, user_id, user_name, message, timestamp FROM {BOT_PREFIX}developer_messages WHERE status = %s ORDER BY timestamp DESC',
        ('unread',)
    )
    
    messages = []
    for row in cursor.fetchall():
        messages.append({
            'id': row[0],
            'user_id': row[1],
            'user_name': row[2],
            'message': row[3],
            'timestamp': row[4]
        })
    
    conn.close()
    return messages

def mark_message_read(message_id):
    """Mark a developer message as read"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        f'UPDATE {BOT_PREFIX}developer_messages SET status = %s WHERE id = %s',
        ('read', message_id)
    )
    
    conn.commit()
    conn.close()
