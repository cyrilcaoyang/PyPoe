class PyPoeApp {
    constructor() {
        this.currentConversationId = null;
        this.websocket = null;
        this.conversations = [];
        this.stats = {};
        this.currentConversation = null;
        
        this.initializeElements();
        this.bindEvents();
        this.loadInitialData();
        
        // Initialize mode description
        this.updateChatMode();
    }
    
    initializeElements() {
        // Chat elements
        this.conversationsList = document.getElementById('conversations-list');
        this.messagesContainer = document.getElementById('messages-container');
        this.messageInput = document.getElementById('message-input');
        this.sendBtn = document.getElementById('send-btn');
        this.currentChatTitle = document.getElementById('current-chat-title');
        this.currentBotName = document.getElementById('current-bot-name');
        this.newChatBtn = document.getElementById('new-chat-btn');
        
        // Global header elements
        this.globalChatMode = document.getElementById('global-chat-mode');
        this.globalBotSelect = document.getElementById('global-bot-select');
        
        // Sidebar elements
        this.searchInput = document.getElementById('search-input');
        this.botFilter = document.getElementById('bot-filter');
        this.totalConversationsEl = document.getElementById('total-conversations');
        this.totalMessagesEl = document.getElementById('total-messages');
        
        // Modal elements
        this.newChatModal = document.getElementById('new-chat-modal');
    }
    
    bindEvents() {
        // Chat functionality
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        this.newChatBtn.addEventListener('click', () => this.showNewChatModal());
        
        // Welcome page new chat button
        const welcomeNewChatBtn = document.getElementById('welcome-new-chat-btn');
        if (welcomeNewChatBtn) {
            welcomeNewChatBtn.addEventListener('click', () => this.showNewChatModal());
        }
        
        // Sidebar functionality
        this.searchInput.addEventListener('input', () => this.debounceSearch());
        this.botFilter.addEventListener('change', () => this.filterConversations());
        
        // Global header functionality
        if (this.globalChatMode) {
            this.globalChatMode.addEventListener('change', () => {
                this.updateChatMode();
                this.updateLockingLogic();
            });
        }
        
        if (this.globalBotSelect) {
            this.globalBotSelect.addEventListener('change', () => {
                this.updateSelectedBot();
                this.updateLockingLogic();
            });
        }
        
        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => this.autoResizeTextarea());
        
        // Global keyboard shortcuts for chat navigation
        document.addEventListener('keydown', (e) => {
            // Only handle when not typing in input
            if (document.activeElement !== this.messageInput && document.activeElement !== this.searchInput) {
                if (e.key === 'Home') {
                    e.preventDefault();
                    this.scrollChatToTop();
                } else if (e.key === 'End') {
                    e.preventDefault();
                    this.scrollToBottom();
                }
            }
        });
    }
    
    async loadInitialData() {
        try {
            // Load conversations for sidebar
            const response = await fetch('/api/conversations');
            this.conversations = await response.json();
            this.renderConversationsSidebar();
            
            // Load stats for sidebar
            await this.loadStats();
            this.populateBotFilter();
            
            // Update locking logic for initial state
            this.updateLockingLogic();
        } catch (error) {
            console.error('Error loading initial data:', error);
        }
    }
    
    async loadStats() {
        try {
            const response = await fetch('/api/stats');
            this.stats = await response.json();
            this.updateStats();
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }

    updateStats() {
        if (this.totalConversationsEl) {
            this.totalConversationsEl.textContent = this.stats.total_conversations || 0;
        }
        if (this.totalMessagesEl) {
            this.totalMessagesEl.textContent = this.stats.total_messages || 0;
        }
    }
    
    renderConversationsSidebar() {
        if (!this.conversationsList) return;
        
        if (this.conversations.length === 0) {
            this.conversationsList.innerHTML = `
                <div class="empty-conversations">
                    <p>No conversations yet</p>
                    <p>Click "New Chat" to start</p>
                </div>
            `;
            return;
        }
        
        this.conversationsList.innerHTML = this.conversations.map(conv => `
            <div class="conversation-item" data-id="${conv.id}">
                <div class="conversation-info">
                    <h4>${this.escapeHtml(conv.title)}</h4>
                    <p><i class="fas fa-robot"></i> ${this.escapeHtml(conv.bot_name)}</p>
                    <small>${conv.created_at}</small>
                </div>
                <button class="delete-btn" data-id="${conv.id}">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `).join('');
        
        // Bind conversation events
        this.bindConversationEvents();
    }
    
    async selectConversation(conversationId) {
        this.currentConversationId = conversationId;
        
        // Update active conversation in sidebar
        this.conversationsList.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.toggle('active', item.dataset.id === conversationId);
        });
        
        // Load conversation details
        const conv = this.conversations.find(c => c.id === conversationId);
        if (conv) {
            this.currentConversation = conv;
            this.currentChatTitle.textContent = conv.title;
            this.currentBotName.textContent = `Bot: ${conv.bot_name} | Mode: ${conv.chat_mode || 'chatbot'}`;
            if (this.globalBotSelect) {
                this.globalBotSelect.value = conv.bot_name;
            }
            if (this.globalChatMode && conv.chat_mode) {
                this.globalChatMode.value = conv.chat_mode;
            }
        }
        
        // Update locking logic based on new state
        this.updateLockingLogic();
        
        // Load messages
        await this.loadConversationMessages(conversationId);
        
        // Enable input
        this.messageInput.disabled = false;
        this.sendBtn.disabled = false;
        this.messageInput.placeholder = 'Type your message here...';
        
        // Setup websocket
        this.setupWebSocket(conversationId);
    }
    
    async loadConversationMessages(conversationId) {
        try {
            const response = await fetch(`/api/conversation/${conversationId}/messages`);
            const messages = await response.json();
            
            this.messagesContainer.innerHTML = '';
            
            // Add messages without individual scrolling
            messages.forEach(msg => {
                this.addMessageToDOM(msg.content, msg.role, false, {
                    bot_name: msg.bot_name,
                    timestamp: msg.timestamp
                });
            });
            
            // Scroll to bottom once after all messages are loaded
            requestAnimationFrame(() => {
                this.scrollToBottom();
            });
        } catch (error) {
            console.error('Error loading messages:', error);
        }
    }
    
    setupWebSocket(conversationId) {
        if (this.websocket) {
            this.websocket.close();
        }
        
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/chat/${conversationId}`;
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
        
        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'user_message':
                this.addMessage(data.content, 'user', false);
                break;
            case 'bot_response_start':
                this.currentBotMessage = this.addMessage('', 'assistant', true);
                break;
            case 'bot_response_chunk':
                if (this.currentBotMessage) {
                    this.currentBotMessage.querySelector('.message-content').textContent += data.content;
                    this.scrollToBottom();
                }
                break;
            case 'bot_response_end':
                this.currentBotMessage = null;
                this.messageInput.disabled = false;
                this.sendBtn.disabled = false;
                break;
            case 'error':
                this.addMessage(data.content, 'error', false);
                break;
        }
    }
    
    addMessageToDOM(content, role, streaming = false, metadata = {}) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';
        
        const contentWrapper = document.createElement('div');
        contentWrapper.className = 'message-wrapper';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = content;
        
        if (streaming) {
            const typingIndicator = document.createElement('div');
            typingIndicator.className = 'typing-indicator';
            typingIndicator.innerHTML = `
                <span>Thinking</span>
                <div class="typing-dots">
                    <span></span><span></span><span></span>
                </div>
            `;
            contentDiv.appendChild(typingIndicator);
        }
        
        contentWrapper.appendChild(contentDiv);
        
        // Add metadata for assistant messages
        if (role === 'assistant' && (metadata.bot_name || metadata.timestamp)) {
            const metadataDiv = document.createElement('div');
            metadataDiv.className = 'message-metadata';
            
            const parts = [];
            if (metadata.bot_name) {
                parts.push(`<span class="bot-name"><i class="fas fa-robot"></i> ${this.escapeHtml(metadata.bot_name)}</span>`);
            }
            if (metadata.timestamp) {
                const timeStr = this.formatTime(metadata.timestamp);
                parts.push(`<span class="timestamp">${timeStr}</span>`);
            }
            
            metadataDiv.innerHTML = parts.join(' • ');
            contentWrapper.appendChild(metadataDiv);
        }
        
        // Add timestamp for user messages
        if (role === 'user' && metadata.timestamp) {
            const metadataDiv = document.createElement('div');
            metadataDiv.className = 'message-metadata user-metadata';
            metadataDiv.innerHTML = `<span class="timestamp">${this.formatTime(metadata.timestamp)}</span>`;
            contentWrapper.appendChild(metadataDiv);
        }
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(contentWrapper);
        
        this.messagesContainer.appendChild(messageDiv);
        
        // Force layout recalculation and scroll after DOM update
        if (!streaming) {
            requestAnimationFrame(() => {
                this.scrollToBottom();
            });
        }
        
        return messageDiv;
    }

    // Backward compatibility method
    addMessage(content, role, streaming = false) {
        return this.addMessageToDOM(content, role, streaming, {
            bot_name: role === 'assistant' ? (this.currentConversation?.bot_name || this.globalBotSelect?.value) : null,
            timestamp: new Date().toISOString()
        });
    }

    formatTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }
    
    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message || !this.currentConversationId) return;
        
        this.messageInput.value = '';
        this.messageInput.disabled = true;
        this.sendBtn.disabled = true;
        
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({
                message: message,
                bot_name: this.globalBotSelect ? this.globalBotSelect.value : 'GPT-3.5-Turbo'
            }));
        }
        
        this.autoResizeTextarea();
    }

    lockBotSelector(lock = true, reason = '') {
        if (this.globalBotSelect) {
            this.globalBotSelect.disabled = lock;
            
            // Update label to show lock status
            const botLabel = document.querySelector('.bot-controls label');
            
            // Add visual styling
            if (lock) {
                this.globalBotSelect.classList.add('locked');
                this.globalBotSelect.title = reason || 'Bot selection is locked';
                if (botLabel) {
                    botLabel.innerHTML = 'Bot: <i class="fas fa-lock" style="color: #e74c3c; margin-left: 4px;" title="' + (reason || 'Locked') + '"></i>';
                }
            } else {
                this.globalBotSelect.classList.remove('locked');
                this.globalBotSelect.title = 'Select AI bot';
                if (botLabel) {
                    botLabel.textContent = 'Bot:';
                }
            }
        }
    }

    lockChatMode(lock = true, reason = '') {
        if (this.globalChatMode) {
            this.globalChatMode.disabled = lock;
            
            // Update label to show lock status
            const modeLabel = document.querySelector('.mode-controls label');
            
            // Add visual styling
            if (lock) {
                this.globalChatMode.classList.add('locked');
                this.globalChatMode.title = reason || 'Chat mode selection is locked';
                if (modeLabel) {
                    modeLabel.innerHTML = 'Mode: <i class="fas fa-lock" style="color: #e74c3c; margin-left: 4px;" title="' + (reason || 'Locked') + '"></i>';
                }
            } else {
                this.globalChatMode.classList.remove('locked');
                this.globalChatMode.title = 'Select chat mode';
                if (modeLabel) {
                    modeLabel.textContent = 'Mode:';
                }
            }
        }
    }

    updateLockingLogic() {
        const chatMode = this.globalChatMode ? this.globalChatMode.value : 'chatbot';
        
        // Chat mode locking: lock when no conversation is selected
        if (!this.currentConversationId) {
            this.lockChatMode(true, 'Select a conversation first');
        } else {
            this.lockChatMode(false);
        }
        
        // Bot locking logic based on frontend rules
        if (!this.currentConversationId) {
            // No conversation selected
            this.lockBotSelector(true, 'Select a conversation first');
        } else if (chatMode === 'chatbot' && this.currentConversation) {
            // Chatbot mode with active conversation
            this.lockBotSelector(true, 'Bot locked in single chat mode');
        } else {
            // Other modes or no active conversation
            this.lockBotSelector(false);
        }
    }

    populateBotFilter() {
        if (!this.botFilter) return;
        
        const bots = [...new Set(this.conversations.map(c => c.bot_name).filter(Boolean))];
        
        this.botFilter.innerHTML = '<option value="">All Bots</option>';
        bots.forEach(bot => {
            const option = document.createElement('option');
            option.value = bot;
            option.textContent = bot;
            this.botFilter.appendChild(option);
        });
    }

    debounceSearch() {
        clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(() => this.filterConversations(), 300);
    }

    filterConversations() {
        const query = this.searchInput?.value.toLowerCase().trim() || '';
        const botFilter = this.botFilter?.value || '';
        
        let filtered = this.conversations;
        
        if (botFilter) {
            filtered = filtered.filter(conv => conv.bot_name === botFilter);
        }
        
        if (query) {
            filtered = filtered.filter(conv => 
                conv.title.toLowerCase().includes(query) ||
                conv.bot_name.toLowerCase().includes(query)
            );
        }
        
        this.renderFilteredConversations(filtered);
    }

    renderFilteredConversations(filteredConversations) {
        if (!this.conversationsList) return;
        
        if (filteredConversations.length === 0) {
            this.conversationsList.innerHTML = `
                <div class="empty-conversations">
                    <p>No conversations found</p>
                    <p>Try adjusting your search</p>
                </div>
            `;
            return;
        }
        
        this.conversationsList.innerHTML = filteredConversations.map(conv => `
            <div class="conversation-item" data-id="${conv.id}">
                <div class="conversation-info">
                    <h4>${this.escapeHtml(conv.title)}</h4>
                    <p><i class="fas fa-robot"></i> ${this.escapeHtml(conv.bot_name)}</p>
                    <small>${conv.created_at}</small>
                </div>
                <button class="delete-btn" data-id="${conv.id}">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `).join('');
        
        // Re-bind events for filtered conversations
        this.bindConversationEvents();
    }

    bindConversationEvents() {
        // Bind conversation selection events
        this.conversationsList.querySelectorAll('.conversation-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (!e.target.closest('.delete-btn')) {
                    this.selectConversation(item.dataset.id);
                }
            });
        });
        
        // Bind delete events
        this.conversationsList.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteConversation(btn.dataset.id);
            });
        });
    }

    async deleteConversation(conversationId) {
        if (!confirm('Are you sure you want to delete this conversation?')) return;
        
        try {
            const response = await fetch(`/api/conversation/${conversationId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                // Remove from arrays
                this.conversations = this.conversations.filter(c => c.id !== conversationId);
                
                // Re-render
                this.renderConversationsSidebar();
                this.populateBotFilter();
                await this.loadStats();
                
                // Clear chat if this was the active conversation
                if (this.currentConversationId === conversationId) {
                    this.currentConversationId = null;
                    this.currentConversation = null;
                    this.messagesContainer.innerHTML = `
                        <div class="welcome-message">
                            <i class="fas fa-robot fa-3x"></i>
                            <h3>Welcome to PyPoe Chat!</h3>
                            <p>Select a conversation from the sidebar or create a new one to start chatting with AI bots.</p>
                            <button id="welcome-new-chat-btn" class="btn btn-primary" style="margin-top: 20px;">
                                <i class="fas fa-plus"></i> Start New Chat
                            </button>
                        </div>
                    `;
                    this.currentChatTitle.textContent = 'Select or create a conversation';
                    this.currentBotName.textContent = 'Choose a chat mode and bot above to get started';
                    this.messageInput.disabled = true;
                    this.sendBtn.disabled = true;
                    
                    // Update locking logic for no active conversation
                    this.updateLockingLogic();
                    
                    // Re-bind welcome button event
                    const welcomeNewChatBtn = document.getElementById('welcome-new-chat-btn');
                    if (welcomeNewChatBtn) {
                        welcomeNewChatBtn.addEventListener('click', () => this.showNewChatModal());
                    }
                }
            }
        } catch (error) {
            console.error('Error deleting conversation:', error);
        }
    }
    
    updateChatMode() {
        // Update UI or behavior based on chat mode
        const selectedMode = this.globalChatMode.value;
        console.log('Chat mode changed to:', selectedMode);
        
        // Update mode description
        const modeDescription = document.getElementById('mode-description');
        if (modeDescription) {
            const descriptions = {
                'chatbot': 'Single AI assistant',
                'group': 'Multiple AI assistants',
                'debate': 'Two AIs debate a topic'
            };
            modeDescription.textContent = descriptions[selectedMode] || 'Unknown mode';
        }
        
        // Update current bot name display to reflect the selected mode
        if (!this.currentConversationId) {
            this.currentBotName.textContent = `Mode: ${this.globalChatMode.options[this.globalChatMode.selectedIndex].text}`;
        }
    }
    
    updateSelectedBot() {
        // Update current bot name display
        const selectedBot = this.globalBotSelect.value;
        console.log('Bot changed to:', selectedBot);
        
        if (!this.currentConversationId) {
            this.currentBotName.textContent = `Bot: ${selectedBot}`;
        }
    }
    
    showNewChatModal() {
        // Pre-fill modal with current global selections
        const chatModeSelect = document.getElementById('chat-mode');
        const chatBotSelect = document.getElementById('chat-bot');
        
        if (chatModeSelect && this.globalChatMode) {
            chatModeSelect.value = this.globalChatMode.value;
        }
        
        if (chatBotSelect && this.globalBotSelect) {
            chatBotSelect.value = this.globalBotSelect.value;
        }
        
        this.newChatModal.style.display = 'block';
    }
    
    autoResizeTextarea() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 120) + 'px';
    }
    
    scrollToBottom(containerId = null) {
        const container = containerId ? document.getElementById(containerId) : this.messagesContainer;
        if (container) {
            container.scrollTo({
                top: container.scrollHeight,
                behavior: 'smooth'
            });
        }
    }
    
    scrollToTop(containerId) {
        const container = document.getElementById(containerId);
        if (container) {
            container.scrollTop = 0;
        }
    }
    
    scrollChatToTop() {
        if (this.messagesContainer) {
            this.messagesContainer.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new PyPoeApp();
    
    // Handle new chat modal (keeping existing functionality)
    const newChatModal = document.getElementById('new-chat-modal');
    const newChatForm = document.getElementById('new-chat-form');
    const closeModalBtns = document.querySelectorAll('.close, #cancel-btn');
    
    closeModalBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            newChatModal.style.display = 'none';
        });
    });
    
    if (newChatForm) {
        newChatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            
            // Convert FormData to JSON for better handling
            const data = {
                title: formData.get('title'),
                bot_name: formData.get('bot_name'),
                chat_mode: formData.get('chat_mode') || 'chatbot'
            };
            
            try {
                const response = await fetch('/api/conversation/new', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                if (result.conversation_id) {
                    newChatModal.style.display = 'none';
                    newChatForm.reset();
                    
                    // Reload conversations and select the new one
                    await app.loadInitialData();
                    app.selectConversation(result.conversation_id);
                }
            } catch (error) {
                console.error('Error creating conversation:', error);
            }
        });
    }
    
    // Close modals when clicking outside
    window.addEventListener('click', (e) => {
        if (e.target === newChatModal) {
            newChatModal.style.display = 'none';
        }
    });
}); 