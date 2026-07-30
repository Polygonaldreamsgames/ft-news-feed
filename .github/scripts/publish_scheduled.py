import json
import os
import datetime
import subprocess
import sys
import traceback

# ✅ АВТОМАТИЧЕСКОЕ ОПРЕДЕЛЕНИЕ ПУТИ
# Скрипт всегда будет искать файлы относительно САМОГО СЕБЯ
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR) # Поднимаемся на уровень выше (.github -> корень)

JOBS_FILE = os.path.join(REPO_ROOT, "scheduled_jobs.json")
NEWS_FILE = os.path.join(REPO_ROOT, "news.txt")

def run_git(args):
    """Выполняет git команду, явно указывая рабочую директорию"""
    try:
        result = subprocess.run(
            ["git"] + args, 
            cwd=REPO_ROOT, # ✅ Явно указываем, где выполнять git
            capture_output=True, 
            text=True,
            timeout=30
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def main():
    print(f"🚀 Запуск авто-публикации...")
    print(f"📂 Корень репозитория: {REPO_ROOT}")
    print(f"📄 Путь к jobs: {JOBS_FILE}")
    print(f"📄 Путь к news: {NEWS_FILE}")
    
    # Проверяем существование файлов
    if not os.path.exists(JOBS_FILE):
        print(f"⚠️ Файл {JOBS_FILE} не найден. Создаем пустой.")
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return

    if not os.path.exists(NEWS_FILE):
        print(f"⚠️ Файл {NEWS_FILE} не найден. Создаем пустой.")
        with open(NEWS_FILE, "w", encoding="utf-8") as f:
            f.write("")

    # Загружаем задачи
    try:
        with open(JOBS_FILE, "r", encoding="utf-8") as f:
            jobs = json.load(f)
        print(f" Загружено {len(jobs)} задач")
    except Exception as e:
        print(f"❌ Ошибка загрузки JSON: {e}")
        traceback.print_exc()
        return

    now_utc = datetime.datetime.utcnow()
    published_any = False
    jobs_to_keep = {}

    for job_id, job_data in list(jobs.items()): # list() чтобы можно было удалять во время цикла
        try:
            run_date = datetime.datetime.strptime(job_data['run_date'], "%d.%m.%Y %H:%M")
            
            if run_date <= now_utc:
                print(f"✅ ПУБЛИКУЮ: {job_data['data']['title_ru']}")
                
                data = job_data['data']
                new_block = (
                    f"[NEWS]\ndate={data['date']}\ntype={data['type']}\n"
                    f"important={data['important']}\n"
                    f"title_ru={data['title_ru']}\ntitle_en={data['title_en']}\n"
                    f"desc_ru={data['desc_ru']}\ndesc_en={data['desc_en']}\n\n"
                )
                
                # Читаем старый контент
                old_content = ""
                if os.path.exists(NEWS_FILE):
                    with open(NEWS_FILE, "r", encoding="utf-8") as f:
                        old_content = f.read()
                        
                # Пишем новый + старый
                with open(NEWS_FILE, "w", encoding="utf-8") as f:
                    f.write(new_block + old_content)
                
                published_any = True
            else:
                jobs_to_keep[job_id] = job_data
                
        except Exception as e:
            print(f"⚠️ Ошибка задачи {job_id}: {e}")
            jobs_to_keep[job_id] = job_data

    # Коммит и пуш
    if published_any:
        print("\n📤 Отправка на GitHub...")
        
        success, out, err = run_git(["add", NEWS_FILE, JOBS_FILE])
        if not success:
            print(f" Git add error: {err}"); return
            
        success, out, err = run_git(["commit", "-m", "Auto-publish: Scheduled news"])
        if not success:
            print(f"❌ Git commit error: {err}"); return
            
        token = os.environ.get('GH_TOKEN')
        repo = os.environ.get('GITHUB_REPOSITORY', '')
        
        if token and repo:
            remote_url = f"https://x-access-token:{token}@github.com/{repo}.git"
            success, out, err = run_git(["remote", "set-url", "origin", remote_url])
            if success:
                success, out, err = run_git(["push", "origin", "main"])
                if success:
                    print("✅ Успешно опубликовано!")
                else:
                    print(f"❌ Push error: {err}")
            else:
                print(f"❌ Remote set-url error: {err}")
        else:
            print("️ Нет токена или имени репо, пропускаю пуш")
    else:
        print("\n⏸️ Нет новостей для публикации")
    
    # Сохраняем оставшиеся задачи
    with open(JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs_to_keep, f, ensure_ascii=False, indent=2)
        
    print("\n🎉 Скрипт завершен!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n💥 CRITICAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)