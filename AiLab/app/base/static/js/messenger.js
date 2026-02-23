function isIdePage() {
    return window.location.pathname.startsWith('/ide');
}


const header = document.querySelector('.header');
if (header) {
    document.documentElement.style.setProperty(
        '--header-height',
        `${header.offsetHeight}px`
    );
}

// Инициализация Socket.IO с правильными параметрами
const socketio = io({
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
    transports: ['websocket', 'polling'], // Явно указываем транспорты
    withCredentials: true
});

const messengerContainer = document.getElementById('messenger-container');
const current_user_id = parseInt(messengerContainer.dataset.userId) || 0;

// Функция для фильтрации контактов
function filterContacts(searchTerm) {
    const contacts = document.querySelectorAll('.contact-item');
    searchTerm = searchTerm.toLowerCase();

    contacts.forEach(contact => {
        const name = contact.querySelector('.contact-name').textContent.toLowerCase();
        if (name.includes(searchTerm)) {
            contact.style.display = 'flex';
        } else {
            contact.style.display = 'none';
        }
    });
}

// Функция обновления статуса пользователя
function updateUserStatus(userId, isOnline) {
    const statusElement = document.querySelector(`.status-indicator[data-user-id="${userId}"]`);
    if (statusElement) {
        statusElement.classList.toggle('online', isOnline);
        statusElement.classList.toggle('offline', !isOnline);
    }
}

