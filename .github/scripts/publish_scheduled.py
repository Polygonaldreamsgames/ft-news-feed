import json
import os
import datetime
import subprocess

JOBS_FILE = "scheduled_jobs.json"
NEWS_FILE = "news.txt"

def run_git(args):
    """Выполняет git команду на сервере GitHub"""
    result = subprocess.run(["git"] + args, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr

def main():
    if not os.path.exists(JOBS_FILE):
        print("Нет запланированных задач.")
        return

    with open(JOBS_FILE, "r", encoding="utf-8") as f:
        jobs = json.load(f)

    # ⚠️ ВАЖНО: Сервер GitHub ВСЕГДА работает по UTC!
    now_utc = datetime.datetime.utcnow()
    published_any = False
    jobs_to_keep = {}

    for job_id, job_data in jobs.items():
        try:
            # Время в файле УЖЕ должно быть в UTC (конвертация делается в Python-скрипте на ПК)
            run_date = datetime.datetime.strptime(job_data['run_date'], "%d.%m.%Y %H:%M")
            
            if run_date <= now_utc:
                print(f" ПУБЛИКУЮ: {job_data['data']['title_ru']}")
                
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
                        
                with open(NEWS_FILE, "w", encoding="utf-8") as f:
                    f.write(new_block + old_content)
                
                published_any = True
            else:
                # Задача еще не наступила — сохраняем её
                jobs_to_keep[job_id] = job_data
                
        except Exception as e:
            print(f"⚠️ Ошибка обработки задачи {job_id}: {e}")
            jobs_to_keep[job_id] = job_data # Не теряем задачу при ошибке

    # Если опубликовали хотя бы одну новость — коммитим и пушим
    if published_any:
        success, out, err = run_git(["add", NEWS_FILE, JOBS_FILE])
        if success:
            success, out, err = run_git(["commit", "-m", "Auto-publish: Scheduled news"])
            if success:
                # Настраиваем remote с токеном для пуша
                token = os.environ.get('GH_TOKEN')
                repo = os.environ['GITHUB_REPOSITORY']
                remote_url = f"https://x-access-token:{token}@github.com/{repo}.git"
                
                success, out, err = run_git(["remote", "set-url", "origin", remote_url])
                if success:
                    success, out, err = run_git(["push", "origin", "main"])
                    if success:
                        print("✅ Успешно опубликовано и отправлено на GitHub!")
                    else:
                        print(f"❌ Ошибка пуша: {err}")
                else:
                    print(f"❌ Ошибка настройки remote: {err}")
            else:
                print(f"❌ Ошибка коммита: {err}")
        else:
            print(f" Ошибка add: {err}")
    
    # Обновляем файл задач (удаляем выполненные)
    with open(JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs_to_keep, f, ensure_ascii=False, indent=2)
        
    if not published_any:
        print("Пока нет новостей для публикации.")

if __name__ == "__main__":
    main()