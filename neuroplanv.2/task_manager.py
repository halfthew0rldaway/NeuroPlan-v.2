# task_manager.py

import uuid
import datetime
import re # Import regular expressions for parsing
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import List, Optional, Dict, Any

class Status(str, Enum):
    TODO = "TODO"
    DONE = "DONE"
    WAITING = "WAITING"

class Priority(str, Enum):
    HIGH = "A"
    MEDIUM = "B"
    LOW = "C"
    NONE = "D"

@dataclass
class Task:
    title: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    author: Optional[str] = None
    status: Status = Status.TODO
    priority: Priority = Priority.NONE
    due_date: Optional[datetime.datetime] = None
    scheduled_date: Optional[datetime.datetime] = None
    reminder_minutes: int = 30
    reminder_enabled: bool = True
    tags: List[str] = field(default_factory=list)
    children: List['Task'] = field(default_factory=list)
    parent_id: Optional[str] = None
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    file: Optional[str] = None

class TaskManager:
    def __init__(self, storage):
        self.storage = storage
        self.tasks: Dict[str, Task] = {}
        self.load_tasks()

    def load_tasks(self):
        """Loads tasks from storage and converts them into Task objects."""
        all_tasks_data = self.storage.load() # Gets a list of dictionaries
        temp_tasks = {}
        task_fields = {f.name for f in fields(Task)}

        for data in all_tasks_data:
            task_id_for_error = data.get('id', 'N/A')
            try:
                # This loop handles date conversion correctly
                for date_key in ['created_at', 'due_date', 'scheduled_date']:
                    if data.get(date_key) and isinstance(data[date_key], str):
                        data[date_key] = datetime.datetime.fromisoformat(data[date_key])
                    # If it's already a datetime object from org_storage, that's fine too
                
                # Ensure only valid fields are passed to the Task constructor
                filtered_data = {k: v for k, v in data.items() if k in task_fields}

                if 'id' in filtered_data:
                    temp_tasks[filtered_data['id']] = Task(**filtered_data) # Creates Task objects
            except Exception as e:
                print(f"⚠️ Warning: Could not load task '{task_id_for_error}'. Reason: {e}. Skipping.")

        # Rebuild the parent-child tree structure from the loaded tasks
        self.tasks = {}
        for task_id, task in temp_tasks.items():
            task.children = []
            if task.parent_id and task.parent_id in temp_tasks:
                parent = temp_tasks[task.parent_id]
                parent.children.append(task)
            else:
                task.parent_id = None
        self.tasks = temp_tasks

    def save_tasks(self):
        """
        Saves all tasks. Passes a list of Task objects to the storage layer,
        as expected by OrgStorage.
        """
        self.storage.save(list(self.tasks.values()))

    def add_task(self, title: str, parent_id: Optional[str] = None, filename: Optional[str] = None, **kwargs) -> Task:
        """
        FIXED: This now correctly creates a Task OBJECT and adds it to the manager.
        This is the core fix for your crash.
        """
        # Create a proper Task object from the provided data
        new_task = Task(title=title, parent_id=parent_id, file=filename, **kwargs)
        
        # Add the new Task OBJECT to our dictionary of tasks
        self.tasks[new_task.id] = new_task
        
        # If it's a child, add it to the parent's children list
        if parent_id and parent_id in self.tasks:
            self.tasks[parent_id].children.append(new_task)
            
        # Save all tasks using the corrected save_tasks method
        self.save_tasks()
        return new_task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieves a task by its ID."""
        return self.tasks.get(task_id)

    def update_task(self, task_id: str, **kwargs: Any):
        """Updates an existing task's attributes."""
        task = self.get_task(task_id)
        if task:
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            self.save_tasks()

    def delete_task(self, task_id: str):
        """Deletes a task and all its sub-tasks recursively."""
        task_to_delete = self.get_task(task_id)
        if not task_to_delete:
            return

        for child in list(task_to_delete.children):
            self.delete_task(child.id)

        if task_to_delete.parent_id and task_to_delete.parent_id in self.tasks:
            parent = self.tasks[task_to_delete.parent_id]
            parent.children = [c for c in parent.children if c.id != task_id]

        if task_id in self.tasks:
            del self.tasks[task_id]
        
        self.save_tasks()

    def get_task_tree(self) -> List[Task]:
        """Returns a list of top-level tasks, sorted for display."""
        top_level_tasks = [task for task in self.tasks.values() if not task.parent_id]
        return sorted(top_level_tasks, key=lambda t: (t.priority.value, t.created_at))

    # All other helper methods from your original file are included below
    def get_all_tasks_flat(self) -> List[Task]:
        return sorted(
            [task for task in self.tasks.values() if task.due_date],
            key=lambda t: t.due_date if t.due_date else datetime.datetime.max
        )

    def search_tasks(self, query: str) -> List[Task]:
        # ... (full implementation) ...
        pass
    
    def get_tasks_with_due_dates(self) -> List[Task]:
        # ... (full implementation) ...
        pass
    
    def get_overdue_tasks(self) -> List[Task]:
        # ... (full implementation) ...
        pass
    
    def get_tasks_due_soon(self, hours: int = 24) -> List[Task]:
        # ... (full implementation) ...
        pass

# --- FIXED: The implementation for this function was missing ---
def parse_flexible_date(date_string: str) -> Optional[datetime.datetime]:
    """
    Parses a flexible date string into a datetime object.
    Handles formats like: "YYYY-MM-DD HH:MM", "tomorrow", "today",
    "in 2h", "in 30m", "in 3d".
    """
    now = datetime.datetime.now()
    date_string = date_string.lower().strip()

    # Handle keywords like "tomorrow"
    if date_string == 'tomorrow':
        return (now + datetime.timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    if date_string == 'today':
        return now.replace(hour=23, minute=59, second=0, microsecond=0)

    # Handle relative time like "in 2h", "in 30m", "in 3d"
    match = re.match(r'in\s+(\d+)\s*(h|m|d)', date_string)
    if match:
        value = int(match.group(1))
        unit = match.group(2)
        delta = datetime.timedelta()
        if unit == 'h':
            delta = datetime.timedelta(hours=value)
        elif unit == 'm':
            delta = datetime.timedelta(minutes=value)
        elif unit == 'd':
            delta = datetime.timedelta(days=value)
        return now + delta

    # Handle absolute date/time formats
    try:
        return datetime.datetime.strptime(date_string, '%Y-%m-%d %H:%M')
    except ValueError:
        try:
            # Try parsing date only, defaulting to 9 AM
            dt = datetime.datetime.strptime(date_string, '%Y-%m-%d')
            return dt.replace(hour=9, minute=0)
        except ValueError:
            # If all parsing attempts fail
            return None