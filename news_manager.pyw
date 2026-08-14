import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import os
import sys
import git
import subprocess
import threading
import winreg
import json

try:
    from PIL import Image, ImageDraw
    import pystray
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    input("Нажми Enter для выхода...")
    sys.exit(1)

# --- НАСТРОЙКИ ---
REPO_PATH = os.path.dirname(os.path.abspath(__file__))
NEWS_FILE = "news.txt"
SETTINGS_FILE = "settings.ini"
DRAFT_FILE = "draft.txt"
JOBS_FILE = "scheduled_jobs.json"

class FTNewsManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("FT News Manager Pro")
        
        self.root.geometry("600x780")
        self.root.minsize(550, 650)
        self.root.resizable(True, True)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - 600) // 2
        y = max(20, (screen_h - 780) // 2)
        self.root.geometry(f"+{x}+{y}")
        
        self.colors = {
            "bg": "#2b2b2b", "frame_bg": "#333333", "entry_bg": "#1e1e1e",
            "text_fg": "#d4d4d4", "accent": "#5c5c5c", "btn_hover": "#4a4a4a",
            "danger": "#8b3a3a", "success": "#4a6b3a"
        }
        self.root.configure(bg=self.colors["bg"])
        
        self.scale_var = tk.DoubleVar(value=1.0)
        self.settings = self.load_settings()
        try: self.scale_var.set(float(self.settings.get("ui_scale", "1.0")))
        except: pass
        
        try: self.repo = git.Repo(REPO_PATH)
        except Exception as e:
            messagebox.showerror("Git Error", f"Репозиторий не найден: {e}")
            return

        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        
        self.setup_ui()
        self.setup_hotkeys()
        self.restore_draft()
        self.restore_scheduled_jobs()
        self.setup_tray_icon()
        self.check_auto_start()
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.root.mainloop()

    def setup_clipboard_hotkeys(self, widget):
        widget.bind("<Control-c>", lambda e: self._copy_text(e, widget))
        widget.bind("<Control-v>", lambda e: self._paste_text(e, widget))
        widget.bind("<Control-x>", lambda e: self._cut_text(e, widget))
        widget.bind("<Button-3>", lambda e: self._show_context_menu(e, widget))

    def _copy_text(self, event, widget):
        try:
            if isinstance(widget, tk.Text):
                text = widget.get("sel.first", "sel.last")
            else:
                text = widget.selection_get() or widget.get()
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except tk.TclError:
            pass
        return "break"

    def _paste_text(self, event, widget):
        try:
            text = self.root.clipboard_get()
            if isinstance(widget, tk.Text):
                widget.insert("insert", text)
            else:
                current_text = widget.get()
                cursor_pos = widget.index(tk.INSERT)
                new_text = current_text[:cursor_pos] + text + current_text[cursor_pos:]
                widget.delete(0, tk.END)
                widget.insert(0, new_text)
                widget.icursor(cursor_pos + len(text))
        except tk.TclError:
            pass
        return "break"

    def _cut_text(self, event, widget):
        try:
            if isinstance(widget, tk.Text):
                text = widget.get("sel.first", "sel.last")
                widget.delete("sel.first", "sel.last")
            else:
                text = widget.selection_get()
                if text:
                    widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except tk.TclError:
            pass
        return "break"

    def _show_context_menu(self, event, widget):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Копировать", command=lambda: self._copy_text(None, widget))
        menu.add_command(label="Вставить", command=lambda: self._paste_text(None, widget))
        menu.add_command(label="Вырезать", command=lambda: self._cut_text(None, widget))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        
        self.tab_create = tk.Frame(self.notebook, bg=self.colors["bg"])
        self.notebook.add(self.tab_create, text=" ️ Создать ")
        self.build_create_tab()
        
        self.tab_list = tk.Frame(self.notebook, bg=self.colors["bg"])
        self.notebook.add(self.tab_list, text=" 📋 Все новости ")
        self.build_list_tab()
        
        self.tab_settings = tk.Frame(self.notebook, bg=self.colors["bg"])
        self.notebook.add(self.tab_settings, text=" ⚙️ Настройки ")
        self.build_settings_tab()
        
        scale_frame = tk.Frame(self.root, bg=self.colors["bg"])
        scale_frame.pack(fill="x", side="bottom", padx=15, pady=8)
        tk.Label(scale_frame, text="Масштаб:", bg=self.colors["bg"], fg="#808080", font=("Segoe UI", 9)).pack(side="left")
        tk.Scale(scale_frame, from_=0.8, to=1.2, resolution=0.1, orient="horizontal", 
                 variable=self.scale_var, bg=self.colors["bg"], fg=self.colors["text_fg"],
                 highlightthickness=0, showvalue=False, command=lambda v: self.save_scale(v)
        ).pack(side="left", fill="x", expand=True, padx=10)

    def build_create_tab(self):
        container = tk.Frame(self.tab_create, bg=self.colors["frame_bg"], padx=20, pady=20)
        container.pack(fill="both", expand=True, padx=10, pady=10)
        
        row_dt = tk.Frame(container, bg=self.colors["frame_bg"])
        row_dt.pack(fill="x", pady=(0, 15))
        tk.Label(row_dt, text="Дата:", bg=self.colors["frame_bg"], fg=self.colors["text_fg"]).pack(side="left")
        self.date_var = tk.StringVar(value=datetime.datetime.now().strftime("%d.%m.%Y"))
        date_entry = tk.Entry(row_dt, textvariable=self.date_var, width=14, bg=self.colors["entry_bg"], 
                 fg=self.colors["text_fg"], relief="flat")
        date_entry.pack(side="left", padx=8)
        self.setup_clipboard_hotkeys(date_entry)

        tk.Label(row_dt, text="Время:", bg=self.colors["frame_bg"], fg=self.colors["text_fg"]).pack(side="left", padx=(15,0))
        self.time_var = tk.StringVar(value=datetime.datetime.now().strftime("%H:%M"))
        time_entry = tk.Entry(row_dt, textvariable=self.time_var, width=10, bg=self.colors["entry_bg"], 
                 fg=self.colors["text_fg"], relief="flat")
        time_entry.pack(side="left", padx=8)
        self.setup_clipboard_hotkeys(time_entry)

        row_meta = tk.Frame(container, bg=self.colors["frame_bg"])
        row_meta.pack(fill="x", pady=(0, 15))
        tk.Label(row_meta, text="Тип:", bg=self.colors["frame_bg"], fg=self.colors["text_fg"]).pack(side="left")
        self.type_var = tk.StringVar(value="update")
        ttk.Combobox(row_meta, textvariable=self.type_var, values=["update", "event", "general", "community"], 
                     width=12, state="readonly").pack(side="left", padx=8)
        self.important_var = tk.BooleanVar(value=False)
        tk.Checkbutton(row_meta, text=" ВАЖНАЯ", variable=self.important_var, 
                       bg=self.colors["frame_bg"], fg="#ff6b6b", selectcolor=self.colors["frame_bg"],
                       activebackground=self.colors["frame_bg"]).pack(side="right")

        grid_frame = tk.Frame(container, bg=self.colors["frame_bg"])
        grid_frame.pack(fill="x", expand=True)
        grid_frame.columnconfigure(1, weight=1)
        
        fields = [("Заголовок RU", "title_ru"), ("Заголовок EN", "title_en"),
                  ("Описание RU", "desc_ru"), ("Описание EN", "desc_en")]
        self.create_fields = {}
        for i, (label, key) in enumerate(fields):
            tk.Label(grid_frame, text=label+":", bg=self.colors["frame_bg"], fg=self.colors["text_fg"]).grid(row=i, column=0, sticky="w", pady=8)
            if "desc" in key:
                txt = tk.Text(grid_frame, bg=self.colors["entry_bg"], fg=self.colors["text_fg"], 
                              relief="flat", height=3, wrap="word", font=("Segoe UI", 10))
                txt.grid(row=i, column=1, sticky="ew", pady=8, padx=(10,0))
                self.setup_clipboard_hotkeys(txt)
                self.create_fields[key] = txt
            else:
                ent = tk.Entry(grid_frame, bg=self.colors["entry_bg"], fg=self.colors["text_fg"], 
                               relief="flat", font=("Segoe UI", 10))
                ent.grid(row=i, column=1, sticky="ew", pady=8, padx=(10,0))
                self.setup_clipboard_hotkeys(ent)
                self.create_fields[key] = ent

        btn = tk.Button(self.tab_create, text=" ОПУБЛИКОВАТЬ", command=self.schedule_or_publish, 
                        bg=self.colors["accent"], fg="white", font=("Segoe UI", 11, "bold"), height=2, relief="flat")
        btn.pack(fill="x", padx=20, pady=15)
        btn.bind("<Enter>", lambda e: btn.config(bg=self.colors["btn_hover"]))
        btn.bind("<Leave>", lambda e: btn.config(bg=self.colors["accent"]))

    def build_list_tab(self):
        list_container = tk.Frame(self.tab_list, bg=self.colors["bg"])
        list_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        tk.Label(list_container, text="Выберите новость (двойной клик):", 
                 bg=self.colors["bg"], fg="#808080", font=("Segoe UI", 9)).pack(anchor="w", pady=(0,5))
                 
        search_frame = tk.Frame(list_container, bg=self.colors["bg"])
        search_frame.pack(fill="x", pady=(0, 10))
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=self.search_var, 
                                bg=self.colors["entry_bg"], fg=self.colors["text_fg"], relief="flat")
        search_entry.pack(fill="x", padx=5)
        search_entry.bind("<KeyRelease>", lambda e: self.filter_news())
        self.setup_clipboard_hotkeys(search_entry)
        
        list_inner = tk.Frame(list_container, bg=self.colors["bg"])
        list_inner.pack(fill="both", expand=True)
        scrollbar = tk.Scrollbar(list_inner); scrollbar.pack(side="right", fill="y")
        self.news_listbox = tk.Listbox(list_inner, bg=self.colors["entry_bg"], fg=self.colors["text_fg"],
                                       yscrollcommand=scrollbar.set, font=("Consolas", 10), 
                                       selectbackground=self.colors["accent"], relief="flat", highlightthickness=0)
        self.news_listbox.pack(fill="both", expand=True)
        scrollbar.config(command=self.news_listbox.yview)
        self.news_listbox.bind("<Double-Button-1>", self.on_news_select)
        
        self.editor_frame = tk.Frame(self.tab_list, bg=self.colors["frame_bg"], padx=20, pady=15)
        tk.Label(self.editor_frame, text="️ РЕДАКТИРОВАНИЕ", bg=self.colors["frame_bg"], 
                 fg="#8fbc8f", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0,10))
                 
        edit_grid = tk.Frame(self.editor_frame, bg=self.colors["frame_bg"])
        edit_grid.pack(fill="x"); edit_grid.columnconfigure(1, weight=1)
        
        self.edit_date = self._add_edit_field(edit_grid, 0, "Дата")
        self.edit_type = self._add_edit_field(edit_grid, 1, "Тип")
        self.edit_title_ru = self._add_edit_field(edit_grid, 2, "Заголовок RU")
        self.edit_title_en = self._add_edit_field(edit_grid, 3, "Заголовок EN")
        
        tk.Label(edit_grid, text="Описание RU:", bg=self.colors["frame_bg"], fg=self.colors["text_fg"]).grid(row=4, column=0, sticky="w", pady=8)
        self.edit_desc_ru = tk.Text(edit_grid, bg=self.colors["entry_bg"], fg=self.colors["text_fg"], relief="flat", height=3, wrap="word")
        self.edit_desc_ru.grid(row=4, column=1, sticky="ew", pady=8, padx=(10,0))
        self.setup_clipboard_hotkeys(self.edit_desc_ru)

        tk.Label(edit_grid, text="Описание EN:", bg=self.colors["frame_bg"], fg=self.colors["text_fg"]).grid(row=5, column=0, sticky="w", pady=8)
        self.edit_desc_en = tk.Text(edit_grid, bg=self.colors["entry_bg"], fg=self.colors["text_fg"], relief="flat", height=3, wrap="word")
        self.edit_desc_en.grid(row=5, column=1, sticky="ew", pady=8, padx=(10,0))
        self.setup_clipboard_hotkeys(self.edit_desc_en)
        
        self.edit_important = tk.BooleanVar(value=False)
        tk.Checkbutton(self.editor_frame, text="❗ ВАЖНАЯ", variable=self.edit_important, 
                       bg=self.colors["frame_bg"], fg="#ff6b6b", selectcolor=self.colors["frame_bg"],
                       activebackground=self.colors["frame_bg"]).pack(anchor="w", pady=10)

        btn_row = tk.Frame(self.editor_frame, bg=self.colors["frame_bg"])
        btn_row.pack(fill="x", pady=(10, 0))
        tk.Button(btn_row, text="💾 Сохранить", command=self.save_edited_news, 
                  bg=self.colors["accent"], fg="white", relief="flat", font=("Segoe UI", 10, "bold")
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        tk.Button(btn_row, text="📋 BB-код", command=self.copy_bb_code, 
                  bg=self.colors["success"], fg="white", relief="flat", font=("Segoe UI", 10, "bold")
        ).pack(side="left", fill="x", expand=True, padx=(5, 5))
        
        tk.Button(btn_row, text="🗑️ Удалить", command=self.delete_selected_news, 
                  bg=self.colors["danger"], fg="white", relief="flat", font=("Segoe UI", 10, "bold")
        ).pack(side="right", fill="x", expand=True, padx=(5, 0))

        self.refresh_news_list()

    def _add_edit_field(self, parent, row, label_text):
        tk.Label(parent, text=label_text+":", bg=self.colors["frame_bg"], fg=self.colors["text_fg"]).grid(row=row, column=0, sticky="w", pady=8)
        ent = tk.Entry(parent, bg=self.colors["entry_bg"], fg=self.colors["text_fg"], relief="flat", font=("Segoe UI", 10))
        ent.grid(row=row, column=1, sticky="ew", pady=8, padx=(10,0))
        self.setup_clipboard_hotkeys(ent)
        return ent

    def build_settings_tab(self):
        container = tk.Frame(self.tab_settings, bg=self.colors["frame_bg"], padx=25, pady=25)
        container.pack(fill="both", expand=True, padx=10, pady=10)
        tk.Label(container, text="️ НАСТРОЙКИ ПРОГРАММЫ", bg=self.colors["frame_bg"], 
                 fg=self.colors["text_fg"], font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0,20))
                 
        self.auto_start_var = tk.BooleanVar(value=self.settings.get("auto_start", "False") == "True")
        tk.Checkbutton(container, text="✅ Запускать программу при старте Windows", 
                       variable=self.auto_start_var, bg=self.colors["frame_bg"], fg=self.colors["text_fg"], 
                       selectcolor=self.colors["frame_bg"], font=("Segoe UI", 10),
                       command=self.toggle_auto_start).pack(anchor="w", pady=10)
                       
        total = len(getattr(self, 'all_news_data', []))
        important = sum(1 for n in getattr(self, 'all_news_data', []) if n.get('important')=='true')
        scheduled = len(self.scheduler.get_jobs())
        tk.Label(container, text=f"📈 Всего новостей: {total} | Важных: {important} | Запланировано: {scheduled}", 
                 bg=self.colors["frame_bg"], fg="#8fbc8f", font=("Segoe UI", 10)).pack(anchor="w", pady=(10,0))
                 
        tk.Label(container, text="ℹ️ Планировщик активен и работает в фоне.", 
                 bg=self.colors["frame_bg"], fg="#8fbc8f", font=("Segoe UI", 9)).pack(anchor="w", pady=(20,0))

    def refresh_news_list(self):
        self.news_listbox.delete(0, tk.END)
        self.all_news_data = []
        file_path = os.path.join(REPO_PATH, NEWS_FILE)
        
        # ✅ Фикс: проверка существования файла
        if not os.path.exists(file_path):
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.read().split('\n'); current_news = {}
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith('#'): continue
                    if line == "[NEWS]":
                        if current_news and 'title_ru' in current_news:
                            self.all_news_data.append(current_news.copy())
                            imp = " ❗" if current_news.get('important') == 'true' else ""
                            self.news_listbox.insert(tk.END, f"[{current_news.get('date', '?')}] {current_news.get('title_ru', 'No Title')}{imp}")
                        current_news = {}
                    elif "=" in line:
                        k, v = line.split("=", 1); current_news[k.strip()] = v.strip()
                if current_news and 'title_ru' in current_news:
                    self.all_news_data.append(current_news.copy())
                    imp = " ❗" if current_news.get('important') == 'true' else ""
                    self.news_listbox.insert(tk.END, f"[{current_news.get('date', '?')}] {current_news.get('title_ru', 'No Title')}{imp}")
        except Exception as e: messagebox.showerror("Ошибка чтения", str(e))

    def filter_news(self):
        query = self.search_var.get().lower()
        self.news_listbox.delete(0, tk.END)
        for news in self.all_news_data:
            title = news.get('title_ru', '').lower()
            date = news.get('date', '')
            type_n = news.get('type', '').lower()
            if query in title or query in date or query in type_n:
                imp = " ❗" if news.get('important') == 'true' else ""
                self.news_listbox.insert(tk.END, f"[{date}] {news.get('title_ru', 'No Title')}{imp}")

    def on_news_select(self, event):
        selection = self.news_listbox.curselection()
        if not selection: return
        idx = selection[0]; news = self.all_news_data[idx]
        self.editor_frame.pack(fill="x", padx=10, pady=(0, 10), side="bottom")
        
        self.edit_date.delete(0, tk.END); self.edit_date.insert(0, news.get('date', ''))
        self.edit_type.delete(0, tk.END); self.edit_type.insert(0, news.get('type', ''))
        self.edit_important.set(news.get('important', 'false') == 'true')
        self.edit_title_ru.delete(0, tk.END); self.edit_title_ru.insert(0, news.get('title_ru', ''))
        self.edit_title_en.delete(0, tk.END); self.edit_title_en.insert(0, news.get('title_en', ''))
        self.edit_desc_ru.delete("1.0", tk.END); self.edit_desc_ru.insert("1.0", news.get('desc_ru', ''))
        self.edit_desc_en.delete("1.0", tk.END); self.edit_desc_en.insert("1.0", news.get('desc_en', ''))
        self.current_edit_index = idx
        self.original_news = news.copy()

    def copy_bb_code(self):
        if not hasattr(self, 'current_edit_index'): 
            messagebox.showwarning("Внимание", "Сначала выберите новость!"); return
        news = self.all_news_data[self.current_edit_index]
        bb = f"[b]{news['title_ru']}[/b]\n\n{news['desc_ru']}"
        self.root.clipboard_clear(); self.root.clipboard_append(bb)
        messagebox.showinfo("Скопировано!", "BB-код скопирован в буфер обмена")

    def save_edited_news(self):
        if not hasattr(self, 'current_edit_index'): return
        current = {
            'date': self.edit_date.get(), 'type': self.edit_type.get(),
            'important': str(self.edit_important.get()).lower(),
            'title_ru': self.edit_title_ru.get(), 'title_en': self.edit_title_en.get(),
            'desc_ru': self.edit_desc_ru.get('1.0', 'end-1c'), 'desc_en': self.edit_desc_en.get('1.0', 'end-1c')
        }
        if current == self.original_news:
            messagebox.showinfo("Инфо", "Изменений нет, сохранение пропущено."); return
            
        idx = self.current_edit_index
        new_block = (f"[NEWS]\ndate={current['date']}\ntype={current['type']}\n"
            f"important={current['important']}\n"
            f"title_ru={current['title_ru']}\ntitle_en={current['title_en']}\n"
            f"desc_ru={current['desc_ru']}\ndesc_en={current['desc_en']}\n\n")
        
        file_path = os.path.join(REPO_PATH, NEWS_FILE)
        try:
            with open(file_path, "r", encoding="utf-8") as f: content = f.read()
            new_content = ""; current_idx = 0; lines = content.split('\n'); i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line == "[NEWS]":
                    j = i + 1
                    while j < len(lines) and lines[j].strip() != "[NEWS]" and lines[j].strip() != "": j += 1
                    if current_idx == idx: new_content += new_block
                    else:
                        for k in range(i, j): new_content += lines[k] + "\n"
                    i = j; current_idx += 1
                else: new_content += lines[i] + "\n"; i += 1
            with open(file_path, "w", encoding="utf-8") as f: f.write(new_content)
            
            if self.safe_git_commit_push(f"Edited news: {current['title_ru']}"):
                messagebox.showinfo("Успех", "Новость обновлена!"); self.editor_frame.pack_forget(); self.refresh_news_list()
        except Exception as e: messagebox.showerror("Ошибка", str(e))

    def delete_selected_news(self):
        if not hasattr(self, 'current_edit_index'): return
        if not messagebox.askyesno("Подтверждение", "Удалить новость навсегда?"): return
        idx = self.current_edit_index; title = self.all_news_data[idx].get('title_ru', 'Unknown')
        file_path = os.path.join(REPO_PATH, NEWS_FILE)
        try:
            with open(file_path, "r", encoding="utf-8") as f: content = f.read()
            new_content = ""; current_idx = 0; lines = content.split('\n'); i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line == "[NEWS]":
                    j = i + 1
                    while j < len(lines) and lines[j].strip() != "[NEWS]" and lines[j].strip() != "": j += 1
                    if current_idx != idx:
                        for k in range(i, j): new_content += lines[k] + "\n"
                    i = j; current_idx += 1
                else: new_content += lines[i] + "\n"; i += 1
            with open(file_path, "w", encoding="utf-8") as f: f.write(new_content)
            if self.safe_git_commit_push(f"Deleted news: {title}"):
                messagebox.showinfo("Успех", "Новость удалена!"); self.editor_frame.pack_forget(); self.refresh_news_list()
        except Exception as e: messagebox.showerror("Ошибка", str(e))

    def schedule_or_publish(self):
        t_ru = self.create_fields['title_ru'].get()
        if not t_ru: messagebox.showwarning("Внимание", "Нужен заголовок!"); return
        
        # Сохраняем черновик
        with open(os.path.join(REPO_PATH, DRAFT_FILE), "w", encoding="utf-8") as f:
            f.write(f"title_ru={t_ru}\n")
            f.write(f"title_en={self.create_fields['title_en'].get()}\n")
            f.write(f"desc_ru={self.create_fields['desc_ru'].get('1.0', 'end-1c')}\n")
            f.write(f"desc_en={self.create_fields['desc_en'].get('1.0', 'end-1c')}\n")
            f.write(f"type={self.type_var.get()}\n")
            f.write(f"date={self.date_var.get()}\n")
            f.write(f"time={self.time_var.get()}\n")

        date_str = self.date_var.get(); time_str = self.time_var.get()
        try: pub_time = datetime.datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
        except: messagebox.showerror("Ошибка", "Неверный формат даты/времени"); return
        now = datetime.datetime.now()
        news_data = {"date": date_str, "type": self.type_var.get(), "important": str(self.important_var.get()).lower(), 
                     "title_ru": t_ru, "title_en": self.create_fields['title_en'].get(), 
                     "desc_ru": self.create_fields['desc_ru'].get('1.0', 'end-1c'), 
                     "desc_en": self.create_fields['desc_en'].get('1.0', 'end-1c')}
        
        if pub_time <= now: 
            self.publish_news(news_data)
        else:
            job_id = f"news_{int(now.timestamp())}"
            self.scheduler.add_job(self.publish_news, 'date', run_date=pub_time, args=[news_data], id=job_id)
            self.save_job_to_file(job_id, pub_time, news_data)
            messagebox.showinfo("Запланировано", f"Новость выйдет {date_str} в {time_str}!\n(Сохранено и переживет перезапуск)")

    def publish_news(self, data):
        new_block = f"[NEWS]\ndate={data['date']}\ntype={data['type']}\nimportant={data['important']}\ntitle_ru={data['title_ru']}\ntitle_en={data['title_en']}\ndesc_ru={data['desc_ru']}\ndesc_en={data['desc_en']}\n\n"
        file_path = os.path.join(REPO_PATH, NEWS_FILE)
        try:
            with open(file_path, "r", encoding="utf-8") as f: old = f.read()
            with open(file_path, "w", encoding="utf-8") as f: f.write(new_block + old)
            
            if self.safe_git_commit_push(f"News: {data['title_ru']}"):
                # ✅ Фикс: Удаляем черновик после успешной публикации
                draft_path = os.path.join(REPO_PATH, DRAFT_FILE)
                if os.path.exists(draft_path):
                    os.remove(draft_path)
                
                if hasattr(self, 'tray_icon'): self.tray_icon.notify("Forgotten Trails", f"Опубликовано: {data['title_ru']}")
                self.refresh_news_list()
                
                # Очищаем поля ввода после публикации
                self.clear_create_fields()
                
                self.remove_completed_job(data['title_ru'], data['date'])
        except Exception as e: print(f"Ошибка публикации: {e}")

    def clear_create_fields(self):
        """Очищает поля на вкладке создания"""
        self.create_fields['title_ru'].delete(0, tk.END)
        self.create_fields['title_en'].delete(0, tk.END)
        self.create_fields['desc_ru'].delete("1.0", tk.END)
        self.create_fields['desc_en'].delete("1.0", tk.END)
        self.date_var.set(datetime.datetime.now().strftime("%d.%m.%Y"))
        self.time_var.set(datetime.datetime.now().strftime("%H:%M"))

    def restore_draft(self):
        draft_path = os.path.join(REPO_PATH, DRAFT_FILE)
        if os.path.exists(draft_path):
            try:
                with open(draft_path, "r", encoding="utf-8") as f:
                    draft = dict(line.strip().split("=", 1) for line in f if "=" in line)
                if draft.get('title_ru'):
                    if messagebox.askyesno("Восстановить?", "Найден несохраненный черновик. Загрузить его?"):
                        self.create_fields['title_ru'].insert(0, draft.get('title_ru', ''))
                        self.create_fields['title_en'].insert(0, draft.get('title_en', ''))
                        self.create_fields['desc_ru'].insert("1.0", draft.get('desc_ru', ''))
                        self.create_fields['desc_en'].insert("1.0", draft.get('desc_en', ''))
                        self.type_var.set(draft.get('type', 'update'))
                        self.date_var.set(draft.get('date', datetime.datetime.now().strftime("%d.%m.%Y")))
                        self.time_var.set(draft.get('time', datetime.datetime.now().strftime("%H:%M")))
                        self.notebook.select(self.tab_create)
                    else:
                        # Если пользователь отказался, удаляем старый битый черновик
                        os.remove(draft_path)
            except: pass

    def save_job_to_file(self, job_id, run_date, data):
        jobs = self.load_jobs_from_file()
        jobs[job_id] = {
            "run_date": run_date.strftime("%d.%m.%Y %H:%M"),
            "data": data
        }
        with open(os.path.join(REPO_PATH, JOBS_FILE), "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)

    def load_jobs_from_file(self):
        path = os.path.join(REPO_PATH, JOBS_FILE)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: return {}
        return {}

    def remove_completed_job(self, title, date):
        jobs = self.load_jobs_from_file()
        keys_to_remove = []
        for job_id, job_data in jobs.items():
            if (job_data['data'].get('title_ru') == title and 
                job_data['data'].get('date') == date):
                keys_to_remove.append(job_id)
        
        for key in keys_to_remove:
            del jobs[key]
            
        with open(os.path.join(REPO_PATH, JOBS_FILE), "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)

    def restore_scheduled_jobs(self):
        jobs = self.load_jobs_from_file()
        restored_count = 0
        now = datetime.datetime.now()
        
        for job_id, job_data in jobs.items():
            try:
                run_date = datetime.datetime.strptime(job_data['run_date'], "%d.%m.%Y %H:%M")
                if run_date > now:
                    self.scheduler.add_job(
                        self.publish_news, 'date', 
                        run_date=run_date, 
                        args=[job_data['data']], 
                        id=job_id
                    )
                    restored_count += 1
                else:
                    del jobs[job_id]
            except Exception as e:
                print(f"Ошибка восстановления задачи {job_id}: {e}")
        
        with open(os.path.join(REPO_PATH, JOBS_FILE), "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
            
        if restored_count > 0:
            print(f"✅ Восстановлено {restored_count} запланированных новостей")

    def setup_hotkeys(self):
        self.root.bind("<Control-s>", lambda e: self.save_edited_news() if hasattr(self, 'current_edit_index') else None)
        self.root.bind("<Control-n>", lambda e: self.notebook.select(self.tab_create))
        self.root.bind("<Escape>", lambda e: self.editor_frame.pack_forget() if hasattr(self, 'editor_frame') else None)
        self.root.bind("<Control-f>", lambda e: (self.notebook.select(self.tab_list), self.search_var.set(""), self.root.focus_set()) )

    def _run_git_cmd(self, args):
        try:
            result = subprocess.run(["git"] + args, cwd=REPO_PATH, capture_output=True, text=True, check=True)
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.stderr

    def safe_git_commit_push(self, message):
        try: current_branch = self.repo.active_branch.name
        except TypeError:
            messagebox.showwarning("Внимание", "Detached HEAD detected. Возвращаю на main...")
            self._run_git_cmd(["checkout", "main"]); current_branch = "main"

        success, err = self._run_git_cmd(["add", NEWS_FILE])
        if not success: messagebox.showerror("Git Error", f"Не удалось добавить файл:\n{err}"); return False
        success, err = self._run_git_cmd(["commit", "-m", message])
        if not success:
            if "nothing to commit" in err.lower(): return True 
            messagebox.showerror("Git Error", f"Ошибка коммита:\n{err}"); return False
        
        self._run_git_cmd(["pull", "--rebase", "-X", "ours"])
        
        if self.repo.remotes:
            success, err = self._run_git_cmd(["push", "origin", current_branch])
            if not success:
                if "rejected" in err.lower():
                    messagebox.showwarning("Требуется ручное вмешательство", 
                        "Автоматическое слияние не удалось. Выполните в консоли:\ngit pull --rebase\ngit push")
                    return False
                messagebox.showerror("Git Error", f"Ошибка пуша:\n{err}"); return False
        return True

    def setup_tray_icon(self):
        image = Image.new('RGB', (64, 64), color=(92, 92, 92)); draw = ImageDraw.Draw(image); draw.text((10, 20), "FT", fill=(255, 255, 255))
        menu = pystray.Menu(pystray.MenuItem('Показать окно', self.show_window, default=True), pystray.MenuItem('Выход', self.quit_app))
        self.tray_icon = pystray.Icon("ft_news", image, "FT News Manager", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def minimize_to_tray(self): self.root.withdraw()
    def show_window(self, icon, item): self.root.deiconify()
    def quit_app(self, icon, item): self.scheduler.shutdown(); icon.stop(); self.root.destroy()

    def toggle_auto_start(self):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if self.auto_start_var.get(): winreg.SetValueEx(key, "FTNewsManager", 0, winreg.REG_SZ, f'"{app_path}" --tray')
            else: winreg.DeleteValue(key, "FTNewsManager")
            winreg.CloseKey(key)
            self.settings["auto_start"] = str(self.auto_start_var.get()); self.save_settings()
        except Exception as e: messagebox.showerror("Ошибка автозапуска", str(e))

    def check_auto_start(self):
        if "--tray" in sys.argv: self.root.withdraw()

    def load_settings(self):
        settings = {}
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1); settings[k] = v
        return settings

    def save_settings(self):
        with open(SETTINGS_FILE, "w") as f:
            for k, v in self.settings.items(): f.write(f"{k}={v}\n")

    def save_scale(self, value):
        self.settings["ui_scale"] = str(value); self.save_settings()

if __name__ == "__main__":
    app = FTNewsManager()