# reminder_system.py
import threading
import time
import datetime
from typing import Dict, Set, Callable, Optional
from dataclasses import dataclass
from enum import Enum
import os
import sys

# Cross-platform notification imports
try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False
    print("Warning: plyer not installed. Install with: pip install plyer")

# Sound support
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("Warning: pygame not installed. Install with: pip install pygame")

class ReminderType(Enum):
    """Types of reminders"""
    DUE_DATE = "due_date"           # Remind at exact due date
    BEFORE_DUE = "before_due"       # Remind X minutes before due date
    OVERDUE = "overdue"             # Remind after due date has passed

@dataclass
class ReminderConfig:
    """Configuration for a reminder"""
    task_id: str
    reminder_type: ReminderType
    trigger_time: datetime.datetime
    message: str
    sound_file: Optional[str] = None
    enabled: bool = True
    sent: bool = False

class ReminderSystem:
    """Handles desktop notifications and reminders for tasks"""
    
    def __init__(self, task_manager, check_interval: int = 30):
        """
        Initialize the reminder system
        
        Args:
            task_manager: TaskManager instance
            check_interval: How often to check for reminders (seconds)
        """
        self.task_manager = task_manager
        self.check_interval = check_interval
        self.running = False
        self.reminder_thread = None
        self.sent_reminders: Set[str] = set()  # Track sent reminders to avoid duplicates
        
        # Initialize sound system
        if PYGAME_AVAILABLE:
            try:
                pygame.mixer.init()
                self.sound_enabled = True
            except pygame.error:
                self.sound_enabled = False
                print("Warning: Could not initialize sound system")
        else:
            self.sound_enabled = False
        
        # Default sound files (you can customize these)
        self.sound_files = {
            ReminderType.DUE_DATE: "due_notification.wav",
            ReminderType.BEFORE_DUE: "warning_notification.wav", 
            ReminderType.OVERDUE: "overdue_notification.wav"
        }
        
        self.notification_callbacks: Dict[str, Callable] = {}
    
    def start(self):
        """Start the reminder system background thread"""
        if self.running:
            return
        
        self.running = True
        self.reminder_thread = threading.Thread(target=self._reminder_loop, daemon=True)
        self.reminder_thread.start()
        print("Reminder system started")
    
    def stop(self):
        """Stop the reminder system"""
        self.running = False
        if self.reminder_thread:
            self.reminder_thread.join(timeout=1)
        print("Reminder system stopped")
    
    def _reminder_loop(self):
        """Main loop that checks for reminders"""
        while self.running:
            try:
                self._check_all_reminders()
                time.sleep(self.check_interval)
            except Exception as e:
                print(f"Error in reminder loop: {e}")
                time.sleep(self.check_interval)
    
    def _check_all_reminders(self):
        """Check all tasks for reminder conditions"""
        now = datetime.datetime.now()
        
        for task in self.task_manager.tasks.values():
            if not task.due_date or task.status.value == "DONE":
                continue
            
            # Generate reminder configs for this task
            reminders = self._generate_reminders_for_task(task, now)
            
            for reminder in reminders:
                if (reminder.enabled and 
                    not reminder.sent and 
                    now >= reminder.trigger_time and
                    reminder.task_id not in self.sent_reminders):
                    
                    self._send_reminder(reminder)
    
    def _generate_reminders_for_task(self, task, now: datetime.datetime) -> list[ReminderConfig]:
        """Generate reminder configurations for a task"""
        reminders = []
        
        if not task.due_date:
            return reminders
        
        # Create unique identifier for this task's reminders
        base_id = f"{task.id}_{task.due_date.isoformat()}"
        
        # Due date reminder (at exact due time)
        if now <= task.due_date:
            reminders.append(ReminderConfig(
                task_id=f"{base_id}_due",
                reminder_type=ReminderType.DUE_DATE,
                trigger_time=task.due_date,
                message=f"Task due now: {task.title}",
                sound_file=self.sound_files[ReminderType.DUE_DATE]
            ))
        
        # Before due reminder (30 minutes before)
        before_time = task.due_date - datetime.timedelta(minutes=30)
        if now <= before_time:
            reminders.append(ReminderConfig(
                task_id=f"{base_id}_before",
                reminder_type=ReminderType.BEFORE_DUE,
                trigger_time=before_time,
                message=f"Task due in 30 minutes: {task.title}",
                sound_file=self.sound_files[ReminderType.BEFORE_DUE]
            ))
        
        # Overdue reminder (30 minutes after due)
        overdue_time = task.due_date + datetime.timedelta(minutes=30)
        if task.due_date < now <= overdue_time:
            reminders.append(ReminderConfig(
                task_id=f"{base_id}_overdue",
                reminder_type=ReminderType.OVERDUE,
                trigger_time=overdue_time,
                message=f"Task is overdue: {task.title}",
                sound_file=self.sound_files[ReminderType.OVERDUE]
            ))
        
        return reminders
    
    def _send_reminder(self, reminder: ReminderConfig):
        """Send a reminder notification"""
        try:
            # Get the actual task for more details
            task_id = reminder.task_id.split('_')[0]  # Extract original task ID
            task = self.task_manager.get_task(task_id)
            
            if not task:
                return
            
            # Prepare notification content
            title = f"NeuroPlan Reminder"
            message = reminder.message
            
            if task.author:
                message += f"\nAuthor: {task.author}"
            
            if task.description:
                # Truncate description for notification
                desc_preview = task.description[:100] + "..." if len(task.description) > 100 else task.description
                message += f"\nDescription: {desc_preview}"
            
            # Send desktop notification
            if PLYER_AVAILABLE:
                try:
                    notification.notify(
                        title=title,
                        message=message,
                        timeout=10,
                        app_name="NeuroPlan",
                        # app_icon="path/to/icon.ico"  # Uncomment and set icon path if you have one
                    )
                    print(f"Notification sent: {reminder.message}")
                except Exception as e:
                    print(f"Failed to send notification: {e}")
                    # Fallback to console notification
                    self._console_notification(title, message)
            else:
                self._console_notification(title, message)
            
            # Play sound
            if self.sound_enabled and reminder.sound_file:
                self._play_sound(reminder.sound_file)
            else:
                # Fallback: system bell
                print('\a')  # Terminal bell
            
            # Mark as sent
            self.sent_reminders.add(reminder.task_id)
            
            # Call any registered callbacks
            if reminder.task_id in self.notification_callbacks:
                self.notification_callbacks[reminder.task_id](task, reminder)
        
        except Exception as e:
            print(f"Error sending reminder: {e}")
    
    def _console_notification(self, title: str, message: str):
        """Fallback console notification"""
        print(f"\n{'='*50}")
        print(f"🔔 {title}")
        print(f"{'='*50}")
        print(message)
        print(f"{'='*50}\n")
    
    def _play_sound(self, sound_file: str):
        """Play notification sound"""
        if not self.sound_enabled:
            return
        
        try:
            # Check if sound file exists
            if os.path.exists(sound_file):
                pygame.mixer.music.load(sound_file)
                pygame.mixer.music.play()
            else:
                # Play default system sound
                print('\a')  # Terminal bell
        except Exception as e:
            print(f"Error playing sound: {e}")
            print('\a')  # Fallback to terminal bell
    
    def add_custom_reminder(self, task_id: str, reminder_time: datetime.datetime, 
                          message: str, sound_file: Optional[str] = None):
        """Add a custom reminder for a task"""
        reminder_id = f"{task_id}_custom_{reminder_time.isoformat()}"
        
        # This would be better stored in a database or file, but for now we'll use memory
        # You could extend this to persist custom reminders
        print(f"Custom reminder scheduled for {reminder_time}: {message}")
    
    def register_notification_callback(self, task_id: str, callback: Callable):
        """Register a callback to be called when a notification is sent"""
        self.notification_callbacks[task_id] = callback
    
    def set_reminder_interval(self, interval_minutes: int):
        """Set how many minutes before due date to send warning reminder"""
        # This could be made configurable per task or globally
        pass
    
    def get_upcoming_reminders(self, hours_ahead: int = 24) -> list[ReminderConfig]:
        """Get all reminders scheduled within the next N hours"""
        now = datetime.datetime.now()
        cutoff = now + datetime.timedelta(hours=hours_ahead)
        
        upcoming = []
        for task in self.task_manager.tasks.values():
            if task.due_date and now <= task.due_date <= cutoff and task.status.value != "DONE":
                reminders = self._generate_reminders_for_task(task, now)
                for reminder in reminders:
                    if now <= reminder.trigger_time <= cutoff:
                        upcoming.append(reminder)
        
        return sorted(upcoming, key=lambda r: r.trigger_time)

