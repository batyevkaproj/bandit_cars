import subprocess
import time
import sys
from pathlib import Path

# =============================
# ⚙️ НАЛАШТУВАННЯ
# =============================

# Визначаємо шлях до Python у віртуальному середовищі
# Це гарантує, що скрипти побачать встановлені бібліотеки (requests, flask)
BASE_DIR = Path(__file__).parent.resolve()
VENV_PYTHON = BASE_DIR / "venv" / "Scripts" / "python.exe"

# Якщо раптом venv не знайдено, спробуємо системний (але це запасний варіант)
if not VENV_PYTHON.exists():
    print(f"⚠️ Увага: Python у venv не знайдено за адресою {VENV_PYTHON}")
    print("Спроба запустити через системний python...")
    VENV_PYTHON = sys.executable
else:
    print(f"✅ Використовую Python з віртуального середовища: {VENV_PYTHON}")

# Список скриптів для запуску
scripts = [
    "olx_monitor.py",   # Шукає нові авто
    "olx_enricher.py",  # Перевіряє та додає деталі
    "app.py"            # Запускає сайт
]

processes = []

print("🚀 Запуск системи OLX Monitor...")

try:
    for script in scripts:
        script_path = BASE_DIR / script
        print(f"   ▶ Запускаю {script}...")
        
        # Запускаємо процес, явно вказуючи шлях до правильного Python
        p = subprocess.Popen([str(VENV_PYTHON), str(script_path)])
        processes.append(p)

    print("\n✅ Всі системи працюють! Натисніть Ctrl+C для зупинки.")
    
    # Тримаємо скрипт активним
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\n🛑 Зупинка всіх процесів...")
    for p in processes:
        p.terminate()