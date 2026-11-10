import re

with open("game_pygame.py", "r", encoding="utf-8") as f:
    code = f.read()

# Ищем блок с BASE_DIR и заменяем на правильный
pattern = re.compile(r"import sys\nimport os\n\nif getattr\(sys, 'frozen', False\):.*?os\.makedirs\(CACHE_DIR, exist_ok=True\)", re.DOTALL)

new_block = '''import sys
import os

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    EXE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXE_DIR = BASE_DIR

MODEL_PATH = os.path.join(BASE_DIR, "models", "vosk-model-small-ru-0.22")
CACHE_DIR = os.path.join(EXE_DIR, "assets", "tts_cache")
CUSTOM_WORDS_FILE = os.path.join(EXE_DIR, "custom_words.json")
os.makedirs(CACHE_DIR, exist_ok=True)'''

if pattern.search(code):
    code = pattern.sub(new_block, code)
    with open("game_pygame.py", "w", encoding="utf-8") as f:
        f.write(code)
    print("Успех! Пути исправлены. Теперь ресурсы ищутся в _MEIPASS, а кэш рядом с .exe.")
else:
    print("Ошибка: не удалось найти блок с BASE_DIR. Возможно, он уже изменен.")
