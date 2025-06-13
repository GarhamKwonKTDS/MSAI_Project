// Configuration for OSS Chatbot Frontend

const ChatbotConfig = {
    // API Configuration
    api: {
        // Auto-detect API URL based on environment
        getBaseUrl: function () {
            // For development, you can override this
            const hostname = window.location.hostname;
            const port = window.location.port;
            const protocol = window.location.protocol;

            // Development environments
            if (hostname === "localhost" || hostname === "127.0.0.1") {
                // Flask typically runs on 5000, but check your backend port
                return `${protocol}//${hostname}:8080`;
            }

            // Production on Azure or custom domain
            // Assumes frontend and backend are on same domain
            return `${protocol}//${hostname}${port ? ":" + port : ""}`;
        },

        // Endpoints
        endpoints: {
            health: "/health",
            chat: "/chat",
        },

        // Request configuration
        timeout: 30000, // 30 seconds
        maxRetries: 3,
        retryDelay: 1000,
    },

    // UI Configuration
    ui: {
        // Messages
        messages: {
            welcome: `안녕하세요! OSS VoC 지원 챗봇입니다. 🤖

다음과 같은 문제를 도와드릴 수 있습니다:
• OSS/NEOSS 로그인 문제
• 계정 권한 신청
• 비밀번호 관련 이슈
• 사용자 정보 동기화

무엇을 도와드릴까요?`,

            connectionError:
                "서버에 연결할 수 없습니다. 페이지를 새로고침해주세요.",
            generalError:
                "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            processing: "응답을 기다리는 중...",
        },

        // Input limits
        maxMessageLength: 1000,

        // Animation settings
        animationDuration: 300,
        typingDelay: 100,
    },

    // Session configuration
    session: {
        generateId: function () {
            return (
                "session_" +
                Date.now() +
                "_" +
                Math.random().toString(36).substr(2, 9)
            );
        },
    },

    // Debug mode (set to false in production)
    debug: true,

    // Feature flags
    features: {
        ragInfo: true, // Show when RAG is used
        connectionStatus: true,
        retryOnError: true,
        autoResize: true,
    },
};
