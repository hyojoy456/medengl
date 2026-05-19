# Тестовое приложение на Streamlit (Medical)

- 8 модулей с заданиями + итоговый тест.
- Админка: страница **Add Medical** (конструктор заданий для преподавателя).

## Запуск локально

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Публичная ссылка (Streamlit Cloud)

Нужен **публичный репозиторий на GitHub** и бесплатный хостинг Streamlit.

### Шаг 1. Репозиторий на GitHub

1. Зайдите на [https://github.com](https://github.com) и войдите (или зарегистрируйтесь).
2. Нажмите **+** → **New repository**.
3. Имя, например: `medical-streamlit-tests` (латиница, без пробелов).
4. Выберите **Public**.
5. **Не** ставьте галочки «Add README» / «Add .gitignore» — репозиторий должен быть пустым.
6. Нажмите **Create repository**.

### Шаг 2. Загрузить код с компьютера

В терминале (в папке проекта):

```bash
cd "/Users/novakkristina/Desktop/Новая папка"

git add -A
git commit -m "Initial commit: medical tests app"

# Подставьте СВОЙ логин и имя репозитория:
git remote add origin https://github.com/ВАШ_ЛОГИН/medical-streamlit-tests.git
git branch -M main
git push -u origin main
```

При `git push` GitHub попросит логин и **Personal Access Token** (не пароль от аккаунта).  
Создать токен: GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Generate new token** (права `repo`).

### Шаг 3. Деплой на Streamlit Cloud

1. Откройте [https://share.streamlit.io](https://share.streamlit.io) и войдите через GitHub.
2. **Create app** → выберите репозиторий `medical-streamlit-tests`.
3. **Main file path:** `app.py`
4. **App URL** (можно задать своё имя): например `medical-tests`
5. **Deploy**

Через 1–3 минуты появится ссылка вида:

`https://medical-tests.streamlit.app`

или

`https://ВАШ-ЛОГИН-medical-streamlit-tests.streamlit.app`

Это и есть **публичная ссылка** для учеников. Админка: в меню слева страница **Add Medical**.

### Если не получается подключить репозиторий

| Проблема | Что сделать |
|----------|-------------|
| «Not a git repository» | В папке проекта выполните `git init` |
| Streamlit не видит репозиторий | На GitHub репозиторий должен быть **Public**; в Streamlit Cloud нажмите **Authorize** для GitHub |
| Ошибка при `git push` | Используйте токен вместо пароля; проверьте URL `origin` |
| Большие файлы / отказ push | Репозиторий с картинками может быть тяжёлым; подождите или используйте [Git LFS](https://git-lfs.com) |
| Папка с кириллицей в пути | Лучше скопировать проект в путь без пробелов, например `~/Projects/medical-tests` |

### Важно для деплоя

- В репозитории должны быть папки `banks/`, `pages/`, `utils/` — без них приложение пустое.
- Файл `.streamlit/config.toml` уже в проекте (настройки для сервера).
- Секреты в `.streamlit/secrets.toml` в git **не** попадают (см. `.gitignore`).
