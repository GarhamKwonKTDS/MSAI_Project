// admin_frontend/admin.js
class AdminApp {
    constructor() {
        this.apiBaseUrl = AdminConfig.api.getBaseUrl();
        this.currentView = "analytics";
        this.init();
    }

    async init() {
        console.log("Admin Dashboard initializing...");
        console.log("API Base URL:", this.apiBaseUrl);

        // Setup navigation
        document.querySelectorAll(".nav-item").forEach((item) => {
            item.addEventListener("click", (e) => {
                const view = e.currentTarget.dataset.view;
                this.switchView(view);
            });
        });

        // Check connection
        await this.checkHealth();

        // Load initial data
        await this.loadAnalytics();
    }

    async checkHealth() {
        try {
            const response = await fetch(
                `${this.apiBaseUrl}${AdminConfig.api.endpoints.health}`
            );
            const data = await response.json();
            console.log("Health check:", data);
        } catch (error) {
            console.error("Health check failed:", error);
        }
    }

    switchView(view) {
        // Update navigation
        document.querySelectorAll(".nav-item").forEach((item) => {
            item.classList.remove("active");
        });
        document.querySelector(`[data-view="${view}"]`).classList.add("active");

        // Update content
        document.querySelectorAll(".view").forEach((v) => {
            v.classList.remove("active");
        });
        document.getElementById(`${view}-view`).classList.add("active");

        this.currentView = view;

        // Load view data
        if (view === "analytics") {
            this.loadAnalytics();
        } else if (view === "knowledge") {
            this.loadCases();
        }
    }

    async loadAnalytics() {
        try {
            // Load summary
            const summaryResponse = await fetch(
                `${this.apiBaseUrl}${AdminConfig.api.endpoints.analytics.summary}`
            );
            const summary = await summaryResponse.json();

            document.getElementById("total-sessions").textContent =
                summary.total_sessions;
            document.getElementById("success-rate").textContent = `${(
                summary.success_rate * 100
            ).toFixed(1)}%`;
            document.getElementById(
                "avg-response-time"
            ).textContent = `${summary.avg_response_time}s`;
            document.getElementById("total-escalations").textContent =
                summary.total_escalations;

            // Load issues breakdown
            const issuesResponse = await fetch(
                `${this.apiBaseUrl}${AdminConfig.api.endpoints.analytics.issues}`
            );
            const issues = await issuesResponse.json();

            // Simple display of issues
            const chartDiv = document.getElementById("issue-chart");
            chartDiv.innerHTML = "";
            issues.issues.forEach((issue) => {
                const div = document.createElement("div");
                div.textContent = `${issue.issue_type}: ${issue.count} (${(
                    issue.percentage * 100
                ).toFixed(1)}%)`;
                chartDiv.appendChild(div);
            });
        } catch (error) {
            console.error("Failed to load analytics:", error);
        }
    }

    async loadCases() {
        try {
            const response = await fetch(
                `${this.apiBaseUrl}${AdminConfig.api.endpoints.knowledge.cases}`
            );
            const data = await response.json();

            const tbody = document.getElementById("cases-tbody");
            tbody.innerHTML = data.cases
                .map(
                    (item) => `
                <tr>
                    <td>${item.id}</td>
                    <td>${item.issue_type}</td>
                    <td>${item.case_name}</td>
                    <td>${item.description?.substring(0, 50)}...</td>
                    <td>
                        <button onclick="adminApp.editCase('${
                            item.id
                        }')">Edit</button>
                        <button onclick="adminApp.deleteCase('${
                            item.id
                        }')">Delete</button>
                    </td>
                </tr>
            `
                )
                .join("");
        } catch (error) {
            console.error("Failed to load cases:", error);
        }
    }

    refreshCases() {
        this.loadCases();
    }

    showCreateCase() {
        alert("Create case functionality coming soon!");
    }

    editCase(id) {
        alert(`Edit case ${id} functionality coming soon!`);
    }

    async deleteCase(id) {
        if (confirm(`Delete case ${id}?`)) {
            alert(`Delete functionality coming soon!`);
        }
    }

    closeModal() {
        document.getElementById("case-modal").style.display = "none";
    }
}

// Initialize app when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
    window.adminApp = new AdminApp();
});
