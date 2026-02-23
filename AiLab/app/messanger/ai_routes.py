from app.messanger import blueprint
from flask import (
    render_template,
    request,
    jsonify,
)  # Импортируем необходимые модули из Flask
import os
from flask_login import current_user
from sqlalchemy.orm import joinedload
from app import db, socketio
from app.base.config import UPLOAD_FOLDER, USER_FILES_PATH
from app.base.models import Message, Attachment, AIChat
from flask_login import login_required
from werkzeug.utils import secure_filename
from app.AI import AI_BOT_V3
from icecream import ic
import logging
bot = AI_BOT_V3()
logger = logging.getLogger(__name__)
@blueprint.route("/messenger/ai/contacts")
@login_required
def messenger_ai_contacts():
    chats = AIChat.query.filter_by(user_id=current_user.id).all()
    return render_template("messenger_ai_contacts.html", chats=chats)


@blueprint.route("/messenger/ai/chat/<int:ai_chat_id>")
@login_required
def messenger_ai_chat(ai_chat_id):
    messages = (
        Message.query.options(joinedload(Message.attachments))
        .filter(Message.ai_chat_id == ai_chat_id)  # <-- фильтр по значению переменной
        .order_by(Message.timestamp.asc())
        .all()
    )
    ai_chat = db.session.get(AIChat, ai_chat_id)

    return render_template("messenger_ai_chat.html", chat=ai_chat, messages=messages)

@blueprint.route("/messenger/ai/send", methods=["POST"])
@login_required
def send_ai_message():
    """Единый роут для текста + файлов."""
    try:
        # 1. Парсим входные данные
        if request.is_json:
            data = request.get_json()
            ai_chat_id = data.get("ai_chat_id")
            text = data.get("text", "").strip()
        else:
            ai_chat_id = request.form.get("ai_chat_id", type=int)
            text = request.form.get("text", "").strip()
        
        if not ai_chat_id or not text:
            return jsonify({"success": False, "error": "No chat or text"}), 400
        
        # 2. Проверяем чат
        ai_chat = db.session.get(AIChat, ai_chat_id)
        if not ai_chat or ai_chat.user_id != current_user.id:
            return jsonify({"success": False, "error": "Chat not found"}), 404
        
        # 3. Сообщение пользователя
        message = Message(
            sender_id=current_user.id,
            ai_chat_id=ai_chat_id,
            text=text,
            is_read=True
        )
        db.session.add(message)
        db.session.flush()
        
        # 4. Файлы
        attachments_data = []
        files = request.files.getlist("files") if not request.is_json else []
        if files:
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            allowed_ext = {"png", "jpg", "pdf", "py", "cpp", "txt"}
            
            for f in files:
                if f and f.filename:
                    ext = f.filename.rsplit(".", 1)[-1].lower()
                    if ext in allowed_ext:
                        filename = secure_filename(f"{message.id}_{f.filename}")
                        save_path = os.path.join(UPLOAD_FOLDER, filename)
                        f.save(save_path)
                        
                        attach = Attachment(
                            message_id=message.id,
                            url=save_path,
                            mime_type=f.mimetype
                        )
                        db.session.add(attach)
                        attachments_data.append({"url": save_path, "mime_type": f.mimetype})
        
        # 5. ✅ AI ОТВЕТ через bot.ask()
        files_context = [f["url"] for f in attachments_data]
        ai_response = bot.ask(
            prompt=text,
            context_path=ai_chat.context,
            userid=str(current_user.id),
            file_context=files_context
        )
        
        # 6. Сохраняем ответ ИИ
        ai_message = Message(
            ai_chat_id=ai_chat_id,
            text=ai_response,
            is_read=True
        )
        db.session.add(ai_message)
        db.session.commit()
        
        # 7. Socket.IO
        message_data = {
            "id": message.id, "sender_id": message.sender_id,
            "ai_chat_id": message.ai_chat_id, "text": message.text,
            "attachments": attachments_data,
            "timestamp": message.timestamp.isoformat(), "is_read": True
        }
        ai_message_data = {
            "id": ai_message.id, "sender_id": None,
            "ai_chat_id": ai_message.ai_chat_id, "text": ai_message.text,
            "attachments": [], "timestamp": ai_message.timestamp.isoformat(),
            "is_read": True
        }
        
        socketio.emit("new_message", message_data, room=f"user_{current_user.id}")
        socketio.emit("new_message", ai_message_data, room=f"user_{current_user.id}")
        
        return jsonify({"success": True, "message": message_data})
        
    except Exception as e:
        logger.error(f"AI Send error: {e}")
        db.session.rollback()
        return jsonify({"success": False, "error": "Server error"}), 500

