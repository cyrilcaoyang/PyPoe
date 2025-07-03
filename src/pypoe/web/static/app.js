class PyPoeChat {
    constructor() {
        this.currentConversationId = null;
        this.currentWebSocket = null;
        this.isConnected = false;
        this.currentBotResponse = null;
        
        this.initElements();
        this.bindEvents();
        this.loadConversations();
    }
    
    initElements() {
        this.messagesContainer = document.getElementById('messages-container');
        this.messageInput = document.getElementById('message-input');
        this.sendBtn = document.getElementById('send-btn');
        this.conversationsList = document.getElementById('conversations-list');
        this.currentChatTitle = document.getElementById('current-chat-title');
        this.currentBotName = document.getElementById('current-bot-name');
        this.botSelect = document.getElementById('bot-select');
        this.newChatBtn = document.getElementById('new-chat-btn');
        this.newChatModal = document.getElementById('new-chat-modal');
        this.newChatForm = document.getElementById('new-chat-form');
    }
    
    bindEvents() {
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        this.newChatBtn.addEventListener('click', () => this.showModal());
        document.querySelector('.close').addEventListener('click', () => this.hideModal());
        document.getElementById('cancel-btn').addEventListener('click', () => this.hideModal());
        this.newChatForm.addEventListener('submit', (e) => this.createConversation(e));
        
        this.conversationsList.addEventListener('click', (e) => {
            if (e.target.closest('.delete-btn')) {
                this.deleteConversation(e.target.closest('.delete-btn').dataset.id);
            } else if (e.target.closest('.conversation-item')) {
                this.selectConversation(e.target.closest('.conversation-item').dataset.id);
            }
        });
    }
    
    async loadConversations() {
        try {
            const response = await fetch('/api/conversations');
            const conversations = await response.json();
            this.renderConversations(conversations);
        } catch (error) {
            console.error('Error loading conversations:', error);
        }
    }
    
    renderConversations(conversations) {
        this.conversationsList.innerHTML = '';
        conversations.forEach(conv => {
            const div = document.createElement('div');
            div.className = 'conversation-item';
            div.dataset.id = conv.id;
            div.innerHTML = `
                <div class="conversation-info">
                    <h4>${this.escapeHtml(conv.title)}</h4>
                    <p><i class="fas fa-robot"></i> ${this.escapeHtml(conv.bot_name)}</p>
                    <small>${new Date(conv.created_at).toLocaleString()}</small>
                </div>
                <button class="delete-btn" data-id="${conv.id}">
                    <i class="fas fa-trash"></i>
                </button>
            `;
            this.conversationsList.appendChild(div);
        });
    }
    
    async selectConversation(conversationId) {
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-id="${conversationId}"]`).classList.add('active');
        
        try {
            const response = await fetch(`/api/conversation/${conversationId}/messages`);
            const messages = await response.json();
            
            this.currentConversationId = conversationId;
            const conversationElement = document.querySelector(`[data-id="${conversationId}"]`);
            const title = conversationElement.querySelector('h4').textContent;
            const botName = conversationElement.querySelector('p').textContent.replace('🤖 ', '').trim();
            
            this.currentChatTitle.textContent = title;
            this.currentBotName.textContent = `Bot: ${botName}`;
            this.botSelect.value = botName;
            
            this.messageInput.disabled = false;
            this.sendBtn.disabled = false;
            
            this.renderMessages(messages);
            this.connectWebSocket(conversationId);
        } catch (error) {
            console.error('Error loading conversation:', error);
        }
    }
    
    renderMessages(messages) {
        this.messagesContainer.innerHTML = '';
        messages.forEach(msg => this.addMessage(msg.role, msg.content, false));
        this.scrollToBottom();
    }
    
    addMessage(role, content, animate = true) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-${role === 'user' ? 'user' : 'robot'}"></i>
            </div>
            <div class="message-content">${this.escapeHtml(content)}</div>
        `;
        
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
        return messageDiv;
    }
    
    connectWebSocket(conversationId) {
        if (this.currentWebSocket) this.currentWebSocket.close();
        
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/chat/${conversationId}`;
        
        this.currentWebSocket = new WebSocket(wsUrl);
        
        this.currentWebSocket.onopen = () => {
            this.isConnected = true;
        };
        
        this.currentWebSocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
        
        this.currentWebSocket.onclose = () => {
            this.isConnected = false;
        };
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'bot_response_start':
                this.hideTypingIndicator();
                this.currentBotResponse = this.addMessage('assistant', '', true);
                break;
            case 'bot_response_chunk':
                if (this.currentBotResponse) {
                    const contentDiv = this.currentBotResponse.querySelector('.message-content');
                    contentDiv.textContent += data.content;
                    this.scrollToBottom();
                }
                break;
            case 'bot_response_end':
                this.currentBotResponse = null;
                this.enableInput();
                break;
            case 'error':
                this.hideTypingIndicator();
                this.showError(data.content);
                this.enableInput();
                break;
        }
    }
    
    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message || !this.currentConversationId || !this.isConnected) return;
        
        this.addMessage('user', message, true);
        this.messageInput.value = '';
        this.disableInput();
        this.showTypingIndicator();
        
        this.currentWebSocket.send(JSON.stringify({
            message: message,
            bot_name: this.botSelect.value
        }));
    }
    
    showTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message assistant';
        typingDiv.id = 'typing-indicator';
        typingDiv.innerHTML = `
            <div class="message-avatar"><i class="fas fa-robot"></i></div>
            <div class="typing-indicator">
                <span>Thinking</span>
                <div class="typing-dots">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `;
        this.messagesContainer.appendChild(typingDiv);
        this.scrollToBottom();
    }
    
    hideTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) indicator.remove();
    }
    
    disableInput() {
        this.messageInput.disabled = true;
        this.sendBtn.disabled = true;
    }
    
    enableInput() {
        this.messageInput.disabled = false;
        this.sendBtn.disabled = false;
        this.messageInput.focus();
    }
    
    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
    
    showModal() {
        this.newChatModal.style.display = 'block';
    }
    
    hideModal() {
        this.newChatModal.style.display = 'none';
        this.newChatForm.reset();
    }
    
    async createConversation(e) {
        e.preventDefault();
        const formData = new FormData(this.newChatForm);
        
        try {
            const response = await fetch('/api/conversation/new', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            
            if (response.ok) {
                this.hideModal();
                await this.loadConversations();
                this.selectConversation(result.conversation_id);
            }
        } catch (error) {
            console.error('Error creating conversation:', error);
        }
    }
    
    async deleteConversation(conversationId) {
        if (!confirm('Delete this conversation?')) return;
        
        try {
            await fetch(`/api/conversation/${conversationId}`, { method: 'DELETE' });
            await this.loadConversations();
            
            if (this.currentConversationId === conversationId) {
                this.clearCurrentChat();
            }
        } catch (error) {
            console.error('Error deleting conversation:', error);
        }
    }
    
    clearCurrentChat() {
        this.currentConversationId = null;
        this.currentChatTitle.textContent = 'Select or create a conversation';
        this.currentBotName.textContent = 'No bot selected';
        this.messagesContainer.innerHTML = `
            <div class="welcome-message">
                <i class="fas fa-robot fa-3x"></i>
                <h3>Welcome to PyPoe Chat!</h3>
                <p>Select a conversation from the sidebar or create a new one.</p>
            </div>
        `;
        this.messageInput.disabled = true;
        this.sendBtn.disabled = true;
        if (this.currentWebSocket) this.currentWebSocket.close();
    }
    
    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.style.cssText = `
            position: fixed; top: 20px; right: 20px; background: #e74c3c;
            color: white; padding: 12px 20px; border-radius: 6px; z-index: 1000;
        `;
        errorDiv.textContent = message;
        document.body.appendChild(errorDiv);
        setTimeout(() => errorDiv.remove(), 3000);
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

document.addEventListener('DOMContentLoaded', () => new PyPoeChat()); 