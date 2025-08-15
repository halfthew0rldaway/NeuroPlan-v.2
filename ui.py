# ui.py - Updated with a robust custom text editor

import curses
import curses.textpad
import textwrap
import webbrowser
import http.server
import socketserver
import threading
import time
import re
import datetime

from app import FlaskServerThread
from task_manager import Task, Status, Priority, parse_flexible_date
# NEW: Import the dashboard view
from dashboard_view import DashboardView
# NEW: Import search and help views
from search_view import SearchView
from help_view import HelpView
# NEW: Import animation view
from animation_view import AnimationView

try:
    from web_graph import generate_web_graph
except ImportError:
    def generate_web_graph(*args, **kwargs):
        print("web_graph module not available")

# --- Server for Web Graph ---
PORT = 8000
httpd = None
server_thread = None

def start_server():
    global httpd, server_thread
    if httpd is None:
        handler = http.server.SimpleHTTPRequestHandler
        httpd = socketserver.TCPServer(("", PORT), handler)
        server_thread = threading.Thread(target=httpd.serve_forever)
        server_thread.daemon = True
        server_thread.start()

def stop_server():
    global httpd
    if httpd:
        httpd.shutdown()
        httpd.server_close()
        httpd = None

class App:
    def __init__(self, stdscr, task_manager, height, width, reminder_system=None):
        self.stdscr = stdscr
        self.task_manager = task_manager
        self.height, self.width = height, width
        self.reminder_system = reminder_system
        
        self.running = True
        self.theme = {}
        self.active_pane = 'list'
        self.list_scroll_offset = 0
        self.detail_scroll_offset = 0
        self.selected_index = 0
        self.planner_tasks = []
        
        # NEW: Tree folding state - keeps track of collapsed task IDs
        self.collapsed_tasks = set()
        
        self.is_input_mode = False
        self.input_fields = []
        self.input_data = {}
        self.current_input_field_index = 0
        self.current_input = ""
        self.on_input_complete = None
        
        # Quick capture mode
        self.is_quick_capture = False
        self.quick_capture_text = ""
        
        # Reminder system integration
        self.show_reminders_pane = False
        
        # NEW: Flask server management
        self.flask_server = None
        self.flask_server_running = False
        self.last_update_time = time.time()
        self.update_interval = 1.0  # Update every 1.0 second
        self.needs_redraw = True

        self.stdscr.keypad(True)
        self.setup_colors()
        self.list_win, self.detail_win, self.input_win = None, None, None

        # NEW: Add state for current view and instantiate views
        self.current_view = 'dashboard'  # Can be 'tasks', 'dashboard', 'search', 'help', 'animation'
        self.dashboard_view = DashboardView(self.stdscr, self.task_manager, self.theme)
        self.search_view = SearchView(self.stdscr, self.task_manager, self.theme)
        self.help_view = HelpView(self.stdscr, self.theme)
        self.animation_view = AnimationView(self.stdscr, self.theme)
        

    # in ui.py

    def setup_colors(self):
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_WHITE, -1)
            curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_GREEN)
            curses.init_pair(3, curses.COLOR_MAGENTA, -1)
            curses.init_pair(4, curses.COLOR_YELLOW, -1)
            curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN)  # Quick capture
            curses.init_pair(6, curses.COLOR_RED, -1)    # Overdue
            curses.init_pair(7, curses.COLOR_CYAN, -1)   # Due soon
            
            # NEW: Animation and status colors
            curses.init_pair(8, curses.COLOR_RED, -1)
            curses.init_pair(9, curses.COLOR_BLUE, -1)
            curses.init_pair(10, curses.COLOR_MAGENTA, -1)
            curses.init_pair(11, curses.COLOR_GREEN, -1) # --- NEW: Green color for 'DONE' status ---
            
            self.theme = {
                'default': curses.color_pair(1),
                'highlight': curses.color_pair(2),
                'author': curses.color_pair(3) | curses.A_BOLD,
                'comment': curses.color_pair(4),
                'title': curses.color_pair(1) | curses.A_BOLD,
                'done': curses.color_pair(11), # --- CHANGED: from dim white to green ---
                'capture': curses.color_pair(5) | curses.A_BOLD,
                'overdue': curses.color_pair(6) | curses.A_BOLD,
                'due_soon': curses.color_pair(7) | curses.A_BOLD,
                'anim_red': curses.color_pair(8),
                'anim_blue': curses.color_pair(9),
                'anim_purple': curses.color_pair(10),
            }
    def _get_color(self, name): 
        return self.theme.get(name, curses.A_NORMAL)

    def start_flask_server(self):
        """Start the Flask server if not already running"""
        if not self.flask_server_running:
            try:
                # Create and start Flask server thread
                self.flask_server = FlaskServerThread(self.task_manager, host='127.0.0.1', port=5001)
                self.flask_server.daemon = True  # Dies when main program exits
                self.flask_server.start()
                self.flask_server_running = True
                
                # Give server time to start
                time.sleep(1.5)
                
                # Open browser
                webbrowser.open('http://127.0.0.1:5001')
                
                self._show_message("Graph view opened in browser")
                
            except Exception as e:
                self._show_message(f"Failed to start server: {str(e)}")
        else:
            # Server already running, just open browser
            webbrowser.open('http://127.0.0.1:5001')
            self._show_message("Graph view opened (server already running)")

    def stop_flask_server(self):
        """Stop the Flask server"""
        if self.flask_server_running and self.flask_server:
            try:
                self.flask_server.shutdown_server()
                self.flask_server_running = False
                self._show_message("Graph server stopped")
            except Exception as e:
                self._show_message(f"Error stopping server: {str(e)}")

    def toggle_task_fold(self):
        """Toggle folding/expanding of the selected task's children"""
        if not self.planner_tasks or self.selected_index >= len(self.planner_tasks):
            return
        
        task = self.planner_tasks[self.selected_index]['task']
        
        # Only allow folding if the task has children
        if not task.children:
            return
        
        task_id = task.id
        if task_id in self.collapsed_tasks:
            # Expand - remove from collapsed set
            self.collapsed_tasks.remove(task_id)
        else:
            # Collapse - add to collapsed set
            self.collapsed_tasks.add(task_id)
        
        self.needs_redraw = True

    def show_upcoming_reminders(self):
        """Display upcoming reminders in a modal window"""
        if not self.reminder_system:
            self._show_message("Reminder system not available")
            return
        
        upcoming = self.reminder_system.get_upcoming_reminders(24)  # Next 24 hours
        
        if not upcoming:
            self._show_message("No upcoming reminders in the next 24 hours")
            return
        
        # Create reminder display window
        reminder_h = min(self.height - 4, len(upcoming) + 6)
        reminder_w = min(self.width - 4, 80)
        reminder_y = (self.height - reminder_h) // 2
        reminder_x = (self.width - reminder_w) // 2
        
        reminder_win = curses.newwin(reminder_h, reminder_w, reminder_y, reminder_x)
        reminder_win.bkgd(' ', self._get_color('default'))
        reminder_win.box()
        reminder_win.addstr(0, 2, " Upcoming Reminders (24h) ", self._get_color('title') | curses.A_BOLD)
        
        # Display reminders
        y_pos = 2
        for i, reminder in enumerate(upcoming[:reminder_h - 4]):
            task_id = reminder.task_id.split('_')[0]
            task = self.task_manager.get_task(task_id)
            
            if task:
                time_str = reminder.trigger_time.strftime("%m/%d %H:%M")
                type_str = reminder.reminder_type.value.replace('_', ' ').title()
                
                line = f"{time_str} - {type_str}: {task.title[:40]}"
                if len(task.title) > 40:
                    line += "..."
                
                # Color code by reminder type
                color = self._get_color('default')
                if reminder.reminder_type.value == 'overdue':
                    color = self._get_color('overdue')
                elif reminder.reminder_type.value == 'before_due':
                    color = self._get_color('due_soon')
                
                reminder_win.addstr(y_pos + i, 2, line[:reminder_w - 4], color)
        
        reminder_win.addstr(reminder_h - 2, 2, "Press any key to close", self._get_color('comment'))
        reminder_win.refresh()
        
        # Wait for key press
        reminder_win.getch()
        self.needs_redraw = True

    def _show_message(self, message: str, duration: float = 1.5):
        """Show a temporary message modal"""
        msg_h, msg_w = 5, min(len(message) + 4, self.width - 4)
        msg_y, msg_x = (self.height - msg_h) // 2, (self.width - msg_w) // 2
        
        msg_win = curses.newwin(msg_h, msg_w, msg_y, msg_x)
        msg_win.bkgd(' ', self._get_color('default'))
        msg_win.box()
        msg_win.addstr(2, 2, message[:msg_w - 4], self._get_color('comment'))
        msg_win.refresh()
        
        # Show for specified duration
        time.sleep(duration)
        self.needs_redraw = True

    def set_due_date_for_task(self, task_id: str):
        """Interactive due date setting for a task"""
        task = self.task_manager.get_task(task_id)
        if not task:
            return
        
        # Simple date/time input fields
        current_due = task.due_date.strftime("%Y-%m-%d %H:%M") if task.due_date else ""
        
        fields = [
            ('due_date_str', f'Due Date/Time for "{task.title[:30]}" (YYYY-MM-DD HH:MM, or "tomorrow", "in 2h", etc.)')
        ]
        
        def on_complete(data):
            due_date_str = data.get('due_date_str', '').strip()
            if due_date_str:
                try:
                    # Parse the date string using the flexible parser
                    due_date = parse_flexible_date(due_date_str)
                    if due_date:
                        self.task_manager.update_task(task_id, due_date=due_date)
                        self._show_message(f"Due date set for {due_date.strftime('%Y-%m-%d %H:%M')}")
                    else:
                        self._show_message("Invalid date format")
                except Exception as e:
                    self._show_message(f"Error parsing date: {str(e)}")
            else:
                # Clear due date
                self.task_manager.update_task(task_id, due_date=None)
                self._show_message("Due date cleared")
        
        initial_data = {'due_date_str': current_due}
        self.start_input_session(fields, on_complete, initial_data)

    def toggle_reminder_system(self):
        """Toggle the reminder system on/off"""
        if not self.reminder_system:
            self._show_message("Reminder system not available")
            return
        
        if self.reminder_system.running:
            self.reminder_system.stop()
            self._show_message("Reminder system stopped")
        else:
            self.reminder_system.start()
            self._show_message("Reminder system started")

    def show_task_reminder_settings(self, task_id: str):
        """Show reminder settings for a specific task"""
        task = self.task_manager.get_task(task_id)
        if not task:
            return
        
        current_minutes = str(getattr(task, 'reminder_minutes', 30))
        current_enabled = "yes" if getattr(task, 'reminder_enabled', True) else "no"
        
        fields = [
            ('reminder_minutes', f'Minutes before due date to remind for "{task.title[:30]}"'),
            ('reminder_enabled', 'Enable reminders? (yes/no)')
        ]
        
        def on_complete(data):
            try:
                minutes = int(data.get('reminder_minutes', '30'))
                enabled = data.get('reminder_enabled', 'yes').lower() in ['yes', 'y', 'true', '1']
                
                self.task_manager.update_task(task_id, 
                                            reminder_minutes=max(1, minutes),
                                            reminder_enabled=enabled)
                
                status = "enabled" if enabled else "disabled"
                self._show_message(f"Reminders {status}, {minutes} min before due")
            except ValueError:
                self._show_message("Invalid reminder minutes - must be a number")
        
        initial_data = {
            'reminder_minutes': current_minutes,
            'reminder_enabled': current_enabled
        }
        self.start_input_session(fields, on_complete, initial_data)

   # in ui.py

    def run_textbox_editor(self, initial_text="", title="Description Editor"):
        editor_h, editor_w = self.height - 4, self.width - 4
        editor_y, editor_x = 2, 2
        editwin = curses.newwin(editor_h, editor_w, editor_y, editor_x)
        editwin.bkgd(' ', self._get_color('default'))
        
        # Draw styled border for the main editor frame
        editwin.attron(self._get_color('title'))
        editwin.box()
        editwin.attroff(self._get_color('title'))
        
        # Header with title
        editwin.addstr(0, 2, f" {title} ", self._get_color('title') | curses.A_BOLD)
        
        # Instructions at bottom
        use_syntax_highlighting = "Quick Capture" in title
        if use_syntax_highlighting:
            instructions = "#+TITLE: | #+AUTHOR: | Ctrl+G: Save | Ctrl+C: Cancel"
        else:
            instructions = "Ctrl+G: Save & Exit | Ctrl+C: Cancel"
            
        if len(instructions) < editor_w - 4:
            editwin.addstr(editor_h - 1, 2, instructions, self._get_color('comment'))
        
        # Corner decorations
        try:
            editwin.addch(0, 0, curses.ACS_ULCORNER, self._get_color('title'))
            editwin.addch(0, editor_w - 1, curses.ACS_URCORNER, self._get_color('title'))
            editwin.addch(editor_h - 1, 0, curses.ACS_LLCORNER, self._get_color('title'))
            editwin.addch(editor_h - 1, editor_w - 1, curses.ACS_LRCORNER, self._get_color('title'))
        except curses.error:
            pass
        
        # Create inner window for text editing with padding
        # It's smaller to fit inside the main editor's border
        inner_win_h, inner_win_w = editor_h - 2, editor_w - 2
        inner_win_y, inner_win_x = editor_y + 1, editor_x + 1
        inner_win = curses.newwin(inner_win_h, inner_win_w, inner_win_y, inner_win_x)
        inner_win.bkgd(' ', self._get_color('default'))
        
        # --- NEW: Pass the parent window to the editor for the char counter ---
        content = self._run_custom_editor(
            win=inner_win, 
            parent_win=editwin, # Pass the outer frame
            initial_text=initial_text, 
            syntax_highlighting=use_syntax_highlighting
        )
        
        editwin.refresh()
        self.needs_redraw = True 
        return content.strip() if content else ""

    def _run_custom_editor(self, win, parent_win, initial_text, syntax_highlighting=False):
        """
        A robust custom text editor that handles insert mode correctly.
        Now includes a border and character counter.
        """
        MAX_CHARS = 2048 # --- NEW: Set a maximum character limit ---
        
        p_height, p_width = parent_win.getmaxyx()
        max_height, max_width = win.getmaxyx()
        max_height -= 2 # Adjust for the new border
        max_width -= 2
        
        lines = initial_text.split('\n') if initial_text else [""]
        cursor_y, cursor_x = 0, 0
        scroll_offset = 0
        
        if initial_text:
            cursor_y = len(lines) - 1
            cursor_x = len(lines[cursor_y])
            
        # --- NEW: Helper function to update the character counter ---
        def update_char_counter():
            current_chars = sum(len(line) for line in lines)
            counter_str = f" {current_chars}/{MAX_CHARS} "
            
            color = self._get_color('comment')
            if current_chars > MAX_CHARS:
                color = self._get_color('overdue') # Red
            elif current_chars > MAX_CHARS * 0.9:
                color = self._get_color('due_soon') # Yellow/Cyan
            
            parent_win.addstr(p_height - 1, p_width - len(counter_str) - 2, counter_str, color)
            parent_win.refresh()

        def refresh_display():
            win.erase()
            # --- NEW: Draw a box around the actual text area ---
            win.box() 
            
            # Draw text content inside the box
            for i, line in enumerate(lines[scroll_offset:]):
                if i >= max_height:
                    break
                display_line = line[:max_width]
                
                y_pos, x_pos = i + 1, 1 # Offset by 1 for the border
                
                if syntax_highlighting:
                    if display_line.startswith('#+TITLE:'):
                        win.addstr(y_pos, x_pos, '#+TITLE:', self._get_color('highlight'))
                        if len(display_line) > 8:
                            win.addstr(y_pos, x_pos + 8, display_line[8:], self._get_color('default'))
                    elif display_line.startswith('#+AUTHOR:'):
                        win.addstr(y_pos, x_pos, '#+AUTHOR:', self._get_color('author'))
                        if len(display_line) > 9:
                            win.addstr(y_pos, x_pos + 9, display_line[9:], self._get_color('default'))
                    else:
                        win.addstr(y_pos, x_pos, display_line, self._get_color('default'))
                else:
                    win.addstr(y_pos, x_pos, display_line, self._get_color('default'))
            
            if not any(lines):
                 win.addstr(1, 1, "Start typing here...", self._get_color('comment'))

            # Position cursor, accounting for the border
            display_y = cursor_y - scroll_offset
            if 0 <= display_y < max_height:
                win.move(display_y + 1, min(cursor_x, max_width - 1) + 1)
            win.refresh()
        
        win.keypad(True)
        
        # Initial draw
        refresh_display()
        update_char_counter()
        
        while True:
            try:
                key = win.getch()
                
                # --- NEW: Flag to check if text was modified ---
                text_changed = False
                
                if key == 7: break
                elif key == 3: return ""
                elif key == curses.KEY_UP:
                    if cursor_y > 0:
                        cursor_y -= 1
                        cursor_x = min(cursor_x, len(lines[cursor_y]))
                elif key == curses.KEY_DOWN:
                    if cursor_y < len(lines) - 1:
                        cursor_y += 1
                        cursor_x = min(cursor_x, len(lines[cursor_y]))
                elif key == curses.KEY_LEFT:
                    if cursor_x > 0: cursor_x -= 1
                    elif cursor_y > 0:
                        cursor_y -= 1
                        cursor_x = len(lines[cursor_y])
                elif key == curses.KEY_RIGHT:
                    if cursor_x < len(lines[cursor_y]): cursor_x += 1
                    elif cursor_y < len(lines) - 1:
                        cursor_y += 1
                        cursor_x = 0
                elif key in [curses.KEY_ENTER, 10, 13]:
                    current_line = lines[cursor_y]
                    lines[cursor_y] = current_line[:cursor_x]
                    lines.insert(cursor_y + 1, current_line[cursor_x:])
                    cursor_y += 1
                    cursor_x = 0
                    text_changed = True
                elif key in [curses.KEY_BACKSPACE, 127, 8]:
                    if cursor_x > 0:
                        line = lines[cursor_y]
                        lines[cursor_y] = line[:cursor_x-1] + line[cursor_x:]
                        cursor_x -= 1
                    elif cursor_y > 0:
                        cursor_x = len(lines[cursor_y - 1])
                        lines[cursor_y - 1] += lines[cursor_y]
                        del lines[cursor_y]
                        cursor_y -= 1
                    text_changed = True
                elif key and 32 <= key <= 255:
                    # --- NEW: Only add character if under the limit ---
                    if sum(len(l) for l in lines) < MAX_CHARS:
                        line = lines[cursor_y]
                        lines[cursor_y] = line[:cursor_x] + chr(key) + line[cursor_x:]
                        cursor_x += 1
                        text_changed = True
                
                if cursor_y < scroll_offset: scroll_offset = cursor_y
                elif cursor_y >= scroll_offset + max_height:
                    scroll_offset = cursor_y - max_height + 1
                
                refresh_display()
                
                # --- NEW: Update counter only when text changes ---
                if text_changed:
                    update_char_counter()
                
            except (curses.error, KeyboardInterrupt):
                continue
        
        return '\n'.join(lines)

    def show_quick_capture(self):
        """Show modal quick capture overlay"""
        self.is_quick_capture = True
        captured_text = self.run_textbox_editor("", "Quick Capture - Use #+TITLE: and #+AUTHOR: for metadata")
        
        if captured_text.strip():
            # Parse metadata from captured text
            lines = captured_text.split('\n')
            title = None
            author = None
            description_lines = []
            
            for line in lines:
                line_stripped = line.strip()
                if line_stripped.startswith('#+TITLE:'):
                    title = line_stripped[8:].strip()
                elif line_stripped.startswith('#+AUTHOR:'):
                    author = line_stripped[9:].strip()
                else:
                    description_lines.append(line)
            
            # Clean up description (remove empty lines at start/end)
            description = '\n'.join(description_lines).strip()
            
            # Use first line as title if no #+TITLE: found
            if not title and description:
                first_line = description.split('\n')[0].strip()
                title = first_line[:50] + "..." if len(first_line) > 50 else first_line
                # Remove first line from description if used as title
                remaining_lines = description.split('\n')[1:]
                description = '\n'.join(remaining_lines).strip()
            
            # Fallback title
            if not title:
                title = "Quick Note"
            
            # Save to captures.org file
            self.task_manager.add_task(
                title=title,
                author=author,
                description=description,
                filename="captures.org"
            )
        
        self.is_quick_capture = False
        self.needs_redraw = True

    def start_input_session(self, fields, callback, initial_data=None):
        self.is_input_mode = True
        self.input_fields = fields
        self.input_data = initial_data.copy() if initial_data else {}
        self.current_input_field_index = 0
        self.on_input_complete = callback
        
        # Initialize current input with existing data if available
        field_key, _ = self.input_fields[0]
        self.current_input = self.input_data.get(field_key, "")
        self.needs_redraw = True

    def handle_input(self, key):
        if self.is_input_mode: 
            self.handle_input_mode(key)
        elif self.current_view == 'dashboard':
            # Pass input to the dashboard view
            if self.dashboard_view.handle_input(key):
                self.needs_redraw = True
            elif key == ord('q'):
                self.running = False
            elif key == 2: # Ctrl+B
                self.current_view = 'tasks'
                self.needs_redraw = True
            elif key == ord('?'):
                self.help_view.set_context('dashboard')
                self.current_view = 'help'
                self.needs_redraw = True
        elif self.current_view == 'search':
            # NEW: Handle search view input
            selected_task_id = self.search_view.handle_input(key)
            if selected_task_id:
                # Task was selected - go to it in main view
                self.current_view = 'tasks'
                # Find the task in our planner_tasks and select it
                for i, item in enumerate(self.planner_tasks):
                    if item['id'] == selected_task_id:
                        self.selected_index = i
                        break
                self.needs_redraw = True
            elif key == 27:  # ESC - exit search
                self.current_view = 'tasks' 
                self.needs_redraw = True
            elif key == ord('?'):
                self.help_view.set_context('search')
                self.current_view = 'help'
                self.needs_redraw = True
            else:
                self.needs_redraw = True
        elif self.current_view == 'help':
            # NEW: Handle help view - any key exits
            self.current_view = 'tasks'  # Go back to previous view
            self.needs_redraw = True
        elif self.current_view == 'animation':
            # Any key exits animation view
            if self.animation_view.handle_input(key):
                self.current_view = 'tasks'
                self.needs_redraw = True
        else: 
            self.handle_navigation_mode(key)

    def handle_navigation_mode(self, key):
        num_tasks = len(self.planner_tasks)
        if key == ord('q'): 
            self.running = False
        elif key == 1: # Ctrl+A for Animation
            self.current_view = 'animation'
            self.animation_view.reset()
        # NEW: Keybinding to switch to dashboard view (Ctrl+B for "Board")
        elif key == 2: # Ctrl+B
            self.current_view = 'dashboard'
        # NEW: Search view (/ key)
        elif key == ord('/'):
            self.search_view.activate()
            self.current_view = 'search'
        # NEW: Help view (? key)
        elif key == ord('?'):
            self.help_view.set_context('tasks')
            self.current_view = 'help'
        # NEW: Tree folding with Ctrl+Space
        elif key == 0:  # Ctrl+Space (appears as null character)
            self.toggle_task_fold()
        elif key == 14:  # Ctrl+N - Quick Capture
            self.show_quick_capture()
        elif key == 9: 
            self.active_pane = 'detail' if self.active_pane == 'list' else 'list'
        elif key in [curses.KEY_DOWN, ord('j')]:
            if self.active_pane == 'list' and self.selected_index < num_tasks - 1:
                self.selected_index += 1
                self.detail_scroll_offset = 0
            else: 
                self.detail_scroll_offset += 1
        elif key in [curses.KEY_UP, ord('k')]:
            if self.active_pane == 'list' and self.selected_index > 0:
                self.selected_index -= 1
                self.detail_scroll_offset = 0
            elif self.detail_scroll_offset > 0: 
                self.detail_scroll_offset -= 1
        elif key == ord(' '):
             if num_tasks > 0:
                task = self.planner_tasks[self.selected_index]['task']
                new_status = Status.DONE if task.status != Status.DONE else Status.TODO
                self.task_manager.update_task(task.id, status=new_status)
        elif key == ord('x'):
            if num_tasks > 0:
                self.task_manager.delete_task(self.planner_tasks[self.selected_index]['id'])
                self.selected_index = max(0, self.selected_index - 1)
        elif key == ord('e'):
            if num_tasks > 0:
                task = self.planner_tasks[self.selected_index]['task']
                fields = [('title', 'Title'), ('description', 'Description')]
                initial_data = {'title': task.title, 'description': task.description}
                def on_complete(data): 
                    self.task_manager.update_task(task.id, **data)
                self.start_input_session(fields, on_complete, initial_data)
        elif key == ord('a'):
            fields = [('title', 'Title'), ('author', 'Author'), ('description', 'Description')]
            def on_complete(data):
                if not data.get('title'): 
                    return
                s = data['title'].strip().lower()
                s = re.sub(r'[^\w\s-]', '', s)
                s = re.sub(r'[\s_-]+', '-', s)
                data['filename'] = f"{s}.org"
                self.task_manager.add_task(**data)
            self.start_input_session(fields, on_complete)
        elif key == ord('i'):
            if num_tasks > 0:
                parent_item = self.planner_tasks[self.selected_index]
                fields = [('title', 'Child Title'), ('author', 'Author'), ('description', 'Description')]
                def on_complete(data):
                    if not data.get('title'): 
                        return
                    data['parent_id'] = parent_item['id']
                    data['filename'] = parent_item['task'].file
                    self.task_manager.add_task(**data)
                self.start_input_session(fields, on_complete)
        elif key == ord('d'):  # Set due date
            if num_tasks > 0:
                task_id = self.planner_tasks[self.selected_index]['id']
                self.set_due_date_for_task(task_id)
        elif key == ord('r'):  # Show upcoming reminders
            self.show_upcoming_reminders()
        elif key == ord('R'):  # Toggle reminder system
            self.toggle_reminder_system()
        elif key == ord('m'):  # Reminder settings for current task
            if num_tasks > 0:
                task_id = self.planner_tasks[self.selected_index]['id']
                self.show_task_reminder_settings(task_id)
        elif key == ord('g'):  # NEW: Start Flask server and open graph view
            self.start_flask_server()
        elif key == ord('G'):  # NEW: Stop Flask server
            self.stop_flask_server()
        
        self.needs_redraw = True

    def handle_input_mode(self, key):
        # ESC key to cancel input
        if key == 27:  
            self.is_input_mode = False
            self.needs_redraw = True
            return

        # Safety check
        if not self.is_input_mode or self.current_input_field_index >= len(self.input_fields):
            self.is_input_mode = False
            self.needs_redraw = True
            return

        current_field_key, _ = self.input_fields[self.current_input_field_index]

        # Handle the special 'description' field with full editor
        if current_field_key == 'description':
            # Enter to open editor
            if key == curses.KEY_ENTER or key in [10, 13]:
                # Open the full text editor, passing in the currently stored description
                self.input_data[current_field_key] = self.run_textbox_editor(
                    self.input_data.get(current_field_key, ""),
                    title="Description Editor"
                )
                # Move to next field or complete
                self._advance_to_next_field()
        else:
            # Handle regular single-line text fields
            if key == curses.KEY_ENTER or key in [10, 13]:
                # Save current field and advance
                self.input_data[current_field_key] = self.current_input
                self._advance_to_next_field()
            elif key in [curses.KEY_BACKSPACE, 127, 8]:
                # Handle backspace
                self.current_input = self.current_input[:-1]
                self.needs_redraw = True
            elif key is not None and 32 <= key <= 255:
                # Add typed character
                self.current_input += chr(key)
                self.needs_redraw = True

    def _advance_to_next_field(self):
        """Helper method to advance to next field or complete input session"""
        self.current_input_field_index += 1
        
        if self.current_input_field_index >= len(self.input_fields):
            # All fields completed - call callback and exit input mode
            self.on_input_complete(self.input_data)
            self.is_input_mode = False
        else:
            # Prepare next field
            next_field_key, _ = self.input_fields[self.current_input_field_index]
            self.current_input = self.input_data.get(next_field_key, "")
        
        self.needs_redraw = True

    def _create_windows(self):
        # Only create these windows if in tasks view
        if self.current_view == 'tasks':
            input_pane_height = 4
            main_pane_height = self.height - input_pane_height
            list_pane_width = self.width // 2
            detail_pane_width = self.width - list_pane_width
            
            self.list_win = curses.newwin(main_pane_height, list_pane_width, 0, 0)
            self.detail_win = curses.newwin(main_pane_height, detail_pane_width, 0, list_pane_width)
            self.input_win = curses.newwin(input_pane_height, self.width, main_pane_height, 0)

    def draw_list_pane(self):
        win = self.list_win
        win.erase()
        height, width = win.getmaxyx()
        is_active = self.active_pane == 'list'
        border_color = self._get_color('title') if is_active else self._get_color('default')
        win.attron(border_color)
        win.box()
        win.attroff(border_color)
        win.addstr(0, 2, " NeuroPlan v.2 ", self._get_color('title'))

        # NEW: Modified flatten function to respect collapsed state
        self.planner_tasks = []
        def flatten(tasks, level=0, parent_collapsed=False):
            for i, task in enumerate(tasks):
                # Add task if not under a collapsed parent
                if not parent_collapsed:
                    self.planner_tasks.append({'task': task, 'level': level, 'id': task.id})
                
                # Only recurse into children if this task is not collapsed
                is_collapsed = task.id in self.collapsed_tasks
                if task.children and not is_collapsed:
                    flatten(task.children, level + 1, parent_collapsed)
                elif task.children and is_collapsed:
                    # Skip all children when collapsed
                    flatten(task.children, level + 1, True)
        
        flatten(self.task_manager.get_task_tree())

        if self.selected_index >= len(self.planner_tasks): 
            self.selected_index = max(0, len(self.planner_tasks) - 1)
        if self.selected_index < self.list_scroll_offset: 
            self.list_scroll_offset = self.selected_index
        if self.selected_index >= self.list_scroll_offset + height - 2: 
            self.list_scroll_offset = self.selected_index - (height - 2) + 1
        
        for i, item in enumerate(self.planner_tasks[self.list_scroll_offset:]):
            display_y = 1 + i
            if display_y >= height - 1: 
                break
            task, level = item['task'], item['level']
            
            # NEW: Create visual indicators for tree structure
            prefix = "  " * level
            
            # Show fold/expand indicator for tasks with children
            if task.children:
                if task.id in self.collapsed_tasks:
                    prefix += "[+] "  # Collapsed - show plus
                else:
                    prefix += "[-] "  # Expanded - show minus
            else:
                prefix += "> "  # No children - show normal bullet
            
            display_str = f"{prefix}{task.title}"
            
            # Determine color based on task status and due date
            attr = self._get_color('default')
            if task.status == Status.DONE: 
                attr = self._get_color('done')
                display_str += " [DONE]"
            elif task.due_date:
                now = datetime.datetime.now()
                if task.due_date < now:
                    display_str += " [OVERDUE!]"
                    attr = self._get_color('overdue')
                elif task.due_date < now + datetime.timedelta(hours=24):
                    display_str += " [DUE SOON]"
                    attr = self._get_color('due_soon')
                else:
                    display_str += f" [DUE: {task.due_date.strftime('%m/%d %H:%M')}]"
            
            if self.list_scroll_offset + i == self.selected_index and is_active: 
                attr = self._get_color('highlight')
            
            win.addstr(display_y, 2, " " * (width - 4), curses.A_NORMAL if attr != self._get_color('highlight') else attr)
            win.addstr(display_y, 2, display_str[:width-4], attr)

    def draw_detail_pane(self):
        win = self.detail_win
        win.erase()
        height, width = win.getmaxyx()
        is_active = self.active_pane == 'detail'
        border_color = self._get_color('title') if is_active else self._get_color('default')
        win.attron(border_color)
        win.box()
        win.attroff(border_color)
        win.addstr(0, 2, " Details ", self._get_color('title') if is_active else self._get_color('default'))
        
        if not self.planner_tasks: 
            return
        task = self.planner_tasks[self.selected_index]['task']
        
        # Format description with proper line breaks
        desc_lines = []
        if task.description:
            for para in task.description.split('\n'):
                if para.strip():
                    desc_lines.extend(textwrap.wrap(para, width - 4))
                else:
                    desc_lines.append("")  # Empty line for paragraph breaks
        
        # Due date information
        due_date_str = "Not set"
        due_color = self._get_color('comment')
        
        if task.due_date:
            now = datetime.datetime.now()
            due_date_str = task.due_date.strftime('%Y-%m-%d %H:%M')
            
            # Color code based on urgency
            if task.due_date < now:
                due_date_str += " (OVERDUE!)"
                due_color = self._get_color('overdue')
            elif task.due_date < now + datetime.timedelta(hours=24):
                due_date_str += " (Due soon)"
                due_color = self._get_color('due_soon')
        
        content = [
            ("Title", task.title, self._get_color('default')),
            ("Author", task.author or 'N/A', self._get_color('author')),
            ("Status", task.status.value, self._get_color('default')),
            ("Due Date", due_date_str, due_color),
            ("Created", task.created_at.strftime('%Y-%m-%d %H:%M'), self._get_color('comment')),
        ]
        
        # NEW: Show tree information
        if task.children:
            child_count = len(task.children)
            fold_status = "collapsed" if task.id in self.collapsed_tasks else "expanded"
            content.append(("Children", f"{child_count} tasks ({fold_status})", self._get_color('comment')))
        
        # Show reminder information if reminder system is available
        if self.reminder_system:
            reminder_status = "Enabled" if self.reminder_system.running else "Disabled"
            content.append(("Reminders", reminder_status, self._get_color('comment')))
            
            # Show task-specific reminder settings
            reminder_enabled = getattr(task, 'reminder_enabled', True)
            reminder_minutes = getattr(task, 'reminder_minutes', 30)
            task_reminder_info = f"{'On' if reminder_enabled else 'Off'} ({reminder_minutes}min before)"
            content.append(("Task Alerts", task_reminder_info, self._get_color('comment')))
        
        content.append(("", "─"*20, self._get_color('default')))
        
        # Add description lines
        for line in desc_lines:
            content.append(("", line, self._get_color('default')))
        
        y_offset = 2
        for line_tup in content[self.detail_scroll_offset:]:
            if y_offset >= height-1: 
                break
            label, value, attr = line_tup
            if label and not label.startswith("─"):
                full_line = f"{label}: {value}"
            else:
                full_line = value
            
            win.addstr(y_offset, 2, full_line[:width-4], attr)
            y_offset += 1

    def draw_input_pane(self):
        win = self.input_win
        win.erase()
        height, width = win.getmaxyx()
        win.box()
        win.addstr(0, 2, " Input / Actions ", self._get_color('title'))
        
        if self.is_input_mode and self.current_input_field_index < len(self.input_fields):
            curses.curs_set(1)
            _, prompt_text = self.input_fields[self.current_input_field_index]
            current_field_key, _ = self.input_fields[self.current_input_field_index]
            
            if current_field_key == 'description':
                prompt = f"{prompt_text}: [Press Enter to open editor, Esc to cancel]"
            else:
                prompt = f"{prompt_text}: {self.current_input}"
            
            win.addstr(2, 2, " " * (width - 4))
            win.addstr(2, 2, prompt[:width - 4])
            
            # Position cursor at end of input for non-description fields
            if current_field_key != 'description':
                cursor_pos = min(len(f"{prompt_text}: {self.current_input}"), width - 4)
                win.move(2, 2 + cursor_pos)
        else:
            curses.curs_set(0)
            # Updated key commands to include Flask server controls
            if self.current_view == 'dashboard':
                keys = "[q]uit [Ctrl+B]ack to tasks [?]help"
            elif self.current_view == 'search':
                keys = "[Esc]exit search [j/k]navigate [Enter]select [?]help"
            elif self.current_view == 'help':
                keys = "Press any key to return"
            else:
                keys = "[q]uit [a]dd [i]nsert [e]dit [g]raph view [G]stop server [/]search [?]help [Ctrl+B]oard"
            win.addstr(2, 2, keys[:width-4], self._get_color('comment'))

    def draw(self):
        # Main draw function now decides which view to render
        if self.current_view == 'dashboard':
            self.dashboard_view.draw()
            # We still need an input pane for the dashboard to show controls
            input_pane_height = 4
            self.input_win = curses.newwin(input_pane_height, self.width, self.height - input_pane_height, 0)
            self.draw_input_pane()
            self.input_win.noutrefresh()
            curses.doupdate()
        elif self.current_view == 'search':
            # NEW: Draw search view
            self.search_view.draw()
            curses.doupdate()
        elif self.current_view == 'help':
            # NEW: Draw help view
            self.help_view.draw()
            curses.doupdate()
        elif self.current_view == 'animation':
            # NEW: Draw animation view
            self.animation_view.draw()
            curses.doupdate()
        else:
            # Original task view drawing logic
            self.stdscr.erase()
            self._create_windows()
            self.draw_list_pane()
            self.draw_detail_pane()
            self.draw_input_pane()
            self.stdscr.noutrefresh()
            self.list_win.noutrefresh()
            self.detail_win.noutrefresh()
            self.input_win.noutrefresh()
            curses.doupdate()

# in ui.py -> class App

    def run(self):
        self.stdscr.nodelay(True)
        try:
            while self.running:
                # --- NEW: Live update logic for the dashboard ---
                now = time.time()
                if self.current_view == 'dashboard' and (now - self.last_update_time > self.update_interval):
                    # You might need to add an update() method to your DashboardView class
                    # to re-fetch CPU/memory stats before redrawing.
                    if hasattr(self.dashboard_view, 'update'):
                        self.dashboard_view.update()
                    
                    self.needs_redraw = True
                    self.last_update_time = now
                
                if self.needs_redraw:
                    self.draw()
                    self.needs_redraw = False

                try:
                    key = self.stdscr.getch()
                # ... (the rest of the run method) ...
                except (curses.error, KeyboardInterrupt):
                    continue
                
                if key != -1:
                    if key == curses.KEY_RESIZE:
                        self.height, self.width = self.stdscr.getmaxyx()
                        self.needs_redraw = True
                    else:
                        self.handle_input(key)
                
                time.sleep(0.01)
        finally:
            # Clean up Flask server when app exits
            if self.flask_server_running:
                self.stop_flask_server()
            stop_server()  # Your existing server stop function