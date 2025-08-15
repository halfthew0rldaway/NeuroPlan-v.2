# notification_test.py - Test your notification setup
import threading
import time
import datetime
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional

try:
    from plyer import notification
    print("✓ plyer imported successfully")
except ImportError:
    print("✗ plyer not found - install with: pip install plyer")
    exit(1)

# Test basic notification first
def test_basic_notification():
    """Test if basic notifications work"""
    print("Testing basic notification...")
    try:
        notification.notify(
            title="Test Notification",
            message="If you see this, notifications are working!",
            timeout=5,
            app_name="TaskManager"
        )
        print("✓ Basic notification sent")
        return True
    except Exception as e:
        print(f"✗ Basic notification failed: {e}")
        return False

# Enhanced reminder system with better error handling
class ReminderType(Enum):
    OVERDUE = "overdue"
    BEFORE_DUE = "before_due"
    CUSTOM = "custom"

@dataclass
class Reminder:
    task_id: str
    trigger_time: datetime.datetime
    message: str
    reminder_type: ReminderType
    sent: bool = False

class ReminderSystem:
    def __init__(self, task_manager):
        self.task_manager = task_manager
        self.reminders: List[Reminder] = []
        self.running = False
        self.thread = None
        self.check_interval = 30  # Check every 30 seconds
        
    def start(self):
        """Start the reminder system"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print("✓ Reminder system started")
        
    def stop(self):
        """Stop the reminder system"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        print("✓ Reminder system stopped")
        
    def add_reminder(self, task_id: str, trigger_time: datetime.datetime, 
                    message: str, reminder_type: ReminderType):
        """Add a new reminder"""
        reminder = Reminder(task_id, trigger_time, message, reminder_type)
        self.reminders.append(reminder)
        print(f"✓ Reminder added for {trigger_time}")
        
    def get_upcoming_reminders(self, hours: int = 24) -> List[Reminder]:
        """Get reminders in the next N hours"""
        now = datetime.datetime.now()
        cutoff = now + datetime.timedelta(hours=hours)
        
        upcoming = [r for r in self.reminders 
                   if now <= r.trigger_time <= cutoff and not r.sent]
        return sorted(upcoming, key=lambda r: r.trigger_time)
        
    def _run_loop(self):
        """Main reminder checking loop"""
        print("Reminder system loop started")
        while self.running:
            try:
                self._check_reminders()
                time.sleep(self.check_interval)
            except Exception as e:
                print(f"Error in reminder loop: {e}")
                time.sleep(self.check_interval)
    
    def _check_reminders(self):
        """Check for due reminders and send notifications"""
        now = datetime.datetime.now()
        
        for reminder in self.reminders:
            if not reminder.sent and reminder.trigger_time <= now:
                self._send_notification(reminder)
                reminder.sent = True
    
    def _send_notification(self, reminder: Reminder):
        """Send a notification for a reminder"""
        try:
            # Get task details
            task_id = reminder.task_id.split('_')[0]  # Handle compound IDs
            task = self.task_manager.get_task(task_id) if hasattr(self.task_manager, 'get_task') else None
            
            title = "Task Reminder"
            if task:
                title = f"Task: {task.title[:30]}"
            
            print(f"Sending notification: {title}")
            
            notification.notify(
                title=title,
                message=reminder.message,
                timeout=10,
                app_name="NeuroPlan"
            )
            
            print(f"✓ Notification sent for reminder {reminder.task_id}")
            
        except Exception as e:
            print(f"✗ Failed to send notification: {e}")

# Mock task manager for testing
class MockTaskManager:
    def __init__(self):
        self.tasks = {}
    
    def get_task(self, task_id):
        return self.tasks.get(task_id)
    
    def add_task(self, task_id, title):
        self.tasks[task_id] = type('Task', (), {'id': task_id, 'title': title})()

def test_reminder_system():
    """Test the complete reminder system"""
    print("\n=== Testing Reminder System ===")
    
    # Create mock task manager
    task_manager = MockTaskManager()
    task_manager.add_task("test1", "Test Task - Check Notifications")
    
    # Create reminder system
    reminder_system = ReminderSystem(task_manager)
    
    # Add a reminder for 5 seconds from now
    future_time = datetime.datetime.now() + datetime.timedelta(seconds=5)
    reminder_system.add_reminder(
        "test1", 
        future_time, 
        "This is a test reminder - it should appear in 5 seconds!",
        ReminderType.CUSTOM
    )
    
    # Start the system
    reminder_system.start()
    
    print("Waiting 10 seconds for reminder to trigger...")
    time.sleep(10)
    
    # Stop the system
    reminder_system.stop()
    
    return reminder_system

def main():
    """Run all tests"""
    print("=== Notification System Test ===\n")
    
    # Test 1: Basic notification
    if not test_basic_notification():
        print("\n⚠️  Basic notifications failed. Check:")
        print("   1. System notification settings enabled")
        print("   2. plyer installation: pip install plyer")
        print("   3. Platform-specific requirements")
        return
    
    print("Waiting 5 seconds to see the test notification...")
    time.sleep(5)
    
    # Test 2: Reminder system
    reminder_system = test_reminder_system()
    
    print("\n=== Integration with Your App ===")
    print("To integrate with your app, modify your main startup code:")
    print("""
# In your main.py or wherever you start the UI:
from ui import App
import curses

def main(stdscr):
    task_manager = YourTaskManager()  # Your existing task manager
    reminder_system = ReminderSystem(task_manager)
    reminder_system.start()  # Start reminder system
    
    height, width = stdscr.getmaxyx()
    app = App(stdscr, task_manager, height, width, reminder_system)
    app.run()
    
    reminder_system.stop()  # Clean shutdown

curses.wrapper(main)
    """)

if __name__ == "__main__":
    main()