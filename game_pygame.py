import pygame
import threading
import queue
import random
import json
import math
import os
import asyncio
import edge_tts
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import traceback
import time

import sys
import os

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))


MODEL_PATH = os.path.join(BASE_DIR, "models", "vosk-model-small-ru-0.22")
CACHE_DIR = os.path.join(BASE_DIR, "assets", "tts_cache")
CUSTOM_WORDS_FILE = os.path.join(BASE_DIR, "custom_words.json")
os.makedirs(CACHE_DIR, exist_ok=True)

DEFAULT_WORDS = {
    "easy": ["сом", "рак", "лук", "суп", "мак", "кот", "дом", "бык", "сыр", "квас"],
    "medium": ["рыба", "лодка", "вода", "удочка", "щука", "ведро", "кошка", "мышка", "шапка", "лиса", "каша", "шуба"],
    "hard": ["акула", "черепаха", "кашалот", "сковорода", "электричество", "чебурашка", "кукуруза", "барабан", "карандаш", "самолет", "помидор", "виноград"]
}

def load_custom_words():
    if os.path.exists(CUSTOM_WORDS_FILE):
        try:
            with open(CUSTOM_WORDS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key in DEFAULT_WORDS:
                    if key not in data or not data[key]:
                        data[key] = DEFAULT_WORDS[key].copy()
                return data
        except:
            pass
    return {k: v.copy() for k, v in DEFAULT_WORDS.items()}

def save_custom_words(data):
    with open(CUSTOM_WORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

custom_words = load_custom_words()
save_custom_words(custom_words)

COLOR_MAP = {
    "red": (220, 60, 60), "green": (60, 180, 60), "blue": (60, 100, 220),
    "yellow": (230, 200, 50), "purple": (150, 60, 180), "orange": (230, 130, 40),
    "pink": (230, 120, 160), "cyan": (60, 200, 200), "gray": (128, 128, 128),
    "black": (40, 40, 40)
}
COLORS_RU = {
    "red": "красную", "green": "зеленую", "blue": "синюю", "yellow": "желтую", 
    "purple": "фиолетовую", "orange": "оранжевую", "pink": "розовую", 
    "cyan": "голубую", "gray": "серую", "black": "черную", "white": "белую",
    "dark": "темную", "bright": "яркую"
}
SIZES_RU = {
    "tiny": "маленькую", "medium": "среднюю", "huge": "огромную", "giant": "гигантскую"
}

pygame.init()
pygame.mixer.init()
pygame.mixer.set_num_channels(8)

WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Логопедическая рыбалка")
clock = pygame.time.Clock()

font_big = pygame.font.SysFont("Arial", 50, bold=True)
font_med = pygame.font.SysFont("Arial", 28, bold=True)
font_small = pygame.font.SysFont("Arial", 18)
font_ui = pygame.font.SysFont("Arial", 14, bold=True)
font_menu = pygame.font.SysFont("Arial", 22, bold=True)

def draw_text_outlined(surface, text, font, x, y, text_color, outline_color, outline_width=2, center=False):
    base = font.render(text, True, text_color)
    outline = font.render(text, True, outline_color)
    if center:
        rect = base.get_rect(center=(x, y))
    else:
        rect = base.get_rect(topleft=(x, y))
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx*dx + dy*dy <= outline_width*outline_width:
                surface.blit(outline, (rect.x + dx, rect.y + dy))
    surface.blit(base, rect)
    return rect

MAX_MUSIC_VOL = 0.3
MAX_FX_VOL = 1.0
vol_music = 0.1
vol_fx = 0.8

sound_catch = None
sound_splash = None
sound_cat_eat = None 

if os.path.exists(os.path.join(BASE_DIR, "assets", "sounds", "catch.wav")):
    sound_catch = pygame.mixer.Sound(os.path.join(BASE_DIR, "assets", "sounds", "catch.wav"))
if os.path.exists(os.path.join(BASE_DIR, "assets", "sounds", "splash.wav")):
    sound_splash = pygame.mixer.Sound(os.path.join(BASE_DIR, "assets", "sounds", "splash.wav"))
if os.path.exists(os.path.join(BASE_DIR, "assets", "sounds", "cat_eat.wav")):
    sound_cat_eat = pygame.mixer.Sound(os.path.join(BASE_DIR, "assets", "sounds", "cat_eat.wav"))
if os.path.exists(os.path.join(BASE_DIR, "assets", "sounds", "music.mp3")):
    pygame.mixer.music.load(os.path.join(BASE_DIR, "assets", "sounds", "music.mp3"))
    pygame.mixer.music.play(-1)

def update_volumes():
    pygame.mixer.music.set_volume(vol_music * MAX_MUSIC_VOL)
    if sound_catch: sound_catch.set_volume(vol_fx * MAX_FX_VOL)
    if sound_splash: sound_splash.set_volume(vol_fx * MAX_FX_VOL)
    if sound_cat_eat: sound_cat_eat.set_volume(vol_fx * MAX_FX_VOL)

update_volumes()

tts_lock = threading.Lock()
is_speaking = False

def get_audio_filename(text):
    safe_text = "".join([c if c.isalnum() else "_" for c in text]).lower()
    return os.path.join(CACHE_DIR, f"{safe_text}.mp3")

def generate_tts_async(text):
    filepath = get_audio_filename(text)
    if os.path.exists(filepath):
        return
    def run():
        try:
            voice = "ru-RU-SvetlanaNeural"
            communicate = edge_tts.Communicate(text, voice, pitch="+25Hz", rate="+5%")
            asyncio.run(communicate.save(filepath))
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()

# Измененная функция: сначала ждем звук поедания, потом говорим
def speak_commentary_after_eat(text, eat_duration):
    global is_speaking
    filepath = get_audio_filename(text)
    if not os.path.exists(filepath):
        generate_tts_async(text)
        return
    
    with tts_lock:
        if is_speaking:
            return
        is_speaking = True
        
    def run_sequence():
        global is_speaking
        try:
            time.sleep(eat_duration) # Ждем, пока кот жует
            
            sound = pygame.mixer.Sound(filepath)
            sound.set_volume(vol_fx * MAX_FX_VOL)
            sound.play()
            time.sleep(sound.get_length())
        except Exception:
            pass
        finally:
            with tts_lock:
                is_speaking = False

    threading.Thread(target=run_sequence, daemon=True).start()

# Обычное произнесение (для клика по рыбке)
def speak_text(text):
    speak_commentary_after_eat(text, 0)

class Slider:
    def __init__(self, x, y, w, h, value):
        self.rect = pygame.Rect(x, y, w, h)
        self.value = value
        self.dragging = False

    def draw(self, surface):
        pygame.draw.rect(surface, (80, 80, 80), self.rect, border_radius=5)
        fill_width = int(self.rect.width * self.value)
        fill_rect = pygame.Rect(self.rect.x, self.rect.y, fill_width, self.rect.height)
        pygame.draw.rect(surface, (0, 200, 255), fill_rect, border_radius=5)
        knob_x = self.rect.x + fill_width
        pygame.draw.circle(surface, (255, 255, 255), (knob_x, self.rect.centery), self.rect.height // 2 + 2)
        pygame.draw.circle(surface, (0,0,0), (knob_x, self.rect.centery), self.rect.height // 2 + 2, 1)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.inflate(0, 15).collidepoint(event.pos):
                self.dragging = True
                self.update_value(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.update_value(event.pos[0])

    def update_value(self, mouse_x):
        rel_x = max(0, min(mouse_x - self.rect.x, self.rect.width))
        self.value = rel_x / self.rect.width

slider_music = Slider(160, 18, 80, 8, vol_music)
slider_fx = Slider(370, 18, 80, 8, vol_fx)

class Fish:
    def __init__(self, difficulty):
        self.difficulty = difficulty
        if difficulty == 0:
            pool = custom_words["easy"]
            self.word = random.choice(pool) if pool else None
            self.size = random.uniform(0.6, 0.8)
            self.color = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
            self.tail_type = 0
            self.size_desc = "tiny"
        elif difficulty == 1:
            pool = custom_words["medium"]
            self.word = random.choice(pool) if pool else None
            self.size = random.uniform(0.9, 1.2)
            self.color = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
            self.tail_type = random.randint(0, 1)
            self.size_desc = "medium"
        else:
            pool = custom_words["hard"]
            self.word = random.choice(pool) if pool else None
            self.size = random.uniform(1.5, 2.2)
            self.color = (random.randint(50, 150), random.randint(50, 150), random.randint(50, 150))
            self.tail_type = 2
            self.size_desc = "huge" if self.size < 1.8 else "giant"

        if self.word:
            r, g, b = self.color
            best_match = "bright"
            min_dist = float('inf')
            for color_name, (cr, cg, cb) in COLOR_MAP.items():
                dist = (r-cr)**2 + (g-cg)**2 + (b-cb)**2
                if dist < min_dist:
                    min_dist = dist
                    best_match = color_name
            
            if r < 80 and g < 80 and b < 80: self.color_desc = "black"
            elif r > 200 and g > 200 and b > 200: self.color_desc = "white"
            else: self.color_desc = best_match
            
            generate_tts_async(self.word)
            generate_tts_async(self.get_comment())

        self.body_w = 120 * self.size
        self.body_h = 70 * self.size
        self.fin_size = 40 * self.size
        self.tail_size = 25 * self.size

    def get_comment(self):
        if not self.word: return ""
        return f"Молодец! Ты поймал {SIZES_RU[self.size_desc]} {COLORS_RU[self.color_desc]} рыбку!"

    def draw(self, surface, x, y, state, time_val):
        if not self.word: return pygame.Rect(0,0,0,0)
        
        bob = math.sin(time_val * 3) * 5 if state != "flying" else 0
        y += bob
        outline_color = (0, 0, 0)
        ow = max(2, int(3 * self.size))
        hitbox = pygame.Rect(x - self.body_w//2 - self.tail_size, y - self.body_h//2, self.body_w + self.tail_size, self.body_h)
        
        if self.tail_type == 0:
            pts = [(x-self.body_w//2, y), (x-self.body_w//2 - self.tail_size, y-self.tail_size), (x-self.body_w//2 - self.tail_size, y+self.tail_size)]
            pygame.draw.polygon(surface, self.color, pts)
            pygame.draw.polygon(surface, outline_color, pts, ow)
            pygame.draw.line(surface, outline_color, (x-self.body_w//2, y), (x-self.body_w//2 - self.tail_size, y-self.tail_size//2), max(1, ow//2))
            pygame.draw.line(surface, outline_color, (x-self.body_w//2, y), (x-self.body_w//2 - self.tail_size, y+self.tail_size//2), max(1, ow//2))
        elif self.tail_type == 1:
            pts1 = [(x-self.body_w//2, y), (x-self.body_w//2 - self.tail_size, y-self.tail_size), (x-self.body_w//2 - self.tail_size//2, y)]
            pts2 = [(x-self.body_w//2, y), (x-self.body_w//2 - self.tail_size, y+self.tail_size), (x-self.body_w//2 - self.tail_size//2, y)]
            pygame.draw.polygon(surface, self.color, pts1)
            pygame.draw.polygon(surface, outline_color, pts1, ow)
            pygame.draw.polygon(surface, self.color, pts2)
            pygame.draw.polygon(surface, outline_color, pts2, ow)
        else:
            pts = [(x-self.body_w//2, y), (x-self.body_w//2 - self.tail_size*1.5, y-self.tail_size*1.5), (x-self.body_w//2 - self.tail_size, y)]
            pygame.draw.polygon(surface, self.color, pts)
            pygame.draw.polygon(surface, outline_color, pts, ow)

        fin_pts = [(x-self.body_w//4, y-self.body_h//2), (x, y-self.body_h//2 - self.fin_size), (x+self.body_w//4, y-self.body_h//2)]
        pygame.draw.polygon(surface, self.color, fin_pts)
        pygame.draw.polygon(surface, outline_color, fin_pts, ow)
        pygame.draw.line(surface, outline_color, (x-self.body_w//4, y-self.body_h//2), (x, y-self.body_h//2 - self.fin_size//2), max(1, ow//2))
        pygame.draw.line(surface, outline_color, (x+self.body_w//4, y-self.body_h//2), (x, y-self.body_h//2 - self.fin_size//2), max(1, ow//2))
        
        body_rect = (x-self.body_w//2, y-self.body_h//2, self.body_w, self.body_h)
        pygame.draw.ellipse(surface, self.color, body_rect)
        pygame.draw.ellipse(surface, outline_color, body_rect, ow)
        
        side_fin_pts = [(x-self.body_w//4, y+self.body_h//4), (x-self.body_w//6, y+self.body_h//2), (x, y+self.body_h//4)]
        pygame.draw.polygon(surface, self.color, side_fin_pts)
        pygame.draw.polygon(surface, outline_color, side_fin_pts, max(1, ow-1))

        eye_x = x + self.body_w//4
        eye_y = y - self.body_h//6
        eye_r = int(10 * self.size)
        pygame.draw.circle(surface, (255, 255, 255), (int(eye_x), int(eye_y)), eye_r)
        pygame.draw.circle(surface, outline_color, (int(eye_x), int(eye_y)), eye_r, 2)
        pygame.draw.circle(surface, (0, 0, 0), (int(eye_x + 3), int(eye_y)), int(5 * self.size))
        pygame.draw.circle(surface, (255, 255, 255), (int(eye_x + 5), int(eye_y - 2)), int(2 * self.size))
        
        mouth_rect = (x+self.body_w//3, y+self.body_h//6 if state == "confused" else y, int(15*self.size), int(15*self.size))
        pygame.draw.arc(surface, outline_color, mouth_rect, 0 if state == "confused" else math.pi, math.pi if state == "confused" else 2*math.pi, 2)

        text_rect = font_big.render(self.word.upper(), True, (0,0,0)).get_rect(center=(x, y - self.body_h//2 - 60))
        bubble_rect = text_rect.inflate(40, 20)
        pygame.draw.rect(surface, (255, 255, 255), bubble_rect, border_radius=20)
        pygame.draw.rect(surface, (100, 200, 255), bubble_rect, width=4, border_radius=20)
        bubble_tail = [(x-10, bubble_rect.bottom-5), (x+10, bubble_rect.bottom-5), (x, bubble_rect.bottom+15)]
        pygame.draw.polygon(surface, (255, 255, 255), bubble_tail)
        pygame.draw.polygon(surface, (100, 200, 255), bubble_tail, 4)
        
        draw_text_outlined(surface, self.word.upper(), font_big, x, y - self.body_h//2 - 60, (50, 50, 150), (0,0,0), 2, center=True)
        return hitbox

class BgFish:
    def __init__(self):
        self.x = random.randint(0, WIDTH)
        self.y = random.randint(HEIGHT//2 + 50, HEIGHT - 50)
        self.speed = random.uniform(20, 60)
        self.size = random.randint(10, 30)
        self.color = (random.randint(100, 200), random.randint(100, 200), random.randint(100, 200))
        self.offset = random.uniform(0, math.pi * 2)

    def update(self, dt, time_val):
        self.x -= self.speed * dt
        if self.x < -50:
            self.x = WIDTH + 50
            self.y = random.randint(HEIGHT//2 + 50, HEIGHT - 50)
        self.current_y = self.y + math.sin(time_val * 2 + self.offset) * 10

    def draw(self, surface):
        pygame.draw.ellipse(surface, self.color, (self.x, self.current_y, self.size*2, self.size))
        pygame.draw.ellipse(surface, (0,0,0), (self.x, self.current_y, self.size*2, self.size), 1)
        pts = [(self.x, self.current_y + self.size//2), (self.x - self.size, self.current_y), (self.x - self.size, self.current_y + self.size)]
        pygame.draw.polygon(surface, self.color, pts)
        pygame.draw.polygon(surface, (0,0,0), pts, 1)

bg_fishes = [BgFish() for _ in range(7)]

def draw_background(surface, time_val):
    for y in range(HEIGHT // 2):
        color = (135 + int(y * 0.1), 206 + int(y * 0.05), 235)
        pygame.draw.line(surface, color, (0, y), (WIDTH, y))
    pygame.draw.circle(surface, (255, 230, 100), (700, 80), 40)
    pygame.draw.circle(surface, (255, 200, 50), (700, 80), 40, 2)
    cloud_x = (time_val * 20) % (WIDTH + 200) - 100
    for offset in [0, 250, 500]:
        cx = (cloud_x + offset) % (WIDTH + 200) - 100
        pygame.draw.ellipse(surface, (255, 255, 255), (cx, 50, 100, 40))
        pygame.draw.ellipse(surface, (255, 255, 255), (cx + 30, 30, 80, 50))

    for y in range(HEIGHT // 2, HEIGHT):
        color = (30, 100 - (y - HEIGHT // 2) // 10, 150 - (y - HEIGHT // 2) // 5)
        pygame.draw.line(surface, color, (0, y), (WIDTH, y))
    for i in range(5):
        offset = math.sin(time_val * 2 + i) * 20
        pygame.draw.line(surface, (100, 200, 255), (100 + i * 150 + offset, HEIGHT//2 + 50), (150 + i * 150 + offset, HEIGHT//2 + 50), 2)

def draw_fisherman_and_basket(surface, caught_fish, cat_eating_timer):
    boat_pts = [(50, 450), (220, 450), (190, 500), (80, 500)]
    pygame.draw.polygon(surface, (139, 69, 19), boat_pts)
    pygame.draw.polygon(surface, (80, 40, 10), boat_pts, 4)
    pygame.draw.polygon(surface, (100, 50, 20), [(60, 450), (210, 450), (185, 490), (85, 490)])
    pygame.draw.line(surface, (80, 40, 10), (70, 465), (195, 465), 2)
    pygame.draw.line(surface, (80, 40, 10), (75, 480), (185, 480), 2)
    
    basket_rect = pygame.Rect(20, 380, 90, 90)
    pygame.draw.rect(surface, (160, 82, 45), basket_rect, border_radius=5)
    pygame.draw.rect(surface, (80, 40, 10), basket_rect, width=3, border_radius=5)
    for i in range(10, 90, 15):
        pygame.draw.line(surface, (100, 50, 20), (20, 380+i), (110, 380+i), 2)
    for i in range(20, 90, 20):
        pygame.draw.line(surface, (100, 50, 20), (20+i, 380), (20+i, 470), 2)
    pygame.draw.ellipse(surface, (120, 60, 30), (15, 370, 100, 20))
    pygame.draw.ellipse(surface, (80, 40, 10), (15, 370, 100, 20), 3)
    
    # --- МИЛЫЙ КОТИК ---
    cat_x, cat_y = 65, 365
    outline_cat = (0, 0, 0)
    
    # Хвост (закрученный влево)
    pygame.draw.arc(surface, (60, 60, 60), (cat_x - 50, cat_y - 10, 40, 40), math.pi/4, math.pi*1.5, 6)
    pygame.draw.arc(surface, outline_cat, (cat_x - 50, cat_y - 10, 40, 40), math.pi/4, math.pi*1.5, 2)

    # Тело
    pygame.draw.ellipse(surface, (60, 60, 60), (cat_x - 25, cat_y - 5, 50, 35))
    pygame.draw.ellipse(surface, outline_cat, (cat_x - 25, cat_y - 5, 50, 35), 2)
    
    # Уши (закругленные)
    pygame.draw.circle(surface, (60, 60, 60), (cat_x - 15, cat_y - 25), 10)
    pygame.draw.circle(surface, outline_cat, (cat_x - 15, cat_y - 25), 10, 2)
    pygame.draw.circle(surface, (60, 60, 60), (cat_x + 15, cat_y - 25), 10)
    pygame.draw.circle(surface, outline_cat, (cat_x + 15, cat_y - 25), 10, 2)
    
    # Голова
    pygame.draw.circle(surface, (60, 60, 60), (cat_x, cat_y - 15), 22)
    pygame.draw.circle(surface, outline_cat, (cat_x, cat_y - 15), 22, 2)

    # Щечки (белые)
    pygame.draw.ellipse(surface, (230, 230, 230), (cat_x - 18, cat_y - 12, 12, 8))
    pygame.draw.ellipse(surface, (230, 230, 230), (cat_x + 6, cat_y - 12, 12, 8))
    
    # Глаза
    pygame.draw.circle(surface, (255, 255, 0), (cat_x - 8, cat_y - 18), 5)
    pygame.draw.circle(surface, (255, 255, 0), (cat_x + 8, cat_y - 18), 5)
    pygame.draw.circle(surface, (0, 0, 0), (cat_x - 8, cat_y - 18), 2)
    pygame.draw.circle(surface, (0, 0, 0), (cat_x + 8, cat_y - 18), 2)
    
    # Нос (розовый)
    pygame.draw.polygon(surface, (255, 150, 150), [(cat_x, cat_y - 10), (cat_x - 3, cat_y - 7), (cat_x + 3, cat_y - 7)])
    pygame.draw.polygon(surface, outline_cat, [(cat_x, cat_y - 10), (cat_x - 3, cat_y - 7), (cat_x + 3, cat_y - 7)], 1)
    
    # Рот
    if cat_eating_timer > 0:
        pygame.draw.ellipse(surface, (30, 30, 30), (cat_x - 8, cat_y - 5, 16, 12))
        pygame.draw.ellipse(surface, outline_cat, (cat_x - 8, cat_y - 5, 16, 12), 1)
        pygame.draw.polygon(surface, (255, 255, 255), [(cat_x - 6, cat_y - 3), (cat_x - 4, cat_y + 3), (cat_x - 2, cat_y - 3)])
        pygame.draw.polygon(surface, (255, 255, 255), [(cat_x + 2, cat_y - 3), (cat_x + 4, cat_y + 3), (cat_x + 6, cat_y - 3)])
    else:
        pygame.draw.arc(surface, outline_cat, (cat_x - 8, cat_y - 8, 16, 12), 0, math.pi, 2)
        
    # Усы
    pygame.draw.line(surface, (255, 255, 255), (cat_x - 10, cat_y - 5), (cat_x - 25, cat_y - 8), 1)
    pygame.draw.line(surface, (255, 255, 255), (cat_x - 10, cat_y - 3), (cat_x - 25, cat_y - 2), 1)
    pygame.draw.line(surface, (255, 255, 255), (cat_x + 10, cat_y - 5), (cat_x + 25, cat_y - 8), 1)
    pygame.draw.line(surface, (255, 255, 255), (cat_x + 10, cat_y - 3), (cat_x + 25, cat_y - 2), 1)

    if cat_eating_timer <= 0:
        for i, f in enumerate(caught_fish):
            if i >= 5: break
            fx = 30 + (i % 3) * 20
            fy = 390 + (i // 3) * 20
            pygame.draw.ellipse(surface, f.color, (fx, fy, 20, 10))
            pygame.draw.ellipse(surface, (0,0,0), (fx, fy, 20, 10), 1)
            pygame.draw.polygon(surface, f.color, [(fx, fy+5), (fx-8, fy), (fx-8, fy+10)])
            pygame.draw.polygon(surface, (0,0,0), [(fx, fy+5), (fx-8, fy), (fx-8, fy+10)], 1)

    # Рыбак
    pygame.draw.rect(surface, (200, 50, 50), (125, 350, 25, 50), border_radius=8)
    pygame.draw.rect(surface, (150, 30, 30), (125, 350, 25, 50), 3, border_radius=8)
    pygame.draw.rect(surface, (200, 50, 50), (110, 350, 40, 100), border_radius=10)
    pygame.draw.rect(surface, (150, 30, 30), (110, 350, 40, 100), 3, border_radius=10)
    pygame.draw.rect(surface, (100, 200, 100), (115, 370, 30, 70), border_radius=5)
    pygame.draw.rect(surface, (50, 150, 50), (115, 370, 30, 70), 2, border_radius=5)
    
    pygame.draw.circle(surface, (255, 220, 180), (130, 330), 25)
    pygame.draw.circle(surface, (200, 150, 100), (130, 330), 25, 3)
    beard_pts = [(115, 340), (130, 365), (145, 340), (130, 350)]
    pygame.draw.polygon(surface, (220, 220, 220), beard_pts)
    pygame.draw.polygon(surface, (150, 150, 150), beard_pts, 2)
    pygame.draw.circle(surface, (0, 0, 0), (120, 325), 3)
    pygame.draw.circle(surface, (0, 0, 0), (140, 325), 3)
    pygame.draw.circle(surface, (200, 150, 120), (130, 335), 4)
    
    pygame.draw.ellipse(surface, (50, 50, 50), (90, 310, 80, 20))
    pygame.draw.ellipse(surface, (20, 20, 20), (90, 310, 80, 20), 3)
    pygame.draw.rect(surface, (50, 50, 50), (110, 295, 40, 20))
    pygame.draw.rect(surface, (20, 20, 20), (110, 295, 40, 20), 3)
    pygame.draw.rect(surface, (200, 50, 50), (110, 308, 40, 5))
    
    pygame.draw.line(surface, (100, 50, 0), (140, 360), (400, 250), 6)
    pygame.draw.circle(surface, (150, 150, 150), (150, 365), 8)
    pygame.draw.circle(surface, (80, 80, 80), (150, 365), 8, 2)

# --- VOSK ---
try:
    model = Model(MODEL_PATH)
except Exception as e:
    print("Ошибка загрузки модели Vosk:", e)
    model = None

audio_q = queue.Queue()
result_q = queue.Queue()
listening = False

def listen_thread():
    if not model: return
    rec = KaldiRecognizer(model, 16000)
    rec.SetWords(True)
    def callback(indata, frames, time, status): audio_q.put(bytes(indata))
    with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype="int16", channels=1, callback=callback):
        for _ in range(120):
            data = audio_q.get()
            if rec.AcceptWaveform(data):
                res = json.loads(rec.Result())
                result_q.put(res.get("text", "").lower().strip())
                return
        res = json.loads(rec.FinalResult())
        result_q.put(res.get("text", "").lower().strip())

def start_listening():
    global listening
    if not listening and model:
        threading.Thread(target=listen_thread, daemon=True).start()
        listening = True

difficulty = 0
current_fish = Fish(difficulty)

state = "waiting"
message = ""
state_timer = 0
total_time = 0

fish_x = 550
fish_y = 350
start_x, start_y = 550, 350
target_x, target_y = 65, 360 
flight_progress = 0.0

fish_hitbox = pygame.Rect(0,0,0,0)
score = 0
caught_fish_list = []

fisherman_speech = ""
fisherman_speech_timer = 0

cat_eating_timer = 0

menu_open = False
menu_input_text = ""
menu_level = 0
menu_scroll = 0
btn_menu_rect = pygame.Rect(WIDTH - 100, 10, 90, 30)
btn_close_rect = pygame.Rect(600, 110, 40, 30)

def add_custom_word(word, level_idx):
    global custom_words, current_fish
    word = word.strip().lower()
    if not word: return
    level_key = ["easy", "medium", "hard"][level_idx]
    if word not in custom_words[level_key]:
        custom_words[level_key].append(word)
        save_custom_words(custom_words)
        generate_tts_async(word)
        if current_fish.word is None and difficulty == level_idx:
            current_fish = Fish(difficulty)

def remove_custom_word(word, level_idx):
    global custom_words
    level_key = ["easy", "medium", "hard"][level_idx]
    if word in custom_words[level_key]:
        custom_words[level_key].remove(word)
        save_custom_words(custom_words)

running = True
while running:
    try:
        dt = clock.tick(60) / 1000.0
        total_time += dt
        
        if cat_eating_timer > 0:
            cat_eating_timer -= dt
            
        mouse_pos = pygame.mouse.get_pos()
        is_hover = (not menu_open) and (state in ("waiting", "listening")) and fish_hitbox.collidepoint(mouse_pos)
        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if is_hover else pygame.SYSTEM_CURSOR_ARROW)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            if menu_open:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        menu_open = False
                    elif event.key == pygame.K_RETURN:
                        add_custom_word(menu_input_text, menu_level)
                        menu_input_text = ""
                        menu_scroll = 0
                    elif event.key == pygame.K_BACKSPACE:
                        menu_input_text = menu_input_text[:-1]
                    else:
                        if event.unicode.isalpha():
                            menu_input_text += event.unicode
                
                if event.type == pygame.MOUSEWHEEL:
                    level_key = ["easy", "medium", "hard"][menu_level]
                    max_scroll = max(0, len(custom_words[level_key]) - 5)
                    menu_scroll = max(0, min(menu_scroll - event.y, max_scroll))
                    
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if btn_close_rect.collidepoint(event.pos):
                        menu_open = False
                        
                    if pygame.Rect(250, 150, 100, 40).collidepoint(event.pos): menu_level = 0; menu_scroll = 0
                    if pygame.Rect(350, 150, 100, 40).collidepoint(event.pos): menu_level = 1; menu_scroll = 0
                    if pygame.Rect(450, 150, 100, 40).collidepoint(event.pos): menu_level = 2; menu_scroll = 0
                    
                    level_key = ["easy", "medium", "hard"][menu_level]
                    words_list = custom_words.get(level_key, [])
                    
                    for i in range(5):
                        idx = i + menu_scroll
                        if idx >= len(words_list): break
                        del_rect = pygame.Rect(560, 330 + i*30, 30, 20)
                        if del_rect.collidepoint(event.pos):
                            remove_custom_word(words_list[idx], menu_level)
                            break
                    
            else:
                slider_music.handle_event(event)
                slider_fx.handle_event(event)
                vol_music = slider_music.value
                vol_fx = slider_fx.value
                update_volumes()

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if btn_menu_rect.collidepoint(event.pos):
                        menu_open = True
                        continue
                        
                    if state in ("waiting", "listening") and fish_hitbox.collidepoint(event.pos):
                        if vol_fx > 0 and current_fish.word:
                            speak_text(current_fish.word)
                    
                    if pygame.Rect(20, 50, 250, 40).collidepoint(event.pos):
                        difficulty = (difficulty + 1) % 3
                        current_fish = Fish(difficulty)
                        state = "waiting"
                        message = ""
                        fisherman_speech = ""

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_TAB:
                        menu_open = True
                    elif event.key == pygame.K_SPACE and state == "waiting" and current_fish.word:
                        state = "listening"
                        message = "Слушаю..."
                        start_listening()

        if not menu_open:
            if state == "listening" and not result_q.empty():
                said = result_q.get()
                listening = False
                if said == current_fish.word:
                    state = "flying"
                    flight_progress = 0.0
                    message = f"Поймал! ({said})"
                    if sound_catch and vol_fx > 0: sound_catch.play()
                else:
                    state = "confused"
                    message = f"«{said}»? Попробуй ещё!"
                    state_timer = 2.0

            if state == "confused":
                state_timer -= dt
                if state_timer <= 0:
                    state = "waiting"
                    message = ""
                    fish_x = 550
                    fish_y = 350
            
            elif state == "flying":
                if flight_progress == 0.0 and sound_splash and vol_fx > 0:
                    sound_splash.play()
                flight_progress += dt * 0.8
                if flight_progress >= 1.0:
                    flight_progress = 1.0
                    state = "caught"
                    state_timer = 4.5 # Увеличили таймер, так как теперь ждем два звука
                    score += 1
                    
                    cat_eating_timer = 1.5
                    eat_duration = 1.5
                    if sound_cat_eat and vol_fx > 0: 
                        sound_cat_eat.play()
                        eat_duration = sound_cat_eat.get_length() # Если звук длиннее 1.5 сек, ждем его
                        cat_eating_timer = eat_duration
                    
                    fisherman_speech = current_fish.get_comment()
                    fisherman_speech_timer = 4.5
                    if vol_fx > 0 and fisherman_speech:
                        speak_commentary_after_eat(fisherman_speech, eat_duration)
                        
                else:
                    fish_x = start_x + (target_x - start_x) * flight_progress
                    fish_y = start_y + (target_y - start_y) * flight_progress - math.sin(flight_progress * math.pi) * 200
                    
            elif state == "caught":
                state_timer -= dt
                if state_timer <= 0:
                    current_fish = Fish(difficulty)
                    state = "waiting"
                    message = ""
                    fish_x = 550
                    fish_y = 350

            if state == "waiting" or state == "listening":
                fish_x = 550 + math.sin(total_time * 2) * 30
                fish_y = 350

            if fisherman_speech_timer > 0:
                fisherman_speech_timer -= dt
            else:
                fisherman_speech = ""

        draw_background(screen, total_time)
        for bf in bg_fishes:
            bf.update(dt, total_time)
            bf.draw(screen)

        if state == "flying" or state == "caught":
            pygame.draw.line(screen, (255, 255, 255), (400, 250), (fish_x, fish_y), 2)
        elif state != "caught":
            pygame.draw.aaline(screen, (255, 255, 255), (400, 250), (fish_x-40, fish_y-20))
            pygame.draw.aaline(screen, (255, 255, 255), (fish_x-40, fish_y-20), (fish_x, fish_y))

        draw_fisherman_and_basket(screen, caught_fish_list, cat_eating_timer)
        
        if current_fish.word is None and not menu_open:
            msg = "Слова закончились! Добавьте новое в меню."
            draw_text_outlined(screen, msg, font_med, WIDTH//2, 200, (255, 255, 0), (0,0,0), 2, center=True)
            fish_hitbox = pygame.Rect(0,0,0,0)
        elif state != "caught" and not menu_open:
            fish_hitbox = current_fish.draw(screen, fish_x, fish_y, state, total_time)
        else:
            fish_hitbox = pygame.Rect(0,0,0,0)

        if fisherman_speech and not menu_open:
            words = fisherman_speech.split()
            line1 = ""
            line2 = ""
            for w in words:
                if font_small.size(line1 + w)[0] < 250: line1 += w + " "
                else: line2 += w + " "
            bubble_w = max(font_small.size(line1)[0], font_small.size(line2)[0]) + 30
            bubble_h = 70 if line2 else 40
            bubble_x = 130 - bubble_w // 2
            bubble_y = 280 - bubble_h
            
            pygame.draw.rect(screen, (255, 255, 255), (bubble_x, bubble_y, bubble_w, bubble_h), border_radius=15)
            pygame.draw.rect(screen, (0, 0, 0), (bubble_x, bubble_y, bubble_w, bubble_h), width=3, border_radius=15)
            tail_pts = [(130 - 10, bubble_y + bubble_h), (130 + 10, bubble_y + bubble_h), (130, bubble_y + bubble_h + 15)]
            pygame.draw.polygon(screen, (255, 255, 255), tail_pts)
            pygame.draw.polygon(screen, (0, 0, 0), tail_pts, 3)
            if line1: draw_text_outlined(screen, line1.strip(), font_small, bubble_x + 15, bubble_y + 10, (0, 0, 0), (255, 255, 255), 1)
            if line2: draw_text_outlined(screen, line2.strip(), font_small, bubble_x + 15, bubble_y + 35, (0, 0, 0), (255, 255, 255), 1)

        if message and not menu_open:
            draw_text_outlined(screen, message, font_med, 50, 90, (255, 255, 0), (0,0,0), 2)

        if not menu_open:
            draw_text_outlined(screen, "Пробел — слушать", font_med, 50, 550, (200, 200, 200), (0,0,0), 2)
            
            draw_text_outlined(screen, f"Улов: {score}", font_med, 20, 10, (255, 255, 255), (0,0,0), 2)
            
            diff_names = ["Легко", "Средне", "Сложно"]
            diff_colors = [(100, 200, 100), (255, 200, 100), (255, 100, 100)]
            draw_text_outlined(screen, f"Сложность: {diff_names[difficulty]}", font_med, 20, 45, diff_colors[difficulty], (0,0,0), 2)
            
            draw_text_outlined(screen, "Музыка", font_ui, 160, 5, (255, 255, 255), (0,0,0), 1)
            draw_text_outlined(screen, "Звуки", font_ui, 370, 5, (255, 255, 255), (0,0,0), 1)
            slider_music.draw(screen)
            slider_fx.draw(screen)

        pygame.draw.rect(screen, (50, 150, 250), btn_menu_rect, border_radius=5)
        pygame.draw.rect(screen, (0,0,0), btn_menu_rect, width=2, border_radius=5)
        draw_text_outlined(screen, "МЕНЮ", font_small, btn_menu_rect.centerx, btn_menu_rect.centery, (255, 255, 255), (0,0,0), 1, center=True)

        if menu_open:
            s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            s.fill((0, 0, 0, 180))
            screen.blit(s, (0, 0))
            
            menu_rect = pygame.Rect(150, 100, 500, 400)
            pygame.draw.rect(screen, (240, 240, 240), menu_rect, border_radius=15)
            pygame.draw.rect(screen, (0, 0, 0), menu_rect, width=3, border_radius=15)
            
            draw_text_outlined(screen, "СПИСОК СЛОВ", font_menu, WIDTH//2, 130, (0, 0, 0), (255, 255, 255), 1, center=True)
            
            pygame.draw.rect(screen, (220, 50, 50), btn_close_rect, border_radius=5)
            pygame.draw.rect(screen, (0,0,0), btn_close_rect, width=2, border_radius=5)
            draw_text_outlined(screen, "X", font_menu, btn_close_rect.centerx, btn_close_rect.centery, (255,255,255), (0,0,0), 1, center=True)
            
            tabs = ["Легкие", "Средние", "Сложные"]
            for i, tab in enumerate(tabs):
                tab_rect = pygame.Rect(250 + i*100, 150, 100, 40)
                color = (100, 200, 255) if i == menu_level else (200, 200, 200)
                pygame.draw.rect(screen, color, tab_rect, border_radius=5)
                pygame.draw.rect(screen, (0,0,0), tab_rect, width=2, border_radius=5)
                draw_text_outlined(screen, tab, font_small, tab_rect.centerx, tab_rect.centery, (0,0,0), (255,255,255), 1, center=True)
                
            input_rect = pygame.Rect(200, 220, 400, 50)
            pygame.draw.rect(screen, (255, 255, 255), input_rect)
            pygame.draw.rect(screen, (0, 0, 0), input_rect, width=3)
            draw_text_outlined(screen, menu_input_text + "_", font_menu, 210, 235, (0, 0, 0), (255,255,255), 1)
            
            level_key = ["easy", "medium", "hard"][menu_level]
            words_list = custom_words.get(level_key, [])
            
            pygame.draw.rect(screen, (200, 200, 200), (200, 290, 400, 30))
            draw_text_outlined(screen, "Слово (клик для удаления)", font_small, 210, 295, (0,0,0), (255,255,255), 1)
            
            for i in range(5):
                idx = i + menu_scroll
                if idx >= len(words_list): break
                w = words_list[idx]
                row_rect = pygame.Rect(200, 325 + i*30, 400, 30)
                
                if i % 2 == 0:
                    pygame.draw.rect(screen, (230, 230, 230), row_rect)
                
                draw_text_outlined(screen, w, font_small, 210, 330 + i*30, (0, 100, 0), (255,255,255), 1)
                
                del_rect = pygame.Rect(560, 330 + i*30, 30, 20)
                pygame.draw.rect(screen, (220, 50, 50), del_rect, border_radius=3)
                draw_text_outlined(screen, "X", font_ui, del_rect.centerx, del_rect.centery, (255,255,255), (0,0,0), 1, center=True)

            if len(words_list) > 5:
                draw_text_outlined(screen, "Колесико мыши — прокрутка", font_small, 200, 470, (100, 100, 100), (255,255,255), 1)
                
            draw_text_outlined(screen, "Enter — добавить, Esc — закрыть", font_small, 200, 490, (100, 100, 100), (255,255,255), 1)

        pygame.display.flip()

    except Exception as e:
        print(f"Ошибка в игровом цикле: {e}")
        traceback.print_exc()
        pygame.time.delay(100)

pygame.quit()