@blueprint.route("/messenger/ai/mark_as_read/<int:ai_chat_id>", methods=["POST"])
@login_required
def ai_mark_as_read(ai_chat_id):
    # Помечаем все непрочитанные сообщения от этого пользователя как прочитанные
    Message.query.filter(
        Message.ai_chat_id == ai_chat_id,
        Message.is_read is False,
    ).update({"is_read": True})
    db.session.commit()
    return jsonify({"success": True})


@blueprint.route("/messenger/ai/mark_message_read/<int:message_id>", methods=["POST"])
@login_required
def ai_mark_message_read(message_id):
    message = Message.query.get_or_404(message_id)

    message.is_read = True
    db.session.commit()
    return jsonify({"success": True})


@blueprint.route("/messenger/ai/create_chat", methods=["POST"])
@login_required
def create_ai_chat():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Invalid JSON data"}), 400

        chat_name = data.get("name")
        if (
            not chat_name
            or not isinstance(chat_name, str)
            or len(chat_name.strip()) == 0
        ):
            return jsonify({"success": False, "error": "Chat name is required"}), 400

        # Создаём новый чат ИИ
        ai_chat = AIChat(
            user_id=current_user.id,
            name=chat_name.strip(),  # Значение по умолчанию
        )
        ai_chat.context = get_started_context(ai_chat.id)
        db.session.add(ai_chat)
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "ai_chat": {
                    "id": ai_chat.id,
                    "name": ai_chat.name,
                    "created_at": ai_chat.created_at.isoformat(),
                },
            }
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@blueprint.route("/ai/send", methods=["POST"])
def ai_send():
    ai_chat_id = request.form.get('ai_chat_id')
    text = request.form.get('text', '')
    
    # ✅ ГЕНЕРИРУЕМ ОТВЕТ AI
    ai_response = AI_BOT_V3.generate_response(text, ai_chat_id)
    
    # ✅ СОХРАНЯЕМ СООБЩЕНИЕ С sender_id = current_user.id
    message_data = {
        'sender_id': current_user.id,  # ← ФИКС!
        'ai_chat_id': ai_chat_id,
        'text': ai_response,
        'attachments': []
    }
    
    # Сохраняем в БД
    message_id = save_ai_message(message_data)
    
    # ✅ SocketIO EMIT С ПРАВИЛЬНЫМИ ДАННЫМИ
    socketio.emit('new_message', {
        'id': message_id,
        'sender_id': current_user.id,  # ← ФИКС!
        'ai_chat_id': ai_chat_id,
        'text': ai_response,
        'attachments': [],
        'timestamp': datetime.utcnow().isoformat(),
        'is_read': True
    }, room=f'user_{current_user.id}')
    
    return jsonify({'success': True})

def get_started_context(ai_chat_id):
    file_path = os.path.join(
        USER_FILES_PATH,
        "context",
        str(current_user.id),
        f"{current_user.id}-{ai_chat_id}.json",
    )
    user_folder = os.path.join(USER_FILES_PATH, "context", str(current_user.id))
    os.makedirs(user_folder, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as file:
        file.write("[]")
    return file_path
