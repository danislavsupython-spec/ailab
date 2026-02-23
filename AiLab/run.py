from flask_migrate import Migrate
from config import Config
from app import create_app, db, socketio
import os


app = create_app(Config)
Migrate(app, db)


if __name__ == "__main__":
    port = int(os.getenv('PORT', 8080))
    socketio.run(
        app, 
        host="0.0.0.0", 
        port=port, 
        debug=True,
        allow_unsafe_werkzeug=True,
        use_reloader=False,      # ← ДОБАВЬ
    )
