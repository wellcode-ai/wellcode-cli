import os
import random
import select
import sys
import termios
import threading
import time
import tty


class CyberpunkRunner:
    def __init__(self, width=30, height=6, screen=None):
        self.screen = screen
        self.height = height
        self.width = width
        self._lock = threading.Lock()

        # Initialize colors first
        self.colors = {
            "neon_pink": "\033[38;2;255;20;147m",  # Hot pink
            "neon_blue": "\033[38;2;0;255;255m",  # Cyan
            "neon_purple": "\033[38;2;147;0;255m",  # Purple
            "neon_green": "\033[38;2;0;255;127m",  # Spring green
            "reset": "\033[0m",
        }

        # Initialize characters
        self.player_char = f"{self.colors['neon_pink']}P{self.colors['reset']}"
        self.shield_char = f"{self.colors['neon_blue']}⚡{self.colors['reset']}"
        self.ground_char = f"{self.colors['neon_purple']}▀{self.colors['reset']}"
        self.heart_char = f"{self.colors['neon_pink']}♥{self.colors['reset']}"

        # Border colors
        self.border_color = self.colors["neon_green"]
        self.border_reset = self.colors["reset"]

        # Initialize game objects
        self.obstacle_types = [
            {"char": "▓", "color": self.colors["neon_blue"], "damage": 1},
            {"char": "█", "color": self.colors["neon_purple"], "damage": 2},
            {"char": "▒", "color": self.colors["neon_pink"], "damage": 1},
        ]

        self.power_up_types = {
            "shield": {"char": "🛡️", "color": self.colors["neon_blue"]},
            "points": {"char": "💎", "color": self.colors["neon_purple"]},
            "extra_life": {"char": "❤️", "color": self.colors["neon_pink"]},
        }

        # Initialize background
        self.stars = [" ", "·", "⋅", "∙"]
        self.background = []
        self._running = True
        self.score = 0  # This could represent progress

        # Jump configuration
        self.max_jumps = 2  # Allow double jump
        self.jumps_left = self.max_jumps
        self.jump_power = [-2, -1, 0, 1, 1]  # Defines jump arc

        # Now we can safely reset the game
        self.reset_game()

    def reset_game(self):
        """Reset all game variables to start a new game"""
        self.width = 30
        self.height = 6
        self.player_pos = self.height - 2
        self.player_x = 5
        self.obstacles = []
        self.score = 0
        self.game_over = False
        self.jumping = False
        self.jump_count = 0
        self.lives = 3
        self.power_ups = []
        self.active_shield = False
        self.shield_duration = 0
        self.jumps_left = self.max_jumps
        self._init_background()

    def show_game_over(self):
        """Display game over screen"""
        sys.stdout.write("\033[H\033[2J")  # Clear screen

        # Game Over frame
        current_line = 1

        # Top border
        sys.stdout.write(f"\033[{current_line};1H")
        sys.stdout.write(f"{self.border_color}╭{'─' * self.width}╮{self.border_reset}")

        # Game Over text
        current_line += 1
        sys.stdout.write(f"\033[{current_line};1H")
        game_over = f"{self.colors['neon_pink']}GAME OVER!{self.colors['reset']}"
        padding = " " * ((self.width - 9) // 2)  # 9 is length of "GAME OVER!"
        sys.stdout.write(
            f"{self.border_color}│{self.border_reset}{padding}{game_over}{padding}{self.border_color}│{self.border_reset}"
        )

        # Score
        current_line += 1
        sys.stdout.write(f"\033[{current_line};1H")
        score_text = f"Final Score: {self.score}"
        padding = " " * ((self.width - len(score_text)) // 2)
        sys.stdout.write(
            f"{self.border_color}│{self.border_reset}{padding}{score_text}{padding}{self.border_color}│{self.border_reset}"
        )

        # Restart instruction
        current_line += 1
        sys.stdout.write(f"\033[{current_line};1H")
        restart_text = "Press 'r' to restart"
        padding = " " * ((self.width - len(restart_text)) // 2)
        sys.stdout.write(
            f"{self.border_color}│{self.border_reset}{padding}{restart_text}{padding}{self.border_color}│{self.border_reset}"
        )

        # Quit instruction
        current_line += 1
        sys.stdout.write(f"\033[{current_line};1H")
        quit_text = "Press 'q' to quit"
        padding = " " * ((self.width - len(quit_text)) // 2)
        sys.stdout.write(
            f"{self.border_color}│{self.border_reset}{padding}{quit_text}{padding}{self.border_color}│{self.border_reset}"
        )

        # Bottom border
        current_line += 1
        sys.stdout.write(f"\033[{current_line};1H")
        sys.stdout.write(f"{self.border_color}╰{'─' * self.width}╯{self.border_reset}")

        sys.stdout.flush()

    def _center_text(self, text, width, color=None):
        """Center text in given width, accounting for color codes"""
        visible_text = text
        if color:
            visible_text = f"{color}{text}{self.colors['reset']}"

        text_length = len(text)  # Length without color codes
        total_padding = width - text_length
        left_padding = total_padding // 2
        right_padding = total_padding - left_padding

        return f"{' ' * left_padding}{visible_text}{' ' * right_padding}"

    def start(self):
        try:
            print("\033[?25l", end="", flush=True)  # Hide cursor
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())

            while self._running:
                if self.game_over:
                    self.show_game_over()
                    # Wait for restart or quit
                    if select.select([sys.stdin], [], [], 0)[0]:
                        key = sys.stdin.read(1)
                        if key == "r":
                            self.reset_game()
                        elif key == "q":
                            break
                    time.sleep(0.1)
                    continue

                # Handle input
                if select.select([sys.stdin], [], [], 0)[0]:
                    key = sys.stdin.read(1)
                    if key == " ":  # Space bar for jump
                        if self.jumps_left > 0:  # Check if jumps are available
                            self.jumping = True
                            self.jump_count = 0
                            self.jumps_left -= 1
                    elif key == "q":
                        break

                self._update_game()
                self._handle_jump()

                # Clear screen
                sys.stdout.write("\033[H\033[2J")

                board = self._get_board()
                current_line = 1

                # Top border
                sys.stdout.write(f"\033[{current_line};1H")
                sys.stdout.write(
                    f"{self.border_color}╭{'─' * self.width}╮{self.border_reset}"
                )

                # Title
                current_line += 1
                sys.stdout.write(f"\033[{current_line};1H")
                centered_title = self._center_text(
                    "CYBER", self.width, self.colors["neon_pink"]
                )
                sys.stdout.write(
                    f"{self.border_color}│{self.border_reset}{centered_title}{self.border_color}│{self.border_reset}"
                )

                # Computing metrics message
                current_line += 1
                sys.stdout.write(f"\033[{current_line};1H")
                centered_message = self._center_text(
                    "Computing your metrics...", self.width, self.colors["neon_blue"]
                )
                sys.stdout.write(
                    f"{self.border_color}│{self.border_reset}{centered_message}{self.border_color}│{self.border_reset}"
                )

                # Enjoy message
                current_line += 1
                sys.stdout.write(f"\033[{current_line};1H")
                centered_enjoy = self._center_text(
                    "Enjoy the game!", self.width, self.colors["neon_green"]
                )
                sys.stdout.write(
                    f"{self.border_color}│{self.border_reset}{centered_enjoy}{self.border_color}│{self.border_reset}"
                )

                # Board content
                for line in board:
                    current_line += 1
                    sys.stdout.write(f"\033[{current_line};1H")
                    sys.stdout.write(
                        f"{self.border_color}│{self.border_reset}{line}{self.border_color}│{self.border_reset}"
                    )

                # Score
                current_line += 1
                sys.stdout.write(f"\033[{current_line};1H")
                score_str = f"Score: {self.score}"
                padding = " " * ((self.width - len(score_str)) // 2)
                score_text = (
                    f"{self.colors['neon_blue']}{score_str}{self.colors['reset']}"
                )
                if (
                    self.width - len(score_str)
                ) % 2 == 1:  # If odd width, add extra space
                    sys.stdout.write(
                        f"{self.border_color}│{self.border_reset}{padding}{score_text}{padding} {self.border_color}│{self.border_reset}"
                    )
                else:
                    sys.stdout.write(
                        f"{self.border_color}│{self.border_reset}{padding}{score_text}{padding}{self.border_color}│{self.border_reset}"
                    )

                # Lives
                current_line += 1
                sys.stdout.write(f"\033[{current_line};1H")
                hearts = " ".join([self.heart_char] * self.lives)
                lives_str = f"Lives: {hearts}"
                visible_length = len("Lives: ") + (
                    self.lives * 2 - 1
                )  # Account for spaces between hearts
                padding = " " * ((self.width - visible_length) // 2)
                if (
                    self.width - visible_length
                ) % 2 == 1:  # If odd width, add extra space
                    sys.stdout.write(
                        f"{self.border_color}│{self.border_reset}{padding}{lives_str}{padding} {self.border_color}│{self.border_reset}"
                    )
                else:
                    sys.stdout.write(
                        f"{self.border_color}│{self.border_reset}{padding}{lives_str}{padding}{self.border_color}│{self.border_reset}"
                    )

                # Bottom border
                current_line += 1
                sys.stdout.write(f"\033[{current_line};1H")
                sys.stdout.write(
                    f"{self.border_color}╰{'─' * self.width}╯{self.border_reset}"
                )

                sys.stdout.flush()
                time.sleep(0.1)

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            print("\033[?25h", end="", flush=True)  # Show cursor

    def _handle_jump(self):
        """Handle jumping mechanics including double jump"""
        if self.jumping:
            if self.jump_count < len(self.jump_power):
                self.player_pos += self.jump_power[self.jump_count]
                self.jump_count += 1
            else:
                self.jumping = False
                self.jump_count = 0

        # Reset jumps when landing
        if self.player_pos >= self.height - 2:  # When on ground
            self.player_pos = self.height - 2  # Ensure player doesn't go below ground
            self.jumps_left = self.max_jumps
            self.jumping = False
            self.jump_count = 0
        elif not self.jumping:  # If in air and not jumping
            self.player_pos += 1  # Fall down

    def _update_game(self):
        """Update game state"""
        self._update_background()
        self._update_power_ups()
        self._spawn_power_up()

        # Update shield duration
        if self.active_shield:
            self.shield_duration -= 1
            if self.shield_duration <= 0:
                self.active_shield = False
                self.player_char = f"{self.colors['neon_pink']}P{self.colors['reset']}"  # Reset player appearance

        # Update obstacles and score
        for obstacle in self.obstacles[:]:  # Create a copy to modify safely
            obstacle[0] -= 1
            # Add score when passing obstacles
            if obstacle[0] == self.player_x - 1:  # Just passed the obstacle
                self.score += 10  # Add 10 points per obstacle passed

        # Clean up passed obstacles
        self.obstacles = [obs for obs in self.obstacles if obs[0] > 0]

        # Spawn new obstacles
        if random.random() < 0.1 and len(self.obstacles) < 2:
            self.obstacles.append([self.width - 1, self.height - 2])

        # Check collisions only if not shielded
        if not self.active_shield:
            for obstacle in self.obstacles:
                if (
                    abs(obstacle[0] - self.player_x) < 1
                    and abs(obstacle[1] - self.player_pos) < 1
                ):
                    self.lives -= 1
                    if self.lives <= 0:
                        self.game_over = True
                    break

    def _init_background(self):
        self.background = []
        for _ in range(self.height - 1):  # All lines except ground
            line = []
            for _ in range(self.width):
                if random.random() < 0.1:  # 10% chance for a star
                    line.append(random.choice(self.stars))
                else:
                    line.append(" ")
            self.background.append(line)

    def _update_background(self):
        """Update the background stars for parallax effect"""
        # Shift all stars left
        for y in range(len(self.background)):
            # Move stars left
            self.background[y] = self.background[y][1:]
            # Add new column at the right
            if random.random() < 0.1:  # 10% chance for a new star
                self.background[y].append(random.choice(self.stars))
            else:
                self.background[y].append(" ")

    def _spawn_power_up(self):
        """Randomly spawn power-ups"""
        if random.random() < 0.02:  # 2% chance to spawn power-up
            power_up_type = random.choice(list(self.power_up_types.keys()))
            self.power_ups.append(
                {
                    "type": power_up_type,
                    "x": self.width - 1,
                    "y": random.randint(1, self.height - 3),
                }
            )

    def _update_power_ups(self):
        """Update power-ups positions and check collisions"""
        # Move power-ups left
        for power_up in self.power_ups[:]:  # Create a copy to modify safely
            power_up["x"] -= 1

            # Check collision with player (make hitbox slightly larger)
            if (
                abs(power_up["x"] - self.player_x) <= 1
                and abs(power_up["y"] - self.player_pos) <= 1
            ):
                self._collect_power_up(power_up)
                self.power_ups.remove(power_up)
                # Add visual or sound effect here if desired
            # Remove if off screen
            elif power_up["x"] < 0:
                self.power_ups.remove(power_up)

    def _collect_power_up(self, power_up):
        """Handle power-up collection effects"""
        if power_up["type"] == "shield":
            self.active_shield = True
            self.shield_duration = 50  # Shield lasts for 5 seconds
            # Change player appearance when shielded
            self.player_char = self.shield_char
        elif power_up["type"] == "points":
            self.score += 50  # Bonus points
        elif power_up["type"] == "extra_life":
            if self.lives < 5:  # Maximum 5 lives
                self.lives += 1

    def _get_board(self):
        """Generate the current game board with all elements"""
        lines = []

        # Add background and game elements
        for y in range(self.height - 1):
            line = ""
            for x in range(self.width):
                char = self.background[y][x]

                # Check for player (highest priority)
                if y == self.player_pos and x == self.player_x:
                    if self.active_shield:
                        line += self.shield_char
                    else:
                        line += self.player_char
                # Check for power-ups
                elif any(p["x"] == x and p["y"] == y for p in self.power_ups):
                    power_up = next(
                        p for p in self.power_ups if p["x"] == x and p["y"] == y
                    )
                    power_up_info = self.power_up_types[power_up["type"]]
                    line += f"{power_up_info['color']}{power_up_info['char']}{self.colors['reset']}"
                # Check for obstacles
                elif any(obs[0] == x and obs[1] == y for obs in self.obstacles):
                    obstacle_type = random.choice(self.obstacle_types)
                    line += f"{obstacle_type['color']}{obstacle_type['char']}{self.colors['reset']}"
                else:
                    line += char
            lines.append(line)

        # Add ground line
        lines.append(self.ground_char * self.width)
        return lines

    def stop_game(self):
        """Safely stop the game"""
        self._running = False

    def update_score(self, progress):
        """Update game score based on metrics progress"""
        self.score = progress

    def _update_screen(self, board):
        """Update screen with thread safety"""
        with self._screen_lock:
            # Clear screen
            sys.stdout.write("\033[H\033[2J")
            sys.stdout.flush()

            # Write board
            for line in board:
                sys.stdout.write(line + "\n")
            sys.stdout.flush()

    def update(self, progress):
        """Update game state and render"""
        with self._lock:
            self.score = progress
            self._update_game()
            self._render()

    def _render(self):
        """Render the game state using curses"""
        with self._lock:
            # Clear game area
            for y in range(self.height):
                self.screen.move(y, 0)
                self.screen.clrtoeol()

            # Draw game
            board = self._get_board()
            for y, line in enumerate(board):
                self.screen.addstr(y, 0, line)

            self.screen.refresh()

    def cleanup(self):
        """Clean up terminal state"""
        with self._lock:
            self.screen.refresh()
            self.screen.clear()


def play_cyberpunk(stop_event=None, game=None):
    """Run the game in a separate process"""
    if game is None:
        game = CyberpunkRunner()

    # Get exclusive control of terminal
    os.system("clear")

    try:
        # Set up terminal for game
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setraw(fd)

        game.start()
        while not stop_event.is_set():
            time.sleep(0.1)

    finally:
        # Restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        os.system("clear")


if __name__ == "__main__":
    import select
    import termios
    import tty

    game = CyberpunkRunner()
    game.start()