// Функция для быстрого обновления счетчика
function updateMessageCounter(increment = 1) {
    const badge = document.getElementById('unread-count');
    if (badge) {
        const currentCount = parseInt(badge.textContent) || 0;
        badge.textContent = currentCount + increment;
        badge.classList.toggle('hidden', currentCount + increment <= 0);
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const messengerButton = document.querySelector('.messenger-icon');
    const messengerContainer = document.getElementById('messenger-container');
    const closeMessenger = document.getElementById('close-messenger');
    const messengerContent = document.getElementById('messenger-content');
    const searchInput = document.getElementById('contact-search');

    // Обработчик поиска
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            filterContacts(this.value);
        });
    }

    // Открытие/закрытие мессенджера
    messengerButton.addEventListener('click', function () {
        messengerContainer.classList.toggle('open');
        if (messengerContainer.classList.contains('open')) {
            loadContacts();
        }
        if (isIdePage()) {
            document.querySelector('.part2-el').classList.toggle('open-messenger');
        }
    });

    closeMessenger.addEventListener('click', function () {
        messengerContainer.classList.remove('open');
        if (searchInput) searchInput.value = '';
        filterContacts('');
        document.querySelector('.part2-el').classList.remove('open-messenger');
    });

    // Загрузка списка контактов
    function loadContacts() {
        document.getElementById('messenger-header').classList.remove('hidden');
        fetch('/messenger/contacts')
            .then(response => response.text())
            .then(html => {
                document.getElementById('messenger-content').innerHTML = html;
                attachContactListeners();
                scrollToBottom();
            });
    }

    // Обработчики для контактов
    function attachContactListeners() {
        const contactItems = document.querySelectorAll('.contact-item');
        contactItems.forEach(item => {
            if (item.dataset.aiChats === "true") {
                item.addEventListener('click', function () {
                    loadAIContacts();
                });
            } else {
                item.addEventListener('click', function () {
                    const userId = this.dataset.userId;
                    if (userId) {
                        loadChat(userId);
                    } else {
                        console.error('User ID не найден для контакта:', this);
                    }
                });
            }
        });
    }

    function formatMessageTimes() {
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
        const yesterday = today - 86400000; // 24 часа в миллисекундах

        document.querySelectorAll('.message-time').forEach(element => {
            const isoString = element.dataset.timestamp;
            if (!isoString) return;

            // Создаём дату в UTC
            const messageDateUTC = new Date(isoString);
            if (isNaN(messageDateUTC.getTime())) return;

            // Корректируем на часовой пояс пользователя
            const userOffset = new Date().getTimezoneOffset() * 60000; // В миллисекундах
            const messageDate = new Date(messageDateUTC.getTime() - userOffset); // Переводим в локальное время

            // Определяем локаль пользователя
            const locale = navigator.language || 'ru-RU';

            // Получаем локализованное время
            const timeStr = messageDate.toLocaleTimeString(locale, {
                hour: '2-digit',
                minute: '2-digit'
            });

            // Определяем начало дня для сообщения
            const messageDayStart = new Date(
                messageDate.getFullYear(),
                messageDate.getMonth(),
                messageDate.getDate()
            ).getTime();

            if (messageDayStart === today) {
                element.textContent = timeStr;
            } else if (messageDayStart === yesterday) {
                element.textContent = `вчера в ${timeStr}`;
            } else {
                const dateStr = messageDate.toLocaleDateString(locale, {
                    day: '2-digit',
                    month: '2-digit',
                    year: messageDate.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
                });

                element.textContent = `${dateStr} ${timeStr}`;
            }
        });
    }


    // Загрузка чата с пользователем
    function loadChat(userId, savedText = '') {
        document.getElementById('messenger-header').classList.add('hidden');
        const messagesContainer = document.getElementById('messages-container');
        if (messagesContainer) {
            messagesContainer.innerHTML = ''; // Очищаем контейнер перед загрузкой
        }
        fetch(`/messenger/chat/${userId}`)
            .then(response => response.text())
            .then(html => {
                document.getElementById('messenger-content').innerHTML = html;
                formatMessageTimes(); // Форматирование времени
                scrollToBottom();
                // Восстанавливаем текст в textarea
                const input = document.getElementById('message-input');
                if (input && savedText) {
                    input.value = savedText;
                    input.style.height = 'auto';
                    input.style.height = Math.min(input.scrollHeight, 150) + 'px';
                }
                // Пометить сообщения как прочитанные
                fetch(`/messenger/mark_as_read/${userId}`, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCookie('csrf_token') }
                }).then(() => checkNewMessages());
                attachChatListeners(userId);
                attachAttachmentListeners();
            })
            .catch(error => {
                console.error('Ошибка загрузки чата:', error);
                alert('Не удалось загрузить чат');
            });
    }

    function attachChatListeners(userId) {
        const input = document.getElementById('message-input');
        const sendButton = document.querySelector('.send-button');
        const messagesContainer = document.getElementById('messages-container');
        const clearButton = document.getElementById('clear-history');

        clearButton.addEventListener('click', () => {
            const status = document.querySelector('.status-indicator')
            const recipient_id = status.dataset.userId
            const user_id = current_user_id

            const postData = {
                action: "clear_history",
                element: {
                    recipient_id: recipient_id
                }
            };

            // Отправка на сервер
            fetch('/api/execute-action', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(postData)
            })
                .then(response => response.json())
                .then(data => {
                    if (data.status === "success") {
                        loadChat(userId)
                    } else {
                        alert("Error: " + data.message);
                    }
                })
                .catch(error => {
                    console.error("Error:", error);
                    alert("Request failed");
                });
        });

        if (input) {
            input.addEventListener('input', function () {
                this.style.height = 'auto'; // Сброс высоты
                this.style.height = Math.min(this.scrollHeight, 150) + 'px'; // Ограничение по max-height
            });
            input.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault(); // Отменяем стандартное поведение (перенос строки)
                    sendMessage(); // Отправляем сообщение
                }
                // Если Shift + Enter — перенос строки работает как обычно
            });

            // Инициализируем начальную высоту (если есть текст при загрузке)
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 150) + 'px';
        }

        function sendMessage() {
            const text = input.value.trim();
            const fileInput = document.getElementById('file-input');
            const files = Array.from(fileInput.files); // Получаем текущие файлы

            if (!text && files.length === 0) return;

            const form = new FormData();
            form.append('recipient_id', userId);
            if (text) form.append('text', text);

            // Добавляем только текущие файлы
            files.forEach(f => form.append('files', f));

            fetch('/messenger/send', {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrf_token') },
                body: form
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        input.value = ''; // Очищаем текстовое поле
                        // Полностью сбрасываем input type="file"
                        fileInput.value = ''; // Сбрасываем значение
                        // Пересоздаем input для полной очистки
                        const newFileInput = document.createElement('input');
                        newFileInput.type = 'file';
                        newFileInput.id = 'file-input';
                        newFileInput.multiple = true;
                        newFileInput.accept = 'image/*,video/*,.pdf,.doc,.docx,.js,.html,.py,.cpp';
                        fileInput.parentNode.replaceChild(newFileInput, fileInput);
                        loadChat(userId); // Перезагружаем чат
                    } else {
                        alert(data.error || 'Ошибка отправки');
                    }
                })
                .catch(error => {
                    console.error('Ошибка отправки сообщения:', error);
                    alert('Не удалось отправить сообщение');
                });
        }


        sendButton.addEventListener('click', sendMessage);
        input.focus();

        const backButton = document.querySelector('.back-button');
        if (backButton) {
            backButton.addEventListener('click', loadContacts);
        }

    }

    function scrollToBottom() {
        const container = document.getElementById('messages-container');
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }

    // Получение CSRF токена
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
    }

    // Проверка новых сообщений
    function checkNewMessages() {
        fetch('/messenger/check_new')
            .then(response => response.json())
            .then(data => {
                const badge = document.getElementById('unread-count');
                if (badge) {
                    badge.textContent = data.count;
                    badge.classList.toggle('hidden', data.count <= 0);
                }
            });
    }

    // Настройка обработчиков Socket.IO
    function setupSocketListeners() {
        socketio.on('connect', function () {
            console.log('Socket.IO connected');
            socketio.emit('join_user_room');
        });

        socketio.on('new_message', function (data) {
            formatMessageTimes();
            const badge = document.getElementById('unread-count');
            const currentChat = document.querySelector('.chat-header');

            // Проверяем, является ли чат с ИИ (наличие ai_chat_id) или с пользователем (наличие sender_id)
            const isAIChat = !!data.ai_chat_id;

            // Обновляем счетчик непрочитанных сообщений и проигрываем звук только для чатов с пользователями
            if (!isAIChat && badge && data.sender_id != current_user_id) {
                const currentCount = parseInt(badge.textContent) || 0;
                badge.textContent = currentCount + 1;
                badge.classList.remove('hidden');
                playNotificationSound();
            }

            // Сохраняем содержимое textarea перед обновлением чата
            const input = document.getElementById('message-input');
            const currentText = input ? input.value : '';

            // Обновляем чат, если он активен
            if (currentChat) {
                if (isAIChat) {
                    const currentChatId = parseInt(currentChat.dataset.aiChatId);
                    if (currentChatId === data.ai_chat_id) {
                        console.log('Updating AI chat:', currentChatId);
                        loadAIChat(currentChatId, currentText); // Передаем сохраненный текст
                    }
                } else {
                    const currentChatUserId = parseInt(currentChat.dataset.userId);
                    if (
                        currentChatUserId === data.sender_id ||
                        (currentChatUserId === data.recipient_id && data.sender_id === current_user_id)
                    ) {
                        console.log('Updating chat for user:', currentChatUserId);
                        loadChat(currentChatUserId, currentText); // Передаем сохраненный текст
                    }
                }
            }
        });

        socketio.on('user_online', function (data) {
            console.log('User status:', data.user_id, data.online ? 'online' : 'offline');
            const statusElement = document.querySelector(`.status-indicator[data-user-id="${data.user_id}"]`);
            if (statusElement) {
                statusElement.classList.toggle('online', data.online);
                statusElement.classList.toggle('offline', !data.online);
            }
        });

        socketio.on('connect_error', function (err) {
            console.error('Socket.IO connection error:', err);
        });
    }

    // ===========================

    // Загрузка списка чатов с ИИ
    function loadAIContacts() {
        document.getElementById('messenger-header').classList.remove('hidden');
        fetch('/messenger/ai/contacts')
            .then(response => response.text())
            .then(html => {
                document.getElementById('messenger-content').innerHTML = html;
                attachAIContactListeners();
                scrollToBottom();
            });
    }

    // Обработчики для списка чатов с ИИ
    function attachAIContactListeners() {
        const contactItems = document.querySelectorAll('.contact-item[data-ai-chat-id]');
        contactItems.forEach(item => {
            item.addEventListener('click', function () {
                const aiChatId = this.dataset.aiChatId;
                loadAIChat(aiChatId);
            });
        });

        const backButton = document.querySelector('.back-button');
        if (backButton) {
            backButton.addEventListener('click', loadContacts);
        }

        const createChatButton = document.getElementById('create_chat_but');
        const createChatTextarea = document.getElementById('create_chat_textarea');
        if (createChatButton && createChatTextarea) {
            createChatButton.addEventListener('click', function () {
                const chatName = createChatTextarea.value.trim();
                if (!chatName) {
                    alert('Введите имя чата');
                    return;
                }

                fetch('/messenger/ai/create_chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrf_token')
                    },
                    body: JSON.stringify({ name: chatName })
                })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            createChatTextarea.value = ''; // Очищаем текстовое поле
                            loadAIContacts(); // Перезагружаем список чатов
                        } else {
                            alert(data.error || 'Ошибка создания чата');
                        }
                    })
                    .catch(error => {
                        console.error('Ошибка создания чата:', error);
                        alert('Не удалось создать чат');
                    });
            });
        }
        const backAiButton = document.getElementById('back-ai-button');
        if (backAiButton) {
            backAiButton.addEventListener('click', loadContacts);
        }
    }

    // Загрузка чата с ИИ
    function loadAIChat(aiChatId, savedText = '') {
        document.getElementById('messenger-header').classList.add('hidden');
        const messagesContainer = document.getElementById('messages-container');
        if (messagesContainer) {
            messagesContainer.innerHTML = ''; // Очищаем контейнер перед загрузкой
        }
        fetch(`/messenger/ai/chat/${aiChatId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.text();
            })
            .then(html => {
                const content = document.getElementById('messenger-content');
                if (!content) {
                    throw new Error('Элемент #messenger-content не найден в DOM');
                }
                content.innerHTML = html;
                if (!document.getElementById('messages-container')) {
                    throw new Error('Элемент #messages-container не найден в HTML');
                }
                formatMessageTimes(); // Форматирование времени
                scrollToBottom();
                // Восстанавливаем текст в textarea
                const input = document.getElementById('message-input');
                if (input && savedText) {
                    input.value = savedText;
                    input.style.height = 'auto';
                    input.style.height = Math.min(input.scrollHeight, 150) + 'px';
                }
                attachAIChatListeners(aiChatId);
                attachAttachmentListeners();
            })
            .catch(error => {
                console.error('Ошибка загрузки чата с ИИ:', error);
                alert(`Не удалось загрузить чат с ИИ: ${error.message}`);
            });
    }

    // Обработчики для чата с ИИ
    function attachAIChatListeners(aiChatId) {
        const input = document.getElementById('message-input');
        const sendButton = document.querySelector('.send-button');
        const messagesContainer = document.getElementById('messages-container');
        const clearButton = document.getElementById('clear-history');

        clearButton.addEventListener('click', () => {
            const postData = {
                action: "clear_history",
                element: {
                    ai_chat_id: aiChatId
                }
            };

            // Отправка на сервер
            fetch('/api/execute-action', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(postData)
            })
                .then(response => response.json())
                .then(data => {
                    if (data.status === "success") {
                        loadAIChat(aiChatId);
                    } else {
                        alert("Error: " + data.message);
                    }
                })
                .catch(error => {
                    console.error("Error:", error);
                    alert("Request failed");
                });
        });

        if (input) {
            input.addEventListener('input', function () {
                this.style.height = 'auto'; // Сброс высоты
                this.style.height = Math.min(this.scrollHeight, 150) + 'px'; // Ограничение по max-height
            });
            input.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault(); // Отменяем стандартное поведение (перенос строки)
                    sendAIMessage(); // Отправляем сообщение
                }
                // Если Shift + Enter — перенос строки работает как обычно
            });

            // Инициализируем начальную высоту (если есть текст при загрузке)
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 150) + 'px';
        }

        function sendAIMessage() {
            const input = document.getElementById('message-input');
            const text = input.value.trim();
            const fileInput = document.getElementById('file-input');
            const files = Array.from(fileInput.files);
            const messagesContainer = document.getElementById('messages-container');

            if (!text && files.length === 0) return;

            // 1. Показываем сообщение юзера
            if (text) {
                const messageElement = document.createElement('div');
                messageElement.className = 'message message-sent';
                messageElement.innerHTML = `
            <div class="message-content">${text}</div>
            <span class="message-time" data-timestamp="${new Date().toISOString()}"></span>
        `;
                messagesContainer.appendChild(messageElement);
                formatMessageTimes();
                scrollToBottom();
            }

            // 2. "ИИ печатает..." 
            const thinkingElement = document.createElement('div');
            thinkingElement.id = 'ai-thinking';
            thinkingElement.className = 'message message-incoming thinking';
            thinkingElement.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
            messagesContainer.appendChild(thinkingElement);
            scrollToBottom();

            // 3. Очистка
            input.value = '';
            input.style.height = 'auto';
            fileInput.value = '';
            const newFileInput = document.createElement('input');
            newFileInput.type = 'file'; newFileInput.id = 'file-input';
            newFileInput.multiple = true; newFileInput.accept = 'image/*,video/*,.pdf,.doc,.docx,.js,.html,.py,.cpp';
            fileInput.parentNode.replaceChild(newFileInput, fileInput);

            // 4. Запрос с ЛОНГИМ ТАЙМАУТОМ
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 120000); // 2 минуты

            const form = new FormData();
            form.append('ai_chat_id', aiChatId);
            if (text) form.append('text', text);
            files.forEach(f => form.append('files', f));

            fetch('/messenger/ai/send', {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrf_token') },
                body: form,
                signal: controller.signal
            })
                .then(res => {
                    clearTimeout(timeout);
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    return res.json();
                })
                .then(data => {
                    thinkingElement.remove();
                    if (data.success) {
                        loadAIChat(aiChatId); // ✅ Перезагрузка чата
                    } else {
                        showError('❌ ' + (data.error || 'Ошибка сервера'));
                    }
                })
                .catch(err => {
                    clearTimeout(timeout);
                    thinkingElement.remove();
                    console.error('AI Error:', err);
                    if (err.name !== 'AbortError') {
                        showError('⏰ AI думает долго... Подождите или повторите');
                    }
                });

            input.focus();
            // Инициализация
            setupSocketListeners();
            checkNewMessages();
            setInterval(checkNewMessages, 30000);
        }



        function showError(text) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'message message-incoming error';
            errorDiv.textContent = text;
            document.getElementById('messages-container').appendChild(errorDiv);
            scrollToBottom();
        }

    });




