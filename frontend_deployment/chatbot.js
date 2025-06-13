// OSS Chatbot Main Application Class

class OSSChatbot {
    constructor() {
        // Initialize configuration
        this.config = ChatbotConfig;
        this.apiBaseUrl = this.config.api.getBaseUrl();
        this.sessionId = this.config.session.generateId();

        // Initialize DOM elements
        this.elements = this.initializeElements();

        // Initialize state
        this.state = {
            isProcessing: false,
            isConnected: false,
            messageHistory: [],
        };

        // Start initialization
        this.init();
    }

    initializeElements() {
        const elements = {};
        const requiredElements = [
            "chatMessages",
            "messageInput",
            "sendButton",
            "chatForm",
            "typingIndicator",
            "errorMessage",
            "connectionStatus",
            "statusIndicator",
        ];

        requiredElements.forEach((id) => {
            elements[id] = document.getElementById(id);
            if (!elements[id]) {
                console.error(`Required element not found: ${id}`);
            }
        });

        return elements;
    }

    async init() {
        this.log("Initializing OSS Chatbot...");
        this.log(`API Base URL: ${this.apiBaseUrl}`);
        this.log(`Session ID: ${this.sessionId}`);

        // Setup event listeners
        this.setupEventListeners();

        // Check connection to backend
        await this.checkConnection();

        // Add welcome message
        this.addWelcomeMessage();

        this.log("Chatbot initialized successfully");
    }

    setupEventListeners() {
        // Form submission
        if (this.elements.chatForm) {
            this.elements.chatForm.addEventListener("submit", (e) => {
                e.preventDefault();
                this.sendMessage();
            });
        }

        // Keyboard shortcuts
        if (this.elements.messageInput) {
            this.elements.messageInput.addEventListener("keydown", (e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });

            // Auto-resize textarea
            if (this.config.features.autoResize) {
                this.elements.messageInput.addEventListener("input", () => {
                    this.autoResizeTextarea();
                });
            }
        }
    }

    autoResizeTextarea() {
        const textarea = this.elements.messageInput;
        if (textarea) {
            textarea.style.height = "auto";
            textarea.style.height = Math.min(textarea.scrollHeight, 120) + "px";
        }
    }

    async checkConnection() {
        try {
            this.log("Checking connection to backend...");

            const response = await fetch(
                `${this.apiBaseUrl}${this.config.api.endpoints.health}`,
                {
                    method: "GET",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    timeout: this.config.api.timeout,
                }
            );

            if (response.ok) {
                const data = await response.json();
                this.state.isConnected = true;
                this.updateConnectionStatus("연결됨", true);
                this.log("Connection successful", data);
            } else {
                throw new Error(
                    `HTTP ${response.status}: ${response.statusText}`
                );
            }
        } catch (error) {
            this.log("Connection failed", error);
            this.state.isConnected = false;
            this.updateConnectionStatus(
                "연결 실패 - 서버를 확인해주세요",
                false
            );
        }
    }

    updateConnectionStatus(message, isConnected) {
        if (this.elements.connectionStatus) {
            this.elements.connectionStatus.textContent = message;
            this.elements.connectionStatus.style.background = isConnected
                ? "#f0f9ff"
                : "#fef2f2";
            this.elements.connectionStatus.style.color = isConnected
                ? "#0369a1"
                : "#dc2626";
        }

        if (this.elements.statusIndicator) {
            this.elements.statusIndicator.style.background = isConnected
                ? "#10B981"
                : "#ef4444";
        }
    }

    addWelcomeMessage() {
        this.addMessage("bot", this.config.ui.messages.welcome);
    }

