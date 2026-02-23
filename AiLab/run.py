import eventlet

eventlet.monkey_patch()  # Патчим библиотеки для работы с eventlet

from flask_migrate import Migrate
from config import Config
from app import create_app, db, socketio

# Создаём приложение и инициализируем миграции
app = create_app(Config)
Migrate(app, db)

if __name__ == "__main__":
    # Запускаем сервер через SocketIO с eventlet
    socketio.run(
        app, host="0.0.0.0", port=5000, debug=True
    )  # debug=False для продакшена
    
