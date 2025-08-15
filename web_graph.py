# web_graph.py

import json
import re
import os
from pathlib import Path
from task_manager import TaskManager, Task

# ADDED: The same JsonStorage class from app.py to correctly handle the task file.
class JsonStorage:
    def __init__(self, filepath):
        self.filepath = Path(filepath)

    def load(self):
        if not self.filepath.exists():
            return []
        with open(self.filepath, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

    def save(self, tasks_data):
        tasks_as_dicts = [task.__dict__ for task in tasks_data]
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(tasks_as_dicts, f, indent=4, default=str)


def generate_web_graph(task_manager: TaskManager, central_node_id: str = None, output_dir: str = "."):
    """
    Generates the graph data in the root directory.
    """
    
    # This now correctly places graph_data.json in the project root.
    output_path = Path(output_dir)
    graph_data_path = output_path / "graph_data.json"
    
    print(f"Generating graph data...")
    
    graph_data = _build_graph_data(task_manager, central_node_id)
    
    with open(graph_data_path, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, indent=2, ensure_ascii=False)
    
    print(f"Graph data saved to: {graph_data_path}")
    print(f"Nodes: {len(graph_data['nodes'])}, Links: {len(graph_data['links'])}")
    
    return {
        "graph_data_path": str(graph_data_path),
        "node_count": len(graph_data['nodes']),
        "link_count": len(graph_data['links'])
    }

def _build_graph_data(task_manager: TaskManager, central_node_id: str = None):
    """Build the graph data structure from task manager."""
    
    tasks = list(task_manager.tasks.values())
    
    if not tasks:
        print("Warning: No tasks found in task manager")
        return {"nodes": [], "links": []}
    
    nodes = []
    for task in tasks:
        node_data = {
            "id": task.id,
            "title": task.title,
            "author": task.author or "Unknown",
            "description": task.description or "No description available.",
            "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
            "created_at": task.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(task, 'created_at') and task.created_at else "Unknown",
            "isCentral": task.id == central_node_id,
            "val": 50 if task.id == central_node_id else 15,
            "parent_id": task.parent_id
        }
        nodes.append(node_data)
    
    links = []
    for task in tasks:
        if task.parent_id and task.parent_id in task_manager.tasks:
            links.append({
                "source": task.id, 
                "target": task.parent_id, 
                "type": "parent"
            })
            
    return {"nodes": nodes, "links": links}


# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate NeuroPlan 3D Web Graph')
    parser.add_argument('--task-file', required=True, help='Path to task storage file')
    parser.add_argument('--central-node', help='ID of central node to highlight')
    parser.add_argument('--output-dir', default='.', help='Output directory for graph data')
    parser.add_argument('--no-server', action='store_true', help='Do not launch a web server')
    
    args = parser.parse_args()
    
    # FIXED: This now creates the storage object before passing it to the TaskManager.
    print(f"Loading tasks from: {args.task_file}")
    storage = JsonStorage(args.task_file)
    task_manager = TaskManager(storage)
    
    if not task_manager.tasks:
        print("Error: No tasks found in the task file")
        exit(1)
    
    # Generate graph
    result = generate_web_graph(task_manager, args.central_node, args.output_dir)
    
    print(f"\nGraph generated with {result['node_count']} nodes and {result['link_count']} links")
    
    if not args.no_server:
        # This part is not needed if you use app.py, but is kept for completeness
        import http.server
        import socketserver
        print(f"\nServing files from the root directory on port 8000")
        print("Run `python app.py` for the full interactive experience.")
        with socketserver.TCPServer(("", 8000), http.server.SimpleHTTPRequestHandler) as httpd:
            httpd.serve_forever()
    else:
        print(f"Graph file ready at: {result['graph_data_path']}")
        print("Run `python app.py` to start the web server.")