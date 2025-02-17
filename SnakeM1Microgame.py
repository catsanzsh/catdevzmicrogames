import pygame
import random
import sys
import numpy as np
from pygame import joystick
import os
from time import time
import json
import os.path
import wave  # For saving WAV files
#import struct # Used by wave, but we don't need to import it directly

# Initialize Pygame with Famicom-like settings
pygame.init()
pygame.mixer.init(44100, -16, 2, 2048)  # Increased buffer size for better performance
pygame.joystick.init()  # Initialize joystick support

# Constants
WINDOW_SIZE = 256  # Famicom resolution
GRID_SIZE = 8     # 8x8 pixel tiles like Famicom
GRID_COUNT = WINDOW_SIZE // GRID_SIZE
SCALE = 3         # Scale up for modern displays
FPS = 60          # Increased to 60 FPS
MOVE_INTERVAL = 0.1  # Snake moves every 100ms

DIFFICULTY_SPEEDS = {
    "Easy": 0.15,
    "Normal": 0.1,
    "Hard": 0.07,
    "Expert": 0.05
}

# Famicom color palette (RGB values)
NES_BLACK = (0, 0, 0)
NES_GREEN = (0, 204, 85)  # Authentic NES green
NES_RED = (255, 51, 51)   # Authentic NES red
NES_GRAY = (188, 188, 188)  # For border
NES_BLUE = (0, 117, 255)   # For title text
NES_YELLOW = (255, 236, 39)  # For menu selection
NES_PURPLE = (188, 0, 188)
NES_CYAN = (0, 188, 188)
NES_WHITE = (255, 255, 255)
NES_ORANGE = (255, 188, 0)

# Audio settings (Famicom-like)
SAMPLE_RATE = 44100
DUTY_CYCLE = 0.125  # Square wave duty cycle like NES APU
VOLUME = 0.5  # Default volume
AUDIO_ENABLED = True  # Flag to track audio state
RECORDING_ENABLED = False # flag to turn recording to wav on/off

def init_audio():
    global AUDIO_ENABLED
    try:
        pygame.mixer.quit()  # Reset mixer if already initialized
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=2048)
        pygame.mixer.set_num_channels(8)  # Support more simultaneous sounds
        return True
    except Exception as e:
        print(f"Audio initialization failed: {e}")
        AUDIO_ENABLED = False
        return False

def play_sound(sound, recording_buffer=None):
    """Safe sound playing with error handling and optional recording."""
    if AUDIO_ENABLED and sound:
        try:
            channel = sound.play()
            if RECORDING_ENABLED and recording_buffer is not None:
                if channel:
                    # Capture the sound's sample array for recording
                    sound_array = pygame.sndarray.samples(channel)
                    recording_buffer.append(sound_array)
        except Exception as e:
            print(f"Error playing sound: {e}")


class GameState:
    TITLE = 0
    PLAYING = 1
    PAUSED = 2
    SETTINGS = 3
    CREDITS = 4
    GAME_OVER = 5

class PowerUpType:
    SPEED = 1  # Temporary speed boost
    SHIELD = 2 # One-time wall collision protection
    SCORE = 3  # Double points
    SHRINK = 4 # Shrink snake length

class PowerUp:
    def __init__(self, position, type):
        self.position = position
        self.type = type
        self.duration = 10 * FPS  # 10 seconds
        self.active = False
        self.timer = 0

class Settings:
    def __init__(self):
        self.volume = VOLUME
        self.pro_controller = True if pygame.joystick.get_count() > 0 else False
        self.difficulty = "Normal"
        self.high_scores = self._load_high_scores()
        try:
            if self.pro_controller:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
        except pygame.error:
            self.pro_controller = False

    def _load_high_scores(self):
        try:
            with open("snake_high_scores.json", "r") as f:
                return json.load(f)
        except:
            return {"Easy": 0, "Normal": 0, "Hard": 0, "Expert": 0}
    
    def save_high_score(self, score):
        if score > self.high_scores[self.difficulty]:
            self.high_scores[self.difficulty] = score
            with open("snake_high_scores.json", "w") as f:
                json.dump(self.high_scores, f)
            return True
        return False

def generate_square_wave(frequency, duration, volume=0.3):
    try:
        t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)  # Don't include endpoint
        square = np.where(np.sin(2 * np.pi * frequency * t) > 0, 1, -1)
        samples = (square * volume * 32767).astype(np.int16) # Scale to int16 range
        stereo = np.ascontiguousarray(np.vstack((samples, samples)).T)
        return pygame.sndarray.make_sound(stereo)
    except Exception as e:
        print(f"Error generating sound: {e}")
        return None

