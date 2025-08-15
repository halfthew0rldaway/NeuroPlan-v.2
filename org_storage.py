# org_storage.py

import os
import datetime
from typing import List, Dict, Any
import orgparse

# Import your Task class definition
from task_manager import Task, Status, Priority

class OrgStorage:
    """Handles saving and loading tasks to/from a directory of .org files."""
    def __init__(self, directory_path: str):
        """
        Initializes the storage handler with a path to the directory for .org files.
        """
        self.directory_path = directory_path
        os.makedirs(self.directory_path, exist_ok=True)

    def load(self) -> List[Dict[str, Any]]:
        """
        Loads tasks from all .org files in the directory.
        Returns a list of dictionaries, where each represents a task.
        """
        all_tasks_data = []
        for filename in os.listdir(self.directory_path):
            if not filename.endswith(".org"):
                continue
            
            file_path = os.path.join(self.directory_path, filename)
            try:
                org_file = orgparse.load(file_path)
            except Exception:
                continue # Skip malformed files

            for node in org_file[1:]: # Skip the root node
                # MODIFIED: Check the object type instead of calling a method
                if not isinstance(node, orgparse.OrgNode):
                    continue

                properties = node.properties
                
                status_val = properties.get("status", "TODO")
                priority_val = properties.get("priority", "D")
                
                due_date = None
                if node.scheduled and node.scheduled.start:
                    due_date = node.scheduled.start
                elif properties.get("due_date"):
                    try:
                        due_date = datetime.datetime.fromisoformat(properties["due_date"])
                    except (ValueError, TypeError):
                        due_date = None
                
                created_at = datetime.datetime.now()
                if properties.get("created_at"):
                    try:
                        created_at = datetime.datetime.fromisoformat(properties["created_at"])
                    except (ValueError, TypeError):
                        pass

                task_dict = {
                    "id": properties.get("id", "N/A"),
                    "title": node.heading,
                    "description": node.body,
                    "author": properties.get("author"),
                    "status": Status(status_val),
                    "priority": Priority(priority_val),
                    "due_date": due_date,
                    "tags": list(node.tags),
                    "parent_id": properties.get("parent_id"),
                    "created_at": created_at,
                    "file": filename
                }
                all_tasks_data.append(task_dict)
                
        return all_tasks_data

    def save(self, tasks: List[Task]):
        """Saves a list of tasks back to their respective .org files."""
        tasks_by_file = {}
        for task in tasks:
            filename = getattr(task, 'file', 'tasks.org')
            if filename not in tasks_by_file:
                tasks_by_file[filename] = []
            tasks_by_file[filename].append(task)
            
        for filename, file_tasks in tasks_by_file.items():
            file_path = os.path.join(self.directory_path, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"#+TITLE: {filename.replace('.org', '')}\n\n")
                for task in sorted(file_tasks, key=lambda t: t.created_at):
                    self._write_task_node(f, task)

    def _write_task_node(self, file_handle, task: Task, level=1):
        """Recursively writes a task and its children to the file."""
        stars = "*" * level
        status = f"{task.status.value} " if task.status != Status.TODO else ""
        tags = f":{':'.join(task.tags)}:" if task.tags else ""
        
        file_handle.write(f"{stars} {status}{task.title} {tags}\n")

        if task.due_date:
            file_handle.write(f"SCHEDULED: <{task.due_date.strftime('%Y-%m-%d %a %H:%M')}>\n")

        file_handle.write(":PROPERTIES:\n")
        file_handle.write(f":id: {task.id}\n")
        if task.parent_id:
            file_handle.write(f":parent_id: {task.parent_id}\n")
        if task.author:
            file_handle.write(f":author: {task.author}\n")
        file_handle.write(f":status: {task.status.value}\n")
        file_handle.write(f":priority: {task.priority.value}\n")
        file_handle.write(f":created_at: {task.created_at.isoformat()}\n")
        file_handle.write(":END:\n\n")
        
        if task.description:
            file_handle.write(f"{task.description.strip()}\n\n")
        
        if task.children:
            for child in sorted(task.children, key=lambda t: t.created_at):
                self._write_task_node(file_handle, child, level + 1)