# Utility function to create default sound files (optional)
def create_default_sounds():
    """Create simple beep sounds using pygame if sound files don't exist"""
    if not PYGAME_AVAILABLE:
        return
    
    sound_configs = {
        "due_notification.wav": (800, 0.3),      # 800Hz for 0.3 seconds
        "warning_notification.wav": (600, 0.5),  # 600Hz for 0.5 seconds  
        "overdue_notification.wav": (400, 0.7),  # 400Hz for 0.7 seconds
    }
    
    for filename, (frequency, duration) in sound_configs.items():
        if not os.path.exists(filename):
            try:
                # Generate a simple sine wave tone
                import numpy as np
                sample_rate = 22050
                frames = int(duration * sample_rate)
                arr = np.zeros(frames)
                
                for i in range(frames):
                    arr[i] = np.sin(2 * np.pi * frequency * i / sample_rate)
                
                # Convert to 16-bit integers
                arr = (arr * 32767).astype(np.int16)
                
                # Save as WAV file
                import wave
                with wave.open(filename, 'w') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 2 bytes per sample
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(arr.tobytes())
                
                print(f"Created default sound: {filename}")
            except Exception as e:
                print(f"Could not create sound file {filename}: {e}")

if __name__ == "__main__":
    # Test the reminder system
    create_default_sounds()
    print("Reminder system module loaded successfully!")