# search_view.py
import curses
import textwrap

class SearchView:
    """
    A full-screen view for searching tasks.
    """
    def __init__(self, stdscr, task_manager, theme):
        self.stdscr = stdscr
        self.task_manager = task_manager
        self.theme = theme
        self.height, self.width = 0, 0
        
        self.query = ""
        self.results = []
        self.selected_index = 0
        self.scroll_offset = 0
        self.active = False

    def activate(self):
        """Called when switching to this view."""
        self.active = True
        self.query = ""
        self.results = []
        self.selected_index = 0
        self.scroll_offset = 0
        curses.curs_set(1) # Show cursor for typing

    def deactivate(self):
        """Called when switching away from this view."""
        self.active = False
        curses.curs_set(0) # Hide cursor
        return None # No task selected

    def handle_input(self, key):
        """Handles user input for the search query and results list."""
        if key in [curses.KEY_BACKSPACE, 127, 8]:
            self.query = self.query[:-1]
            self._update_search()
        elif key is not None and 32 <= key <= 126:
            self.query += chr(key)
            self._update_search()
        elif key in [curses.KEY_DOWN, ord('j')]:
            if self.selected_index < len(self.results) - 1:
                self.selected_index += 1
        elif key in [curses.KEY_UP, ord('k')]:
            if self.selected_index > 0:
                self.selected_index -= 1
        elif key in [curses.KEY_ENTER, 10, 13]:
            if self.results:
                selected_task_id = self.results[self.selected_index].id
                self.active = False
                curses.curs_set(0)
                return selected_task_id # Return the ID to the main app
        elif key == 27: # ESC key
            return self.deactivate()
            
        return None

    def _update_search(self):
        """Performs a new search and resets the view."""
        self.results = self.task_manager.search_tasks(self.query)
        self.selected_index = 0
        self.scroll_offset = 0

    def draw(self):
        """Draws the entire search interface."""
        self.height, self.width = self.stdscr.getmaxyx()
        
        # Draw search bar at the top
        search_prompt = "Search: "
        self.stdscr.addstr(0, 0, " " * (self.width -1), self.theme.get('highlight'))
        self.stdscr.addstr(0, 1, search_prompt + self.query, self.theme.get('highlight'))
        self.stdscr.move(0, 1 + len(search_prompt) + len(self.query))

        # Draw results list
        list_h = self.height - 2
        
        # Adjust scroll offset to keep selection in view
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        if self.selected_index >= self.scroll_offset + list_h:
            self.scroll_offset = self.selected_index - list_h + 1

        for i, task in enumerate(self.results[self.scroll_offset:]):
            y = i + 2
            if y >= self.height:
                break
            
            display_str = f"{task.title}"
            if task.file:
                display_str += f"  [{task.file}]"

            attr = self.theme.get('default')
            if i + self.scroll_offset == self.selected_index:
                attr = self.theme.get('highlight')
            
            self.stdscr.addstr(y, 0, " " * (self.width -1), attr)
            self.stdscr.addstr(y, 1, display_str[:self.width-2], attr)
