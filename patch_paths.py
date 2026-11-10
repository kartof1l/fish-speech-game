import re

with open("game_pygame.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Добавляем BASE_DIR и абсолютные пути в начало (после импортов)
base_block = '''
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
'''

# Удаляем старые определения, если есть
code = re.sub(r'MODEL_PATH = ".*?"', '', code)
code = re.sub(r'CACHE_DIR = ".*?"', '', code)
code = re.sub(r'CUSTOM_WORDS_FILE = ".*?"', '', code)
code = re.sub(r'os\.makedirs\(CACHE_DIR, exist_ok=True\)', '', code)

# Вставляем новый блок после последнего импорта
lines = code.split('\n')
insert_idx = 0
for i, line in enumerate(lines):
    if line.startswith('import ') or line.startswith('from '):
        insert_idx = i + 1
lines.insert(insert_idx, base_block)
code = '\n'.join(lines)

# 2. Заменяем пути к звукам на os.path.join(BASE_DIR, ...)
code = code.replace(
    'os.path.exists("assets/sounds/catch.wav")',
    'os.path.exists(os.path.join(BASE_DIR, "assets", "sounds", "catch.wav"))'
)
code = code.replace(
    'pygame.mixer.Sound("assets/sounds/catch.wav")',
    'pygame.mixer.Sound(os.path.join(BASE_DIR, "assets", "sounds", "catch.wav"))'
)
code = code.replace(
    'os.path.exists("assets/sounds/splash.wav")',
    'os.path.exists(os.path.join(BASE_DIR, "assets", "sounds", "splash.wav"))'
)
code = code.replace(
    'pygame.mixer.Sound("assets/sounds/splash.wav")',
    'pygame.mixer.Sound(os.path.join(BASE_DIR, "assets", "sounds", "splash.wav"))'
)
code = code.replace(
    'os.path.exists("assets/sounds/cat_eat.wav")',
    'os.path.exists(os.path.join(BASE_DIR, "assets", "sounds", "cat_eat.wav"))'
)
code = code.replace(
    'pygame.mixer.Sound("assets/sounds/cat_eat.wav")',
    'pygame.mixer.Sound(os.path.join(BASE_DIR, "assets", "sounds", "cat_eat.wav"))'
)
code = code.replace(
    'os.path.exists("assets/sounds/music.mp3")',
    'os.path.exists(os.path.join(BASE_DIR, "assets", "sounds", "music.mp3"))'
)
code = code.replace(
    'pygame.mixer.music.load("assets/sounds/music.mp3")',
    'pygame.mixer.music.load(os.path.join(BASE_DIR, "assets", "sounds", "music.mp3"))'
)

with open("game_pygame.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Готово! Пути заменены на абсолютные (через BASE_DIR).")
