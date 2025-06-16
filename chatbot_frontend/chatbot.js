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
            "processingStatus",
            "statusText",
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
        this.setProcessing(true);

        try {
            // Reset stream response
            this.state.currentStreamResponse = null;
            this.state.currentStreamMetadata = null;

            // Call streaming API
            await this.callChatStreamAPI(message);

            // Wait for final response
            let waitTime = 0;
            while (!this.state.currentStreamResponse && waitTime < 30000) {
                await this.delay(100);
                waitTime += 100;
            }

            if (this.state.currentStreamResponse) {
                this.addMessage("bot", this.state.currentStreamResponse);

                // Show RAG info if enabled and used
                if (
                    this.config.features.ragInfo &&
                    this.state.currentStreamMetadata?.rag_used
                ) {
                    this.log("RAG was used for this response");
                }

                // Store in history
                this.state.messageHistory.push({
                    user: message,
                    bot: this.state.currentStreamResponse,
                    timestamp: new Date().toISOString(),
                    ragUsed:
                        this.state.currentStreamMetadata?.rag_used || false,
                    metadata: this.state.currentStreamMetadata,
                });
            } else {
                throw new Error("Timeout waiting for response");
            }
        } catch (error) {
            this.log("Chat API error", error);
            this.addMessage("bot", this.config.ui.messages.generalError);
        } finally {
            this.showTyping(false);
            this.setProcessing(false);
            if (this.elements.processingStatus) {
                this.elements.processingStatus.classList.remove("show");
                this.elements.processingStatus.style.display = "none";
            }
            if (this.elements.typingIndicator) {
                this.elements.typingIndicator.classList.remove("show");
            }
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

    async callChatStreamAPI(message) {
        try {
            this.log(`Calling streaming chat API`);
            this.log("Endpoints: ", this.config.api.endpoints);

            const response = await fetch(
                `${this.apiBaseUrl}${this.config.api.endpoints.stream}`,
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
                throw new Error(
                    `HTTP ${response.status}: ${response.statusText}`
                );
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            this.handleStreamEvent(data);
                        } catch (e) {
                            this.log("Failed to parse SSE data", e);
                        }
                    }
                }
            }
        } catch (error) {
            this.log("Stream API error", error);
            throw error;
        }
    }

    handleStreamEvent(data) {
        this.log("Stream event received", data);

        if (data.status === "started") {
            // Already showing typing indicator
        } else if (data.node && data.status === "processing") {
            // Hide typing dots completely
            if (this.elements.typingIndicator) {
                this.elements.typingIndicator.classList.remove("show");
            }
            // Show status with node info
            this.updateTypingIndicator(data.node);
        } else if (data.response) {
            // Final response received
            this.state.currentStreamResponse = data.response;
            this.state.currentStreamMetadata = data.metadata;
        } else if (data.error) {
            // Handle error
            this.log("Stream error", data.error);
            this.state.currentStreamResponse =
                this.config.ui.messages.generalError;
        }
    }

    updateTypingIndicator(nodeName) {
        console.log("🔵 updateTypingIndicator called with:", nodeName);
        console.log(
            "🔵 processingStatus element:",
            this.elements.processingStatus
        );
        console.log("🔵 statusText element:", this.elements.statusText);

        const nodeMessages = {
            state_analyzer: "상태 분석 중...",
            issue_classification: "문제 분류 중...",
            case_narrowing: "구체적인 케이스 확인 중...",
            reply_formulation: "응답 작성 중...",
            default: "응답을 기다리는 중...",
        };

        // Default message if nodeName is not recognized
        if (!nodeName || !nodeMessages[nodeName]) {
            nodeName = "default";
        }
        console.log("🔵 Node name:", nodeName);

        const message = nodeMessages[nodeName];
        console.log("🔵 Message to display:", message);

        if (
            this.elements.processingStatus &&
            this.elements.statusText &&
            message
        ) {
            console.log("🔵 Showing processing status");
            // Show the processing status
            this.elements.processingStatus.classList.add("show");
            this.elements.processingStatus.style.display = "flex"; // Force display
            this.elements.statusText.textContent = message;
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
