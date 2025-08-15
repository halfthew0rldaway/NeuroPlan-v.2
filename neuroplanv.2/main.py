# main.py - Updated with reminder system
import curses
import sys
import atexit
from ui import App
from task_manager import TaskManager
from org_storage import OrgStorage
from reminder_system import ReminderSystem, create_default_sounds

# Global reminder system instance
reminder_system = None

def cleanup_reminder_system():
    """Cleanup function to ensure reminder system stops properly"""
    global reminder_system
    if reminder_system:
        reminder_system.stop()

def main(stdscr):
    """The main function managed by curses.wrapper."""
    global reminder_system
    
    curses.curs_set(0) # Hide the cursor
    stdscr.nodelay(True) # Make getch non-blocking to allow for resize events

    # Initialize backend components with OrgStorage
    storage = OrgStorage("org_files")
    task_manager = TaskManager(storage)
    
    # Initialize and start reminder system
    reminder_system = ReminderSystem(task_manager, check_interval=30)  # Check every 30 seconds
    
    # Create default sound files if they don't exist
    create_default_sounds()
    
    # Start the reminder system
    reminder_system.start()
    
    # Register cleanup function
    atexit.register(cleanup_reminder_system)
    
    # Get initial screen dimensions
    height, width = stdscr.getmaxyx()

    # Create and run the App (pass reminder_system to App)
    app = App(stdscr, task_manager, height, width, reminder_system)
    
    try:
        app.run()
    finally:
        # Ensure cleanup happens
        cleanup_reminder_system()

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except Exception as e:
        print(f"An error occurred: {e}")
        cleanup_reminder_system()
    finally:
        print("NeuroPlan has shut down.")