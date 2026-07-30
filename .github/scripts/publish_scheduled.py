import json
import os
import datetime
import subprocess
import sys
import traceback

JOBS_FILE = "scheduled_jobs.json"
NEWS_FILE = "news.txt"

def run_git(args):
    """Выполняет git команду на сервере GitHub"""
    try:
        result = subprocess.run(
            ["git"] + args, 
            capture_output=True, 
            text=True,
            timeout=30
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def main():
    print("🚀 Запуск авто-публикации новостей...")
    print(f"Текущее время UTC: {datetime.datetime.utcnow()}")
    
    # Проверяем существование файла задач
    if not os.path.exists(JOBS_FILE):
        print(f"️ Файл {JOBS_FILE} не найден. Создаем пустой.")
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return

    # Загружаем задачи
    try:
        with open(JOBS_FILE, "r", encoding="utf-8") as f:
            jobs = json.load(f)
        print(f"📋 Загружено {len(jobs)} запланированных задач")
    except Exception as e:
        print(f"❌ Ошибка загрузки {JOBS_FILE}: {e}")
        traceback.print_exc()
        return

    now_utc = datetime.datetime.utcnow()
    published_any = False
    jobs_to_keep = {}

    for job_id, job_data in jobs.items():
        try:
            print(f"\n🔍 Проверка задачи: {job_id}")
            print(f"   Запланировано на: {job_data['run_date']}")
            
            # Парсим время
            run_date = datetime.datetime.strptime(job_data['run_date'], "%d.%m.%Y %H:%M")
            print(f"   Текущее UTC: {now_utc}")
            print(f"   Пора публиковать: {run_date <= now_utc}")
            
            if run_date <= now_utc:
                print(f"✅ ПУБЛИКУЮ: {job_data['data']['title_ru']}")
                
                data = job_data['data']
                new_block = (
                    f"[NEWS]\ndate={data['date']}\ntype={data['type']}\n"
                    f"important={data['important']}\n"
                    f"title_ru={data['title_ru']}\ntitle_en={data['title_en']}\n"
                    f"desc_ru={data['desc_ru']}\ndesc_en={data['desc_en']}\n\n"
                )
                
                # Добавляем новость в начало файла
                old_content = ""
                if os.path.exists(NEWS_FILE):
                    with open(NEWS_FILE, "r", encoding="utf-8") as f:
                        old_content = f.read()
                    print(f"   Прочитано {len(old_content)} символов из {NEWS_FILE}")
                    
                with open(NEWS_FILE, "w", encoding="utf-8") as f:
                    f.write(new_block + old_content)
                print(f"   Новость записана в {NEWS_FILE}")
                
                published_any = True
            else:
                # Задача еще не наступила — сохраняем её
                jobs_to_keep[job_id] = job_data
                print(f"⏳ Задача еще не наступила, сохраняем")
                
        except Exception as e:
            print(f"⚠️ Ошибка обработки задачи {job_id}: {e}")
            traceback.print_exc()
            jobs_to_keep[job_id] = job_data # Не теряем задачу при ошибке

    # Если опубликовали хотя бы одну новость — коммитим и пушим
    if published_any:
        print("\n Отправка изменений на GitHub...")
        
        success, out, err = run_git(["add", NEWS_FILE, JOBS_FILE])
        if not success:
            print(f"❌ Ошибка git add: {err}")
            return
            
        success, out, err = run_git(["commit", "-m", "Auto-publish: Scheduled news"])
        if not success:
            print(f"❌ Ошибка git commit: {err}")
            return
            
        # Настраиваем remote с токеном для пуша
        token = os.environ.get('GH_TOKEN')
        repo = os.environ.get('GITHUB_REPOSITORY', '')
        if not token or not repo:
            print("❌ Не найдены переменные окружения GH_TOKEN или GITHUB_REPOSITORY")
            return
            
        remote_url = f"https://x-access-token:{token}@github.com/{repo}.git"
        
        success, out, err = run_git(["remote", "set-url", "origin", remote_url])
        if not success:
            print(f"❌ Ошибка настройки remote: {err}")
            return
            
        success, out, err = run_git(["push", "origin", "main"])
        if success:
            print("✅ Успешно опубликовано и отправлено на GitHub!")
        else:
            print(f"❌ Ошибка пуша: {err}")
    else:
        print("\n⏸️ Нет новостей для публикации")
    
    # Обновляем файл задач (удаляем выполненные)
    print(f"\n💾 Сохранение оставшихся задач ({len(jobs_to_keep)} шт.)")
    with open(JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs_to_keep, f, ensure_ascii=False, indent=2)
        
    print("\n🎉 Скрипт завершен успешно!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
        traceback.print_exc()
        sys.exit(1)
