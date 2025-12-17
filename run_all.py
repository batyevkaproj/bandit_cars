import subprocess
import time
import sys

# Список скриптів для запуску
scripts = [
    "olx_monitor.py",
    "olx_enricher.py",
    "app.py"
    # "telegram_notifier.py" # Розкоментуйте, якщо додали телеграм
]

processes = []

print("🚀 Запуск системи OLX Monitor...")

try:
    for script in scripts:
        print(f"   ▶ Запускаю {script}...")
        # Запускаємо кожен скрипт як окремий процес
        p = subprocess.Popen([sys.executable, script])
        processes.append(p)

    print("\n✅ Всі системи працюють! Натисніть Ctrl+C для зупинки.")
    
    # Тримаємо скрипт активним
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\n🛑 Зупинка всіх процесів...")
    for p in processes:
        p.terminate()