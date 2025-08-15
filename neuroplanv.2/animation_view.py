# animation_view.py - Complete fixed version
import curses
import time
import random
import math

class AnimationView:
    """
    A full-screen view to display a moving, multi-stage ASCII animation of Gojo.
    """
    def __init__(self, stdscr, theme):
        self.stdscr = stdscr
        self.theme = theme
        self.height, self.width = 0, 0
        
        # Animation state
        self.state = "charging"  # charging -> firing -> cooldown
        self.state_timer = 0
        self.last_update_time = 0
        
        # Animation frame counter for smooth movement
        self.frame_counter = 0
        
        # Gojo ASCII Art - properly sized
        self.gojo_art = [
            "       ╭─────────────────╮       ",
            "     ╭─┴─────────────────┴─╮     ",
            "   ╱                       ╲   ",
            "  ╱           ●   ●           ╲  ",
            " ╱             ─────             ╲ ",
            "│               ███               │",
            "│                                │",
            " ╲                             ╱ ",
            "  ╲___________________________╱  ",
            "      │ S A T O R U  G O J O │      ",
            "      ╰─────────────────────╯      "
        ]
        
        # Hollow Purple beam properties
        self.beam_pos_x = 0
        self.beam_particles = []
        
        # Energy orb positions
        self.red_orb_angle = 0
        self.blue_orb_angle = math.pi  # Start opposite side
        self.orb_distance = 20

    def reset(self):
        """Resets the animation state."""
        self.state = "charging"
        self.state_timer = 0
        self.last_update_time = time.time()
        self.beam_pos_x = 0
        self.beam_particles = []
        self.frame_counter = 0
        self.red_orb_angle = 0
        self.blue_orb_angle = math.pi
        self.orb_distance = 20

    def draw(self):
        """Draws the current animation frame and state."""
        try:
            self.height, self.width = self.stdscr.getmaxyx()
            self.stdscr.erase()
            
            self.update()

            # Calculate Gojo position
            gojo_h = len(self.gojo_art)
            gojo_w = max(len(line) for line in self.gojo_art) if gojo_h > 0 else 0
            start_y = max(0, (self.height - gojo_h) // 2)
            start_x = max(0, (self.width - gojo_w) // 2)

            # Draw Gojo character
            self._draw_gojo(start_y, start_x, gojo_h, gojo_w)

            # Draw animation effects based on state
            if self.state == "charging":
                self._draw_charging_effect(start_y, start_x, gojo_h, gojo_w)
            elif self.state == "firing":
                self._draw_beam(start_y, start_x, gojo_h, gojo_w)
            elif self.state == "cooldown":
                self._draw_cooldown_effect(start_y, start_x, gojo_h, gojo_w)
            
            # Draw state indicator
            self._draw_state_indicator()
            
            # Draw border and footer
            self._draw_panel_border("Gojo Satoru - Hollow Purple")
            self._draw_footer()
        
        except curses.error:
            # Handle screen size issues gracefully
            pass

    def _draw_gojo(self, start_y, start_x, gojo_h, gojo_w):
        """Draw the Gojo character with subtle animation."""
        try:
            # Add subtle movement to Gojo
            offset_x = int(math.sin(self.frame_counter * 0.05) * 1)
            offset_y = 0
            
            if self.state == "firing":
                # More dramatic movement during firing
                offset_x = int(math.sin(self.frame_counter * 0.2) * 2)
                offset_y = int(math.cos(self.frame_counter * 0.15) * 1)
            
            draw_x = max(0, min(self.width - gojo_w - 1, start_x + offset_x))
            draw_y = max(0, min(self.height - gojo_h - 1, start_y + offset_y))
            
            for i, line in enumerate(self.gojo_art):
                if draw_y + i < self.height - 1 and len(line) > 0:
                    # Color the character based on animation state
                    char_color = self.theme.get('default')
                    if self.state == "firing":
                        char_color = self.theme.get('anim_purple') | curses.A_BOLD
                    elif self.state == "charging" and self.state_timer > 2:
                        char_color = self.theme.get('default') | curses.A_BOLD
                    
                    display_line = line[:min(len(line), self.width - draw_x - 1)]
                    self.stdscr.addstr(draw_y + i, draw_x, display_line, char_color)
        
        except curses.error:
            pass

    def _draw_charging_effect(self, y, x, h, w):
        """Draws the Red and Blue orbs charging up with circular motion."""
        try:
            center_y = y + h // 2
            center_x = x + w // 2
            
            # Calculate orb positions using circular motion
            red_x = int(center_x + math.cos(self.red_orb_angle) * self.orb_distance)
            red_y = int(center_y + math.sin(self.red_orb_angle) * (self.orb_distance // 3))
            
            blue_x = int(center_x + math.cos(self.blue_orb_angle) * self.orb_distance)
            blue_y = int(center_y + math.sin(self.blue_orb_angle) * (self.orb_distance // 3))
            
            # Draw red orb (Cursed Technique Reversal: Red)
            if 0 <= red_y < self.height - 1 and 0 <= red_x < self.width - 1:
                orb_char = "●" if self.frame_counter % 20 < 10 else "◉"
                self.stdscr.addstr(red_y, red_x, orb_char, self.theme.get('anim_red') | curses.A_BOLD)
                
                # Red energy particles
                for _ in range(6):
                    p_x = red_x + random.randint(-4, 4)
                    p_y = red_y + random.randint(-2, 2)
                    if 0 <= p_y < self.height - 1 and 0 <= p_x < self.width - 1:
                        char = random.choice(["*", ".", "+", "~", "◦"])
                        self.stdscr.addstr(p_y, p_x, char, self.theme.get('anim_red'))

            # Draw blue orb (Cursed Technique Lapse: Blue)
            if 0 <= blue_y < self.height - 1 and 0 <= blue_x < self.width - 1:
                orb_char = "●" if (self.frame_counter + 10) % 20 < 10 else "◉"
                self.stdscr.addstr(blue_y, blue_x, orb_char, self.theme.get('anim_blue') | curses.A_BOLD)
                
                # Blue energy particles
                for _ in range(6):
                    p_x = blue_x + random.randint(-4, 4)
                    p_y = blue_y + random.randint(-2, 2)
                    if 0 <= p_y < self.height - 1 and 0 <= p_x < self.width - 1:
                        char = random.choice(["*", ".", "+", "~", "◦"])
                        self.stdscr.addstr(p_y, p_x, char, self.theme.get('anim_blue'))
            
            # Draw energy convergence lines as charging intensifies
            if self.state_timer > 1.5:
                self._draw_convergence_lines(center_x, center_y, red_x, red_y, blue_x, blue_y)
        
        except curses.error:
            pass

    def _draw_convergence_lines(self, center_x, center_y, red_x, red_y, blue_x, blue_y):
        """Draw energy lines converging to center."""
        try:
            steps = 15
            for i in range(1, steps):
                t = i / steps
                
                # Red convergence line
                line_x = int(red_x + (center_x - red_x) * t)
                line_y = int(red_y + (center_y - red_y) * t)
                if 0 <= line_y < self.height - 1 and 0 <= line_x < self.width - 1:
                    char = "─" if i % 3 == 0 else "━"
                    self.stdscr.addstr(line_y, line_x, char, self.theme.get('anim_red'))
                
                # Blue convergence line
                line_x = int(blue_x + (center_x - blue_x) * t)
                line_y = int(blue_y + (center_y - blue_y) * t)
                if 0 <= line_y < self.height - 1 and 0 <= line_x < self.width - 1:
                    char = "─" if i % 3 == 0 else "━"
                    self.stdscr.addstr(line_y, line_x, char, self.theme.get('anim_blue'))
        except curses.error:
            pass

    def _draw_beam(self, y, x, h, w):
        """Draws the Hollow Purple beam moving across the screen."""
        try:
            beam_start_x = x + w // 2
            beam_y = y + h // 2
            
            # Main beam core
            beam_chars = ['═', '━', '▬', '■', '▪', '◆']
            beam_width = min(self.beam_pos_x, self.width - beam_start_x - 1)
            
            for i in range(beam_width):
                if beam_start_x + i < self.width - 1 and beam_y < self.height - 1:
                    # Animate beam character
                    char_index = (i + self.frame_counter // 2) % len(beam_chars)
                    char = beam_chars[char_index]
                    
                    # Pulsing intensity
                    intensity = curses.A_BOLD if (i + self.frame_counter) % 4 < 2 else curses.A_NORMAL
                    color = self.theme.get('anim_purple') | intensity
                    
                    self.stdscr.addstr(beam_y, beam_start_x + i, char, color)
            
            # Beam spread (upper and lower)
            if self.beam_pos_x > 8:
                for offset in [-1, 1, -2, 2]:
                    spread_width = max(0, beam_width - abs(offset) * 3)
                    for i in range(spread_width):
                        beam_pos_y = beam_y + offset
                        beam_pos_x = beam_start_x + i
                        
                        if (0 <= beam_pos_y < self.height - 1 and 
                            0 <= beam_pos_x < self.width - 1 and
                            random.random() > 0.4):  # Sparse secondary beams
                            
                            char = random.choice(['─', '▬', '·', '◦'])
                            intensity = curses.A_NORMAL if abs(offset) > 1 else curses.A_BOLD
                            self.stdscr.addstr(beam_pos_y, beam_pos_x, char,
                                             self.theme.get('anim_purple') | intensity)
            
            # Update and draw particles
            self._update_beam_particles(beam_y, beam_start_x)
            self._draw_beam_particles()
        
        except curses.error:
            pass

    def _update_beam_particles(self, beam_y, beam_start_x):
        """Update beam particle system."""
        # Create new particles at beam tip
        if self.beam_pos_x > 0:
            for _ in range(4):
                self.beam_particles.append([
                    beam_y + random.randint(-4, 4),
                    beam_start_x + self.beam_pos_x + random.randint(-3, 10),
                    random.choice(['·', '*', '+', '~', '▪', '◦', '○']),
                    random.randint(10, 20)  # Particle lifetime
                ])

        # Update existing particles
        updated_particles = []
        for p_y, p_x, p_char, p_life in self.beam_particles:
            new_life = p_life - 1
            if new_life > 0:
                # Add drift and dispersion
                new_x = p_x + random.randint(-1, 3)
                new_y = p_y + random.randint(-1, 1)
                updated_particles.append([new_y, new_x, p_char, new_life])
        
        self.beam_particles = updated_particles

    def _draw_beam_particles(self):
        """Draw all beam particles."""
        try:
            for p_y, p_x, p_char, p_life in self.beam_particles:
                if (p_life > 0 and 0 <= p_y < self.height - 1 and 0 <= p_x < self.width - 1):
                    # Fade particles based on remaining life
                    intensity = curses.A_BOLD if p_life > 10 else curses.A_NORMAL
                    self.stdscr.addstr(p_y, p_x, p_char, self.theme.get('anim_purple') | intensity)
        except curses.error:
            pass

    def _draw_cooldown_effect(self, y, x, h, w):
        """Draw a cooldown effect with dissipating energy."""
        try:
            center_y = y + h // 2
            center_x = x + w // 2
            
            # Draw dissipating energy sparks
            fade_factor = max(0.1, 2 - self.state_timer)  # Fade over 2 seconds
            num_sparks = max(5, int(25 * fade_factor))
            
            for _ in range(num_sparks):
                spark_radius = int(25 * fade_factor)
                spark_x = center_x + random.randint(-spark_radius, spark_radius)
                spark_y = center_y + random.randint(-spark_radius//2, spark_radius//2)
                
                if 0 <= spark_y < self.height - 1 and 0 <= spark_x < self.width - 1:
                    char = random.choice(['·', '*', '+', '~', '◦', '○'])
                    colors = [
                        self.theme.get('anim_purple'),
                        self.theme.get('anim_blue'),
                        self.theme.get('anim_red')
                    ]
                    color = random.choice(colors)
                    intensity = curses.A_NORMAL if fade_factor < 1 else curses.A_BOLD
                    self.stdscr.addstr(spark_y, spark_x, char, color | intensity)
        
        except curses.error:
            pass

    def _draw_state_indicator(self):
        """Draw current animation state indicator."""
        try:
            state_text = f"[ {self.state.upper()} ]"
            if len(state_text) < self.width - 4:
                if self.state == "charging":
                    color = self.theme.get('anim_red') | curses.A_BOLD
                elif self.state == "firing":
                    color = self.theme.get('anim_purple') | curses.A_BOLD
                else:  # cooldown
                    color = self.theme.get('anim_blue') | curses.A_BOLD
                
                self.stdscr.addstr(1, (self.width - len(state_text)) // 2, state_text, color)
        except curses.error:
            pass

    def _draw_footer(self):
        """Draw footer instructions."""
        try:
            footer = "Press any key to return to task view"
            if len(footer) < self.width - 4:
                self.stdscr.addstr(self.height - 2, (self.width - len(footer)) // 2, 
                                 footer, self.theme.get('comment'))
        except curses.error:
            pass

    def update(self):
        """Updates the animation state and properties."""
        now = time.time()
        if self.last_update_time == 0:
            self.last_update_time = now
            return

        delta_time = now - self.last_update_time
        self.state_timer += delta_time
        self.frame_counter += 1

        if self.state == "charging":
            # Update orb rotation (faster as charging intensifies)
            rotation_speed = 1.5 + (self.state_timer * 0.5)
            self.red_orb_angle += delta_time * rotation_speed
            self.blue_orb_angle += delta_time * rotation_speed
            
            # Gradually decrease orb distance (pull towards center)
            if self.state_timer > 1:
                target_distance = max(8, 20 - (self.state_timer - 1) * 4)
                self.orb_distance = target_distance
            
            # Transition to firing after 3 seconds
            if self.state_timer > 3:
                self.state = "firing"
                self.state_timer = 0
                self.beam_pos_x = 1
                
        elif self.state == "firing":
            # Beam expands rapidly across screen
            beam_speed = max(8, int(10 * delta_time * 60))  # Accelerate over time
            self.beam_pos_x += beam_speed
            
            # Transition to cooldown when beam crosses most of screen
            if self.beam_pos_x > self.width // 2 + 40:
                self.state = "cooldown"
                self.state_timer = 0
                
        elif self.state == "cooldown":
            # Reset after cooldown period
            if self.state_timer > 3:
                self.reset()
        
        self.last_update_time = now

    def _draw_panel_border(self, title):
        """Draws a styled box with a title."""
        try:
            # Draw border
            self.stdscr.attron(self.theme.get('title'))
            self.stdscr.box()
            self.stdscr.attroff(self.theme.get('title'))
            
            # Draw title
            if len(title) < self.width - 4:
                self.stdscr.addstr(0, 2, f" {title} ", self.theme.get('title') | curses.A_BOLD)
        except curses.error:
            pass

    def handle_input(self, key):
        """Handles user input for the animation view."""
        # Any key will exit the view
        self.reset()  # Reset animation when leaving
        return True