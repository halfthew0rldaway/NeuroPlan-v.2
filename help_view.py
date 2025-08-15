# help_view.py
import curses

class HelpView:
    """
    A full-screen view to display context-aware help.
    """
    def __init__(self, stdscr, theme):
        self.stdscr = stdscr
        self.theme = theme
        self.height, self.width = 0, 0
        self.context = 'tasks' # Can be 'tasks', 'dashboard', etc.

    def set_context(self, context: str):
        """Sets the current context to display the correct help text."""
        self.context = context

    def draw(self):
        """Draws the help screen for the current context."""
        self.height, self.width = self.stdscr.getmaxyx()
        self.stdscr.erase()
        
        self._draw_panel_border(f"Help: {self.context.capitalize()} View")
        
        help_text = self._get_help_text()
        
        y = 2
        for section, commands in help_text.items():
            if y >= self.height - 2: break
            self.stdscr.addstr(y, 2, section, self.theme.get('title'))
            y += 1
            for key, desc in commands.items():
                if y >= self.height - 2: break
                line = f"  {key:<15} {desc}"
                self.stdscr.addstr(y, 2, line[:self.width-3], self.theme.get('default'))
                y += 1
            y += 1 # Add a blank line between sections
            
        footer = "Press any key to return"
        self.stdscr.addstr(self.height - 2, (self.width - len(footer)) // 2, footer, self.theme.get('comment'))

    def _draw_panel_border(self, title):
        """Draws a styled box with a title."""
        self.stdscr.attron(self.theme.get('title'))
        self.stdscr.box()
        self.stdscr.attroff(self.theme.get('title'))
        self.stdscr.addstr(0, 2, f" {title} ", self.theme.get('title'))

    def _get_help_text(self):
        """Returns the appropriate dictionary of keybindings."""
        if self.context == 'tasks':
            return {
                "Navigation": {
                    "j / ↓": "Move down",
                    "k / ↑": "Move up",
                    "Tab": "Switch between List and Detail panes",
                },
                "Task Management": {
                    "a": "Add new task",
                    "i": "Insert child task",
                    "e": "Edit selected task",
                    "x": "Delete selected task",
                    "Space": "Toggle task status (TODO/DONE)",
                    "d": "Set due date",
                },
                "Application": {
                    "q": "Quit",
                    "/": "Open Search View",
                    "Ctrl+B": "Open Dashboard",
                    "Ctrl+N": "Quick Capture Note",
                    "Ctrl+A": "Show Animation",
                    "?": "Show this help screen",
                }
            }
        elif self.context == 'dashboard':
            return {
                "Navigation": {
                    "← / →": "Navigate calendar months",
                },
                "Application": {
                    "q": "Quit",
                    "Ctrl+B": "Return to Task View",
                    "?": "Show this help screen",
                }
            }
        elif self.context == 'search':
            return {
                "Navigation": {
                    "j / ↓": "Move down in results",
                    "k / ↑": "Move up in results",
                    "Enter": "Go to selected task",
                },
                "Application": {
                    "Esc": "Exit Search View",
                    "?": "Show this help screen",
                }
            }
        return {}
