# dashboard_view.py
import curses
import datetime
import textwrap
import requests
import calendar
from task_manager import Status

# Import system monitor components and handle optional psutil dependency
try:
    from system_monitor import (
        format_bytes,
        NetworkMonitor,
    )
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class DashboardView:
    """
    Manages the rendering of the main dashboard view using curses.
    """
    def __init__(self, stdscr, task_manager, theme):
        self.stdscr = stdscr
        self.task_manager = task_manager
        self.theme = theme
        self.height, self.width = self.stdscr.getmaxyx()
        self._weather_data = {
            "temp_C": "N/A",
            "description": "Loading...",
            "wind_kmph": "N/A",
            "humidity": "N/A",
            "region": "Bekasi"
        }
        self._last_weather_fetch = None
        self._calendar_date = datetime.date.today()
        # Initialize system monitor components if available
        self.network_monitor = NetworkMonitor() if PSUTIL_AVAILABLE else None

    def _get_color(self, name):
        """Helper to get a color pair from the theme."""
        return self.theme.get(name, curses.A_NORMAL)

    # NEW: A dedicated method to draw the system monitor bar at the top
    def _draw_top_bar(self, win):
        """Draws a single-line system monitor bar."""
        win.erase()
        h, w = win.getmaxyx()
        
        # Use a distinct background color for the bar
        bar_color = self._get_color('capture')
        win.bkgd(' ', bar_color)

        if not PSUTIL_AVAILABLE:
            msg = "System Monitor disabled: 'psutil' not found."
            win.addstr(0, (w - len(msg)) // 2, msg, self._get_color('overdue') | bar_color)
            return

        # Get system stats
        cpu_stat = f"CPU: {psutil.cpu_percent(interval=None):>5.1f}%"
        mem = psutil.virtual_memory()
        mem_stat = f"Mem: {mem.percent:>5.1f}%"
        
        upload_speed, download_speed = self.network_monitor.get_speed()
        net_stat = f"Net: ↓{format_bytes(download_speed)}/s ↑{format_bytes(upload_speed)}/s"

        # Create the full string for the bar
        full_stat_str = f"  {cpu_stat}    |    {mem_stat}    |    {net_stat}  "
        
        # Draw the stats, centered
        start_x = (w - len(full_stat_str)) // 2
        if start_x < 0: start_x = 0
        
        win.addstr(0, start_x, full_stat_str, curses.A_BOLD | bar_color)

    def handle_input(self, key):
        """Handles user input for the dashboard view, like calendar navigation."""
        if key == curses.KEY_LEFT:
            current_month = self._calendar_date.month
            current_year = self._calendar_date.year
            
            new_month = current_month - 1
            new_year = current_year
            if new_month == 0:
                new_month = 12
                new_year -= 1
            
            self._calendar_date = self._calendar_date.replace(year=new_year, month=new_month, day=1)
            return True
            
        elif key == curses.KEY_RIGHT:
            current_month = self._calendar_date.month
            current_year = self._calendar_date.year

            new_month = current_month + 1
            new_year = current_year
            if new_month == 13:
                new_month = 1
                new_year += 1
            
            self._calendar_date = self._calendar_date.replace(year=new_year, month=new_month, day=1)
            return True
            
        return False

    def _fetch_weather(self):
        """Fetches detailed weather data from wttr.in's JSON endpoint for a specific region."""
        now = datetime.datetime.now()
        if self._last_weather_fetch and (now - self._last_weather_fetch) < datetime.timedelta(minutes=30):
            return

        try:
            response = requests.get("https://wttr.in/Bekasi?format=j1", timeout=5)
            response.raise_for_status()
            data = response.json()
            
            current_condition = data.get('current_condition', [{}])[0]
            nearest_area = data.get('nearest_area', [{}])[0]
            
            self._weather_data = {
                "temp_C": current_condition.get('temp_C', 'N/A'),
                "description": current_condition.get('weatherDesc', [{}])[0].get('value', 'N/A'),
                "wind_kmph": current_condition.get('windspeedKmph', 'N/A'),
                "humidity": current_condition.get('humidity', 'N/A'),
                "region": nearest_area.get('areaName', [{}])[0].get('value', 'Bekasi')
            }

        except (requests.RequestException, KeyError, IndexError):
            self._weather_data = {
                "temp_C": "N/A",
                "description": "Unavailable",
                "wind_kmph": "N/A",
                "humidity": "N/A",
                "region": "Bekasi"
            }
        finally:
            self._last_weather_fetch = now

    def draw(self):
        """MODIFIED: Draws the entire dashboard layout with a top bar."""
        self.height, self.width = self.stdscr.getmaxyx()
        self._fetch_weather()

        # Define heights for top and bottom bars
        top_bar_h = 1
        status_bar_h = 1

        # Create the top bar window
        top_bar_win = curses.newwin(top_bar_h, self.width, 0, 0)
        self._draw_top_bar(top_bar_win)

        # Adjust main area height and starting Y position
        main_h = self.height - top_bar_h - status_bar_h
        start_y = top_bar_h
        if main_h < 1: return

        # Panel layout logic uses the new start_y and main_h
        left_w = self.width // 2
        right_w = self.width - left_w
        
        agenda_h = main_h // 2
        system_info_h = main_h - agenda_h
        
        upcoming_h = main_h // 2
        calendar_h = main_h - upcoming_h

        if any(d <= 0 for d in [agenda_h, left_w, upcoming_h, right_w, system_info_h, calendar_h]):
            return

        # Create windows with the new starting Y coordinate
        agenda_win = curses.newwin(agenda_h, left_w, start_y, 0)
        upcoming_win = curses.newwin(upcoming_h, right_w, start_y, left_w)
        system_info_win = curses.newwin(system_info_h, left_w, start_y + agenda_h, 0)
        calendar_win = curses.newwin(calendar_h, right_w, start_y + upcoming_h, left_w)
        status_win = curses.newwin(status_bar_h, self.width, self.height - status_bar_h, 0)

        # Draw all components
        self._draw_agenda_panel(agenda_win)
        self._draw_upcoming_panel(upcoming_win)
        self._draw_system_info_panel(system_info_win) # This now shows the log as before
        self._draw_calendar_panel(calendar_win)
        self._draw_status_bar(status_win)

        # Refresh all windows, including the new top bar
        top_bar_win.noutrefresh()
        agenda_win.noutrefresh()
        upcoming_win.noutrefresh()
        system_info_win.noutrefresh()
        calendar_win.noutrefresh()
        status_win.noutrefresh()

    def _draw_panel_border(self, win, title, color_name='title'):
        """Draws a styled box around a window with a title."""
        win.erase()
        win.attron(self._get_color(color_name))
        win.box()
        win.attroff(self._get_color(color_name))
        win.addstr(0, 2, f" {title} ", self._get_color(color_name) | curses.A_BOLD)

    def _draw_agenda_panel(self, win):
        """Draws the 'Today's Agenda' panel."""
        self._draw_panel_border(win, "Today's Agenda", 'due_soon')
        h, w = win.getmaxyx()

        today = datetime.date.today()
        all_tasks = self.task_manager.get_all_tasks_flat()
        todays_tasks = [
            task for task in all_tasks
            if task.due_date and task.due_date.date() == today and task.status != Status.DONE
        ]
        todays_tasks.sort(key=lambda t: t.due_date)

        if not todays_tasks:
            win.addstr(h // 2, (w - 18) // 2, "No tasks for today.", self._get_color('comment'))
            return

        y = 2
        for task in todays_tasks:
            if y >= h - 1: break
            time_str = task.due_date.strftime('%H:%M')
            display_str = f" {time_str} - {task.title}"
            win.addstr(y, 2, "●", self._get_color('due_soon'))
            win.addstr(y, 4, display_str[:w-5], self._get_color('default'))
            y += 1

    def _draw_upcoming_panel(self, win):
        """Draws tasks for the month selected in the calendar."""
        self._draw_panel_border(win, f"Agenda for {self._calendar_date.strftime('%B')}", 'author')
        h, w = win.getmaxyx()

        all_tasks = self.task_manager.get_all_tasks_flat()
        upcoming_tasks = [
            task for task in all_tasks
            if task.due_date and task.due_date.year == self._calendar_date.year and \
               task.due_date.month == self._calendar_date.month and task.status != Status.DONE
        ]
        upcoming_tasks.sort(key=lambda t: t.due_date)

        if not upcoming_tasks:
            win.addstr(h // 2, (w - 26) // 2, "No scheduled tasks this month.", self._get_color('comment'))
            return

        y = 2
        for task in upcoming_tasks:
            if y >= h - 1: break
            date_str = task.due_date.strftime('%d/%m %H:%M')
            display_str = f" {date_str} - {task.title}"
            win.addstr(y, 2, "●", self._get_color('author'))
            win.addstr(y, 4, display_str[:w-5], self._get_color('default'))
            y += 1

    # RESTORED: This method now shows the original System Log content.
    def _draw_system_info_panel(self, win):
        """Displays clock, detailed weather, and logs."""
        self._draw_panel_border(win, "System Status", 'comment')
        h, w = win.getmaxyx()
        
        # --- Clock Section ---
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%A, %d %B %Y")
        
        win.addstr(2, (w - len(time_str)) // 2, time_str, self._get_color('title'))
        win.addstr(3, (w - len(date_str)) // 2, date_str, self._get_color('comment'))
        
        # --- Weather Section ---
        weather_y = 5
        if weather_y < h - 4:
            region_str = f"Weather in {self._weather_data['region']}:"
            win.addstr(weather_y, 2, region_str, self._get_color('title'))
            
            desc_str = f"{self._weather_data['temp_C']}°C, {self._weather_data['description']}"
            details_str = f"Wind: {self._weather_data['wind_kmph']} km/h, Humidity: {self._weather_data['humidity']}%"
            
            win.addstr(weather_y + 1, 4, desc_str[:w-5], self._get_color('default'))
            win.addstr(weather_y + 2, 4, details_str[:w-5], self._get_color('default'))
        
        # --- Log Section (original placeholder) ---
        log_y = weather_y + 4
        if log_y < h - 1:
            win.addstr(log_y, 2, "System Log:", self._get_color('title'))
            
            # This is a placeholder for a real logging system.
            log_lines = [
                f"{(now - datetime.timedelta(minutes=15)).strftime('%H:%M')} [INFO] App initialized successfully.",
                f"{(now - datetime.timedelta(minutes=10)).strftime('%H:%M')} [INFO] Loaded 8 tasks from storage.",
                f"{(now - datetime.timedelta(minutes=2)).strftime('%H:%M')} [WARN] Could not connect to calendar API.",
                f"{(now - datetime.timedelta(seconds=30)).strftime('%H:%M')} [INFO] Dashboard rendered."
            ]
            
            for i, log_line in enumerate(log_lines):
                if log_y + i + 1 < h - 1:
                    color = self._get_color('default')
                    if "[WARN]" in log_line:
                        color = self._get_color('overdue')
                    elif "[INFO]" in log_line:
                        color = self._get_color('comment')
                    win.addstr(log_y + i + 1, 4, log_line[:w-5], color)

    def _draw_calendar_panel(self, win):
        """Draws an interactive calendar panel."""
        self._draw_panel_border(win, "Calendar", 'author')
        h, w = win.getmaxyx()
        
        today = datetime.date.today()
        cal = calendar.monthcalendar(self._calendar_date.year, self._calendar_date.month)
        
        all_tasks = self.task_manager.get_all_tasks_flat()
        task_days = {
            task.due_date.day for task in all_tasks 
            if task.due_date and task.due_date.year == self._calendar_date.year and \
               task.due_date.month == self._calendar_date.month
        }

        cal_width = 20
        start_x = (w - cal_width) // 2
        if start_x < 2: start_x = 2
        
        month_header = f"< {self._calendar_date.strftime('%B %Y')} >"
        win.addstr(2, (w - len(month_header)) // 2, month_header, self._get_color('title'))

        day_names = "Mo Tu We Th Fr Sa Su"
        win.addstr(4, start_x, day_names, self._get_color('comment'))

        y = 6
        for week in cal:
            if y >= h -1: break
            x = start_x
            for day in week:
                if day == 0:
                    win.addstr(y, x, "  ")
                else:
                    day_str = f"{day:2}"
                    attr = self._get_color('default')
                    if self._calendar_date.year == today.year and \
                       self._calendar_date.month == today.month and \
                       day == today.day:
                        attr = self._get_color('highlight')
                    elif day in task_days:
                        attr = self._get_color('due_soon') | curses.A_BOLD
                    
                    win.addstr(y, x, day_str, attr)
                x += 3
            y += 1

    def _draw_status_bar(self, win):
        """Draws the bottom status bar with new keybindings."""
        win.erase()
        h, w = win.getmaxyx()
        keys = "[q]uit | [< >] Nav Month | [Ctrl+B]ack to tasks"
        win.addstr(0, 1, keys, self._get_color('comment'))