import re

with open("game_pygame.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Добавляем BASE_DIR в начало (после импортов), НЕ трогая существующие MODEL_PATH и т.д.
if "BASE_DIR" not in code:
    base_block = '''
import sys
import os

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
'''
    lines = code.split('\n')
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('import ') or line.startswith('from '):
            insert_idx = i + 1
    lines.insert(insert_idx, base_block)
    code = '\n'.join(lines)

# 2. Меняем MODEL_PATH, CACHE_DIR, CUSTOM_WORDS_FILE на абсолютные (аккуратно, только присваивания)
code = re.sub(
    r'MODEL_PATH\s*=\s*["\'].*?["\']',
    'MODEL_PATH = os.path.join(BASE_DIR, "models", "vosk-model-small-ru-0.22")',
    code
)
code = re.sub(
    r'CACHE_DIR\s*=\s*["\'].*?["\']',
    'CACHE_DIR = os.path.join(BASE_DIR, "assets", "tts_cache")',
    code
)
code = re.sub(
    r'CUSTOM_WORDS_FILE\s*=\s*["\'].*?["\']',
    'CUSTOM_WORDS_FILE = os.path.join(BASE_DIR, "custom_words.json")',
    code
)

# 3. Заменяем пути к звукам
replacements = [
    ('"assets/sounds/catch.wav"', 'os.path.join(BASE_DIR, "assets", "sounds", "catch.wav")'),
    ('"assets/sounds/splash.wav"', 'os.path.join(BASE_DIR, "assets", "sounds", "splash.wav")'),
    ('"assets/sounds/cat_eat.wav"', 'os.path.join(BASE_DIR, "assets", "sounds", "cat_eat.wav")'),
    ('"assets/sounds/music.mp3"', 'os.path.join(BASE_DIR, "assets", "sounds", "music.mp3")'),
]
for old, new in replacements:
    code = code.replace(old, new)

with open("game_pygame.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Патч путей применён. TTS-блок не тронут.")