def generate_eat_sound():
    # NES-style coin sound
    return generate_square_wave(880, 0.07)  

def generate_move_sound():
    # NES-style movement blip
    return generate_square_wave(220, 0.03, 0.2)

def generate_game_over_sound():
    # NES-style death sound
    duration = 0.4
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)  # Don't include endpoint
    freq = np.linspace(440, 110, len(t))  # Falling pitch
    square = np.where(np.sin(2 * np.pi * freq * t) > 0, 1, -1)
    samples = (square * 0.5 * 32767).astype(np.int16)  # Scale and convert
    stereo = np.ascontiguousarray(np.vstack((samples, samples)).T)
    return pygame.sndarray.make_sound(stereo)

def generate_title_jingle():
    duration = 0.8
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    freqs = [440, 554, 659, 880]  # Famicom style jingle notes
    samples = np.zeros_like(t)
    for i, freq in enumerate(freqs):
        samples += np.sin(2 * np.pi * freq * t) * 0.25 * 32767 * np.exp(-3 * t)
    samples = samples.astype(np.int16)
    stereo = np.ascontiguousarray(np.vstack((samples, samples)).T)
    return pygame.sndarray.make_sound(stereo)

# Generate all sounds
def init_game_sounds():
    global eat_sound, move_sound, game_over_sound, title_sound
    if AUDIO_ENABLED:
        eat_sound = generate_square_wave(880, 0.07)      # Higher pitch for eating
        move_sound = generate_square_wave(220, 0.03, 0.2)  # Lower pitch for movement
        game_over_sound = generate_game_over_sound()
        title_sound = generate_title_jingle()
    else:
        eat_sound = move_sound = game_over_sound = title_sound = None

# Initialize audio system
init_audio()
init_game_sounds()

# Setup display with scaling
screen = pygame.display.set_mode((WINDOW_SIZE * SCALE, WINDOW_SIZE * SCALE))
pygame.display.set_caption('Famicom Snake')  # Fixed caption method
clock = pygame.time.Clock()

# Create a separate surface for native resolution
game_surface = pygame.Surface((WINDOW_SIZE, WINDOW_SIZE))

