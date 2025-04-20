import database
import sys
import os

# List of user IDs to delete
# Add user IDs here that should be deleted
USERS_TO_DELETE = [
    # Example: 123456789,
]

def reset_specified_users():
    """
    Delete data only for users specified in USERS_TO_DELETE list.
    If the list is empty, prints a warning message and exits.
    """
    if not USERS_TO_DELETE:
        print("WARNING: No users specified for deletion in USERS_TO_DELETE list.")
        print("Please add user IDs to the USERS_TO_DELETE list in reset_db.py.")
        sys.exit(1)
    
    # Connect to database
    try:
        conn = database.get_connection()
        cursor = conn.cursor()
        
        total_deleted = 0
        
        # Loop through each user and delete their data
        for user_id in USERS_TO_DELETE:
            # Delete user's test submissions
            cursor.execute(
                f'DELETE FROM {database.BOT_PREFIX}test_submissions WHERE user_id = %s',
                (user_id,)
            )
            deleted = cursor.rowcount
            
            # Delete user's interview requests
            cursor.execute(
                f'DELETE FROM {database.BOT_PREFIX}interview_requests WHERE user_id = %s',
                (user_id,)
            )
            deleted += cursor.rowcount
            
            # Delete user's developer messages
            cursor.execute(
                f'DELETE FROM {database.BOT_PREFIX}developer_messages WHERE user_id = %s',
                (user_id,)
            )
            deleted += cursor.rowcount
            
            # Finally delete the user
            cursor.execute(
                f'DELETE FROM {database.BOT_PREFIX}users WHERE user_id = %s',
                (user_id,)
            )
            user_deleted = cursor.rowcount
            
            if user_deleted > 0:
                total_deleted += 1
                print(f"Deleted user {user_id} and {deleted} related records")
            else:
                print(f"User {user_id} not found in database")
        
        conn.commit()
        conn.close()
        
        print(f"Successfully deleted data for {total_deleted} users")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    reset_specified_users()
