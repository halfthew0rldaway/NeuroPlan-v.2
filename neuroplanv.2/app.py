# app.py

import threading
import logging
import requests
from flask import Flask, jsonify, render_template

# --- 1. Set up logging to a file ---
# This will capture all messages instead of printing them to the screen.
logging.basicConfig(
    filename='server.log', 
    level=logging.INFO, 
    format='%(asctime)s - %(message)s'
)
# Silence the default Werkzeug logger from printing to the console
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.ERROR)


task_manager_instance = None 

# --- Your data generation function (unchanged) ---
def build_graph_data_live(tm):
    if not tm:
        return {"nodes": [], "links": []}
    
    tasks = list(tm.tasks.values())
    nodes, links = [], []
    task_ids = {task.id for task in tasks}

    for task in tasks:
        has_children = any(t.parent_id == task.id for t in tasks)
        nodes.append({
            "id": task.id, "title": task.title, "author": task.author or "Unknown",
            "description": task.description, "status": task.status.value,
            "created_at": task.created_at.strftime('%Y-%m-%d %H:%M') if task.created_at else "Unknown",
            "filename": getattr(task, 'file', "N/A"),
            "val": 30 if has_children else 15
        })
        if task.parent_id and task.parent_id in task_ids:
            links.append({"source": task.id, "target": task.parent_id})
            
    return {"nodes": nodes, "links": links}

# --- Server Control Class ---
class FlaskServerThread(threading.Thread):
    def __init__(self, tm, host='127.0.0.1', port=5001):
        super().__init__()
        global task_manager_instance
        task_manager_instance = tm 
        
        self.app = Flask(__name__, template_folder='web/templates', static_folder='web/static')
        self.host = host
        self.port = port
        self.server = None
        self.setup_routes()

    def setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template('index.html')

        @self.app.route('/api/graph-data')
        def get_graph_data():
            global task_manager_instance
            graph_data = build_graph_data_live(task_manager_instance)
            return jsonify(graph_data)

        @self.app.route('/shutdown')
        def shutdown_route():
            if self.server:
                self.server.shutdown()
            return 'Server shutting down...'

    def run(self):
        from werkzeug.serving import make_server
        self.server = make_server(self.host, self.port, self.app)
        with self.app.app_context():
            # --- Use logging instead of print ---
            logging.info(f"Starting Flask server on http://{self.host}:{self.port}")
            self.server.serve_forever()

    def shutdown_server(self):
        """Triggers the shutdown by making a request to the /shutdown route."""
        # --- Use logging instead of print ---
        logging.info("Shutting down Flask server...")
        try:
            requests.get(f'http://{self.host}:{self.port}/shutdown', timeout=1)
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
            pass