class Snake:
    def __init__(self):
        self.body = [(GRID_COUNT//2, GRID_COUNT//2)]
        self.direction = [1, 0]
        self.grow = False
        self.moved_this_frame = False
        self.last_move_time = time()
        self.next_direction = None  # Input buffer
        self.dead = False
        self.shield_active = False
        self.speed_multiplier = 1.0
        self.score_multiplier = 1

    def move(self, current_time, recording_buffer):
        if self.dead:
            return False

        # Apply speed multiplier to movement interval
        effective_interval = MOVE_INTERVAL / self.speed_multiplier

        # Only move after interval has passed
        if current_time - self.last_move_time < effective_interval:
            return True

        # Apply buffered direction if it exists
        if self.next_direction:
            if (self.direction[0] + self.next_direction[0] != 0 or 
                self.direction[1] + self.next_direction[1] != 0):
                self.direction = self.next_direction
            self.next_direction = None

        head = self.body[0]
        new_head = (head[0] + self.direction[0], head[1] + self.direction[1])
        
        # Check for wall collision
        if (new_head[0] < 1 or new_head[0] >= GRID_COUNT-1 or 
            new_head[1] < 1 or new_head[1] >= GRID_COUNT-1):
            if self.shield_active:
                self.shield_active = False
                new_head = self._wrap_position(new_head)
            else:
                play_sound(game_over_sound, recording_buffer)
                self.dead = True
                return False

        # Check for self collision
        if new_head in self.body:
            play_sound(game_over_sound, recording_buffer)
            self.dead = True
            return False

        play_sound(move_sound, recording_buffer)
        self.body.insert(0, new_head)
        if not self.grow:
            self.body.pop()
        else:
            self.grow = False
            
        self.last_move_time = current_time
        return True

    def change_direction(self, new_direction):
        # Buffer the input if we can't move yet
        if self.direction[0] + new_direction[0] != 0 or self.direction[1] + new_direction[1] != 0:
            self.next_direction = new_direction

    def _wrap_position(self, pos):
        x, y = pos
        if x < 1: x = GRID_COUNT-2
        if x >= GRID_COUNT-1: x = 1
        if y < 1: y = GRID_COUNT-2
        if y >= GRID_COUNT-1: y = 1
        return (x, y)

def draw_border():
    # Draw NES-style border
    pygame.draw.rect(game_surface, NES_GRAY, (0, 0, WINDOW_SIZE, GRID_SIZE))  # Top
    pygame.draw.rect(game_surface, NES_GRAY, (0, WINDOW_SIZE-GRID_SIZE, WINDOW_SIZE, GRID_SIZE))  # Bottom
    pygame.draw.rect(game_surface, NES_GRAY, (0, 0, GRID_SIZE, WINDOW_SIZE))  # Left
    pygame.draw.rect(game_surface, NES_GRAY, (WINDOW_SIZE-GRID_SIZE, 0, GRID_SIZE, WINDOW_SIZE))  # Right

class TitleScreen:
    def __init__(self):
        self.options = ["Start Game", "Settings", "Credits", "Exit"]
        self.selected = 0
        self.blink_timer = 0
        self.show_cursor = True
        
    def draw(self, surface):
        surface.fill(NES_BLACK)
        draw_border()
        
        # Draw title
        font_big = pygame.font.Font(None, 36)
        title = font_big.render("FAMICOM SNAKE", True, NES_BLUE)
        surface.blit(title, (WINDOW_SIZE//2 - title.get_width()//2, 30))
        
        # Draw menu options
        font = pygame.font.Font(None, 24)
        for i, option in enumerate(self.options):
            color = NES_YELLOW if i == self.selected else NES_GREEN
            if i == self.selected and self.show_cursor:
                text = "> " + option
            else:
                text = "  " + option
            option_text = font.render(text, True, color)
            surface.blit(option_text, (WINDOW_SIZE//2 - option_text.get_width()//2, 100 + i*30))

    def update(self):
        self.blink_timer += 1
        if self.blink_timer >= 15:  # Blink every 15 frames
            self.show_cursor = not self.show_cursor
            self.blink_timer = 0

class Game:
    def __init__(self):
        self.state = GameState.TITLE
        self.settings = Settings()
        self.title_screen = TitleScreen()
        self.snake = None
        self.food = None
        self.score = 0
        self.power_ups = []
        self.power_up_spawn_timer = 0
        self.high_score = False
        self.last_frame_time = time()
        self.recording_buffer = []  # Buffer to store sound data
        self.output_filename = "game_audio.wav" # default filename


    def handle_input(self, event):
        if self.state == GameState.TITLE:
            self._handle_title_input(event)
        elif self.state == GameState.PLAYING:
            self._handle_game_input(event)

    def _handle_title_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.title_screen.selected = (self.title_screen.selected - 1) % len(self.title_screen.options)
                play_sound(move_sound, self.recording_buffer)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.title_screen.selected = (self.title_screen.selected + 1) % len(self.title_screen.options)
                play_sound(move_sound, self.recording_buffer)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._select_menu_option()
            elif event.key == pygame.K_d:
                difficulties = list(DIFFICULTY_SPEEDS.keys())
                current_idx = difficulties.index(self.settings.difficulty)
                self.settings.difficulty = difficulties[(current_idx + 1) % len(difficulties)]
                play_sound(move_sound, self.recording_buffer)


        # Pro Controller support
        if self.settings.pro_controller:
            try:
                if event.type == pygame.JOYBUTTONDOWN:
                    if event.button == 0:  # A button
                        self._select_menu_option()
                elif event.type == pygame.JOYAXISMOTION:
                    if event.axis == 1:  # Vertical axis
                        if event.value < -0.5:  # Up
                            self.title_screen.selected = (self.title_screen.selected - 1) % len(self.title_screen.options)
                            play_sound(move_sound, self.recording_buffer)
                        elif event.value > 0.5:  # Down
                            self.title_screen.selected = (self.title_screen.selected + 1) % len(self.title_screen.options)
                            play_sound(move_sound, self.recording_buffer)
            except pygame.error:
                pass

    def _select_menu_option(self):
        option = self.title_screen.options[self.title_screen.selected]
        if option == "Start Game":
            self._start_new_game()
        elif option == "Exit":
            self.quit_game()  # Call the quit_game method

        play_sound(eat_sound, self.recording_buffer)  # Use safe sound playing

    def _start_new_game(self):
        self.state = GameState.PLAYING
        self.snake = Snake()
        self.food = (random.randint(1, GRID_COUNT-2), random.randint(1, GRID_COUNT-2))
        self.score = 0
        self.power_ups = []
        self.power_up_spawn_timer = 0
        self.high_score = False
        play_sound(title_sound, self.recording_buffer)

    def _handle_game_input(self, event):
        """Handle input during gameplay"""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a) and not self.snake.moved_this_frame:
                self.snake.change_direction([-1, 0])
            elif event.key in (pygame.K_RIGHT, pygame.K_d) and not self.snake.moved_this_frame:
                self.snake.change_direction([1, 0])
            elif event.key in (pygame.K_UP, pygame.K_w) and not self.snake.moved_this_frame:
                self.snake.change_direction([0, -1])
            elif event.key in (pygame.K_DOWN, pygame.K_s) and not self.snake.moved_this_frame:
                self.snake.change_direction([0, 1])
            elif event.key == pygame.K_ESCAPE:
                self.state = GameState.TITLE
            elif event.key == pygame.K_r:  # Toggle recording with 'r' key
                global RECORDING_ENABLED
                RECORDING_ENABLED = not RECORDING_ENABLED
                print(f"Recording: {'Enabled' if RECORDING_ENABLED else 'Disabled'}")
                if not RECORDING_ENABLED and self.recording_buffer:
                  self.save_recording()
                  self.recording_buffer = []


        
        # Pro Controller support 
        if self.settings.pro_controller:
            try:
                if event.type == pygame.JOYBUTTONDOWN:  
                    if event.button == 0:  # A button
                        pass  # Could add pause functionality here
                elif event.type == pygame.JOYAXISMOTION:
                    if event.axis < 2:  # Only handle the first two axes (left stick)
                        if event.axis == 0:  # X axis
                            if event.value < -0.5:  # Left
                                self.snake.change_direction([-1, 0])
                            elif event.value > 0.5:  # Right  
                                self.snake.change_direction([1, 0])
                        elif event.axis == 1:  # Y axis
                            if event.value < -0.5:  # Up
                                self.snake.change_direction([0, -1])
                            elif event.value > 0.5:  # Down
                                self.snake.change_direction([0, 1])
            except pygame.error:
                pass

    def run(self):
        running = True
        while running:
            current_time = time()
            frame_time = current_time - self.last_frame_time
            self.last_frame_time = current_time

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                self.handle_input(event)

            game_surface.fill(NES_BLACK)
            
            if self.state == GameState.TITLE:
                self.title_screen.update()
                self.title_screen.draw(game_surface)
            elif self.state == GameState.PLAYING:
                self._update_game()
                self._draw_game()

            # Scale and display
            scaled_surface = pygame.transform.scale(game_surface, 
                                                 (WINDOW_SIZE * SCALE, WINDOW_SIZE * SCALE))
            screen.blit(scaled_surface, (0, 0))
            pygame.display.flip()
            
            # Maintain consistent 60 FPS
            clock.tick(FPS)
        self.quit_game()

    def quit_game(self):
        if RECORDING_ENABLED and self.recording_buffer:
            self.save_recording()  # Save any remaining audio before exiting
        pygame.quit()
        sys.exit()



    def _update_game(self):
        current_time = time()
        
        # Update power-ups
        self._update_power_ups()
        
        # Spawn new power-up
        self.power_up_spawn_timer += 1
        if self.power_up_spawn_timer >= FPS * 15:  # Every 15 seconds
            self._spawn_power_up()
            self.power_up_spawn_timer = 0
            
        if not self.snake.move(current_time, self.recording_buffer):
            if not self.high_score:
                self.high_score = self.settings.save_high_score(self.score)
            self.state = GameState.GAME_OVER
            return

        # Check power-up collection
        for power_up in self.power_ups[:]:
            if self.snake.body[0] == power_up.position:
                self._apply_power_up(power_up)
                self.power_ups.remove(power_up)

        if self.snake.body[0] == self.food:
            play_sound(eat_sound, self.recording_buffer)
            self.snake.grow = True
            self.score += 1 * self.snake.score_multiplier
            # Make sure food doesn't spawn on snake or borders
            while True:
                new_food = (random.randint(1, GRID_COUNT-2), random.randint(1, GRID_COUNT-2))
                if new_food not in self.snake.body:
                    self.food = new_food
                    break

    def _spawn_power_up(self):
        while True:
            pos = (random.randint(1, GRID_COUNT-2), random.randint(1, GRID_COUNT-2))
            if pos not in self.snake.body and pos != self.food:
                break
        power_type = random.choice([PowerUpType.SPEED, PowerUpType.SHIELD, 
                                  PowerUpType.SCORE, PowerUpType.SHRINK])
        self.power_ups.append(PowerUp(pos, power_type))

    def _apply_power_up(self, power_up):
        if power_up.type == PowerUpType.SPEED:
            self.snake.speed_multiplier = 1.5
            power_up.active = True
        elif power_up.type == PowerUpType.SHIELD:
            self.snake.shield_active = True
        elif power_up.type == PowerUpType.SCORE:
            self.snake.score_multiplier = 2
            power_up.active = True
        elif power_up.type == PowerUpType.SHRINK:
            if len(self.snake.body) > 3:
                self.snake.body = self.snake.body[:-2]

    def _update_power_ups(self):
        for power_up in self.power_ups[:]:
            if power_up.active:
                power_up.timer += 1
                if power_up.timer >= power_up.duration:
                    if power_up.type == PowerUpType.SPEED:
                        self.snake.speed_multiplier = 1.0
                    elif power_up.type == PowerUpType.SCORE:
                        self.snake.score_multiplier = 1
                    self.power_ups.remove(power_up)

    def _draw_game(self):
        draw_border()
        
        # Draw food
        food_size = GRID_SIZE - 1
        food_x = self.food[0] * GRID_SIZE + (GRID_SIZE - food_size) // 2
        food_y = self.food[1] * GRID_SIZE + (GRID_SIZE - food_size) // 2
        pygame.draw.rect(game_surface, NES_RED, 
                        (food_x, food_y, food_size, food_size))
        
        # Draw snake
        for segment in self.snake.body:
            pygame.draw.rect(game_surface, NES_GREEN,
                           (segment[0]*GRID_SIZE+1, segment[1]*GRID_SIZE+1,
                            GRID_SIZE-2, GRID_SIZE-2))

        # Draw power-ups
        for power_up in self.power_ups:
            color = {
                PowerUpType.SPEED: NES_CYAN,
                PowerUpType.SHIELD: NES_PURPLE,
                PowerUpType.SCORE: NES_ORANGE,
                PowerUpType.SHRINK: NES_WHITE
            }[power_up.type]
            
            pygame.draw.rect(game_surface, color,
                           (power_up.position[0]*GRID_SIZE+1,
                            power_up.position[1]*GRID_SIZE+1,
                            GRID_SIZE-2, GRID_SIZE-2))

        # Draw effects
        if self.snake.shield_active:
            head = self.snake.body[0]
            pygame.draw.rect(game_surface, NES_PURPLE,
                           (head[0]*GRID_SIZE, head[1]*GRID_SIZE,
                            GRID_SIZE, GRID_SIZE), 1)

        # Enhanced HUD
        font = pygame.font.Font(None, 20)
        score_text = font.render(f"SCORE:{self.score}", True, NES_YELLOW)
        high_score_text = font.render(f"HI-SCORE:{self.settings.high_scores[self.settings.difficulty]}", True, NES_ORANGE)
        level_text = font.render(f"LEVEL:{self.settings.difficulty}", True, NES_CYAN)
        
        game_surface.blit(score_text, (8, 8))
        game_surface.blit(high_score_text, (8, 24))
        game_surface.blit(level_text, (WINDOW_SIZE - 80, 8))
    def save_recording(self):
        """Saves the recorded audio data to a WAV file."""
        if not self.recording_buffer:
            print("No audio data to save.")
            return

        print(f"Saving recording to {self.output_filename}")

        try:
           # Flatten the list of arrays into a single array
            all_samples = np.concatenate(self.recording_buffer, axis=0)

            # Ensure the data type is int16
            all_samples = all_samples.astype(np.int16)
            # Convert to bytes
            audio_data = all_samples.tobytes()
            
            with wave.open(self.output_filename, 'wb') as wf:
                wf.setnchannels(2)  # Stereo
                wf.setsampwidth(2)  # 2 bytes for int16
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(audio_data)
            print ("file saved")

        except Exception as e:
            print(f"Error saving WAV file: {e}")


if __name__ == "__main__":
    try:
        game = Game()
        game.run()
    except Exception as e:
        print(f"Error: {e}")
        pygame.quit()
        sys.exit(1)
