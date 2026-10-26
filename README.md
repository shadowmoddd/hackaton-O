
# 1. виртуальное окружение
python -m venv venv
venv\Scripts\Activate.ps1

# 2. установка библиотек
pip install -r requirements.txt

# 3. запуск
uvicorn main:app --reload