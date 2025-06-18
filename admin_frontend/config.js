// admin_frontend/config.js
const AdminConfig = {
    api: {
        getBaseUrl: function () {
            const hostname = window.location.hostname;
            const protocol = window.location.protocol;

            if (hostname === "localhost" || hostname === "127.0.0.1") {
                return `${protocol}//${hostname}:8082`;
            }

            // Production - assumes backend is on same domain with different subdomain
            return `${protocol}//${hostname}`;
        },

        endpoints: {
            health: "/health",
            analytics: {
                summary: "/api/analytics/summary",
                issues: "/api/analytics/issues",
            },
            knowledge: {
                cases: "/api/knowledge/cases",
            },
        },
    },
};
