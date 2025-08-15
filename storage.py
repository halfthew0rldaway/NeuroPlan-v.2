# storage.py
#
# Description:
# This file handles the persistence of task data. It provides a class
# for saving tasks to and loading tasks from a JSON file. This abstracts
# the file I/O operations away from the main application logic.
#

import json
import datetime
from typing import List, Dict, Any
from task_manager import Task, Status, Priority

class TaskEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Task objects and other custom types."""
    def default(self, obj):
        if isinstance(obj, Task):
            # Exclude children from serialization; structure is rebuilt on load
            task_dict = {
                'id': obj.id,
                'title': obj.title,
                'description': obj.description,
                'author': getattr(obj, 'author', None), # NEW: Safely get author
                'status': obj.status.value,
                'priority': obj.priority.value,
                'due_date': obj.due_date.isoformat() if obj.due_date else None,
                'tags': obj.tags,
                'parent_id': obj.parent_id,
                'created_at': obj.created_at.isoformat()
            }
            return task_dict
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if isinstance(obj, (Status, Priority)):
            return obj.value
        return super().default(obj)

def task_decoder(task_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Custom decoder hook for loading task data from JSON."""
    
    # NEW: Ensure author field exists, defaulting to None if loading old data
    if 'author' not in task_dict:
        task_dict['author'] = None
        
    for key, value in task_dict.items():
        if key == 'due_date' and value:
            task_dict[key] = datetime.datetime.fromisoformat(value)
        if key == 'created_at' and value:
            task_dict[key] = datetime.datetime.fromisoformat(value)
        if key == 'status' and value:
            task_dict[key] = Status(value)
        if key == 'priority' and value:
            task_dict[key] = Priority(value)
    return task_dict

class JsonStorage:
    """Handles saving and loading tasks to/from a JSON file."""
    def __init__(self, filepath: str):
        """
        Initializes the storage handler with a path to the data file.
        
        Args:
            filepath: The path to the JSON file where tasks are stored.
        """
        self.filepath = filepath

    def load(self) -> List[Dict[str, Any]]:
        """
        Loads tasks from the JSON file.
        
        Returns:
            A list of dictionaries, where each dictionary represents a task.
            Returns an empty list if the file doesn't exist or is empty.
        """
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f, object_hook=task_decoder)
                # Ensure we return a list, even if file is empty or malformed
                return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save(self, tasks: List[Task]):
        """
        Saves a list of tasks to the JSON file.
        
        Args:
            tasks: A list of Task objects to be saved.
        """
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, cls=TaskEncoder, indent=4)