    async sendMessage() {
        const message = this.elements.messageInput?.value.trim();

        if (!message || this.state.isProcessing) {
            return;
        }

        if (!this.state.isConnected) {
            this.showError(this.config.ui.messages.connectionError);
            return;
        }

        if (message.length > this.config.ui.maxMessageLength) {
            this.showError(
                `메시지는 ${this.config.ui.maxMessageLength}자를 초과할 수 없습니다.`
            );
            return;
        }

        // Add user message to chat
        this.addMessage("user", message);
        this.clearInput();

        // Show processing state
        this.showTyping(true);
        this.setProcessing(true);

        try {
            const response = await this.callChatAPI(message);
            this.addMessage("bot", response.response);

            // Show RAG info if enabled and used
            if (this.config.features.ragInfo && response.rag_used) {
                this.log("RAG was used for this response");
            }

            // Store in history
            this.state.messageHistory.push({
                user: message,
                bot: response.response,
                timestamp: new Date().toISOString(),
                ragUsed: response.rag_used || false,
            });
        } catch (error) {
            this.log("Chat API error", error);
            this.addMessage("bot", this.config.ui.messages.generalError);
        } finally {
            this.showTyping(false);
            this.setProcessing(false);
        }
    }

    async callChatAPI(message, retryCount = 0) {
        try {
            this.log(`Calling chat API (attempt ${retryCount + 1})`);

            const response = await fetch(
                `${this.apiBaseUrl}${this.config.api.endpoints.chat}`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        message: message,
                        session_id: this.sessionId,
                    }),
                }
            );

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(
                    errorData.error ||
                        `HTTP ${response.status}: ${response.statusText}`
                );
            }

            const data = await response.json();
            this.log("Chat API response received", data);
            return data;
        } catch (error) {
            if (
                this.config.features.retryOnError &&
                retryCount < this.config.api.maxRetries
            ) {
                this.log(
                    `Retrying chat API call (${retryCount + 1}/${
                        this.config.api.maxRetries
                    })`
                );
                await this.delay(this.config.api.retryDelay);
                return this.callChatAPI(message, retryCount + 1);
            }
            throw error;
        }
    }

    addMessage(sender, message) {
        if (!this.elements.chatMessages) return;

        const messageElement = document.createElement("div");
        messageElement.className = `message ${sender}`;

        const avatarElement = document.createElement("div");
        avatarElement.className = "message-avatar";
        avatarElement.textContent = sender === "user" ? "👤" : "🤖";

        const contentElement = document.createElement("div");
        contentElement.className = "message-content";
        contentElement.innerHTML = this.formatMessage(message);

        messageElement.appendChild(avatarElement);
        messageElement.appendChild(contentElement);

        this.elements.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }

    formatMessage(message) {
        return message
            .replace(/\n/g, "<br>")
            .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
            .replace(/\*(.*?)\*/g, "<em>$1</em>")
            .replace(/`(.*?)`/g, "<code>$1</code>");
    }

    showTyping(show) {
        if (this.elements.typingIndicator) {
            if (show) {
                this.elements.typingIndicator.classList.add("show");
            } else {
                this.elements.typingIndicator.classList.remove("show");
            }
            this.scrollToBottom();
        }
    }

    setProcessing(processing) {
        this.state.isProcessing = processing;

        if (this.elements.sendButton) {
            this.elements.sendButton.disabled = processing;
        }

        if (this.elements.messageInput) {
            this.elements.messageInput.disabled = processing;
        }
    }

    clearInput() {
        if (this.elements.messageInput) {
            this.elements.messageInput.value = "";
            this.autoResizeTextarea();
        }
    }

    showError(message) {
        if (this.elements.errorMessage) {
            this.elements.errorMessage.textContent = message;
            this.elements.errorMessage.style.display = "block";

            setTimeout(() => {
                this.elements.errorMessage.style.display = "none";
            }, 5000);
        }
    }

    scrollToBottom() {
        if (this.elements.chatMessages) {
            setTimeout(() => {
                this.elements.chatMessages.scrollTop =
                    this.elements.chatMessages.scrollHeight;
            }, 100);
        }
    }

    delay(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }

    log(message, data = null) {
        if (this.config.debug) {
            console.log(`[OSS Chatbot] ${message}`, data || "");
        }
    }

    // Public methods for external use
    getMessageHistory() {
        return this.state.messageHistory;
    }

    clearHistory() {
        this.state.messageHistory = [];
        if (this.elements.chatMessages) {
            this.elements.chatMessages.innerHTML = "";
        }
        this.addWelcomeMessage();
    }

    reconnect() {
        this.checkConnection();
    }
}
