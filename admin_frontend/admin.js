// admin_frontend/admin.js
class AdminApp {
    constructor() {
        this.apiBaseUrl = AdminConfig.api.getBaseUrl();
        this.currentView = "analytics";
        this.currentCaseId = null;
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

        // Setup FAB button
        const addBtn = document.getElementById("addCaseBtn");
        if (addBtn) {
            addBtn.addEventListener("click", () => this.openCaseEditor());
        }
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
            // First, run analytics to get fresh data
            await fetch(`${this.apiBaseUrl}/analytics`, { method: "POST" });

            // Load summary
            const summaryResponse = await fetch(
                `${this.apiBaseUrl}${AdminConfig.api.endpoints.analytics.summary}`
            );
            const summary = await summaryResponse.json();

            // Check if we have metrics data
            if (summary.message === "No analytics data available yet") {
                this.showNoDataMessage();
                return;
            }

            // Get the actual metrics from the latest analytics run
            const metrics = summary.metrics || {};
            const volume = metrics.volume || {};
            const performance = metrics.performance || {};
            const breakdown = performance.breakdown || {};

            // Volume Metrics
            document.getElementById("total-sessions").textContent =
                volume.unique_sessions || 0;
            document.getElementById("total-conversations").textContent =
                volume.total_conversations || 0;
            document.getElementById("total-messages").textContent =
                volume.total_messages || 0;

            // Performance Metrics
            document.getElementById("success-rate").textContent = `${(
                performance.success_rate || 0
            ).toFixed(1)}%`;
            document.getElementById("avg-response-time").textContent = `${(
                performance.avg_resolution_time_minutes || 0
            ).toFixed(1)}m`;
            document.getElementById(
                "avg-conversation-length"
            ).textContent = `${(
                performance.avg_conversation_length || 0
            ).toFixed(1)} turns`;

            // Breakdown
            document.getElementById("solved-count").textContent =
                breakdown.solved || 0;
            document.getElementById("escalated-count").textContent =
                breakdown.escalated || 0;
            document.getElementById("abandoned-count").textContent =
                breakdown.abandoned || 0;
            document.getElementById("interrupted-count").textContent =
                breakdown.interrupted || 0;

            // Issue Distribution
            this.displayDistribution(
                "issue-distribution",
                metrics.issue_distribution || {}
            );

            // Case Distribution
            this.displayDistribution(
                "case-distribution",
                metrics.case_distribution || {}
            );

            // Unidentified Conversations
            this.displayUnidentified(metrics.unidentified || {});
        } catch (error) {
            console.error("Failed to load analytics:", error);
            this.showErrorMessage();
        }
    }

    displayDistribution(elementId, distribution) {
        const container = document.getElementById(elementId);
        container.innerHTML = "";

        const entries = Object.entries(distribution);
        if (entries.length === 0) {
            container.innerHTML =
                '<p style="text-align: center; color: #95a5a6;">No data available</p>';
            return;
        }

        // Calculate total for percentages
        const total = entries.reduce((sum, [_, count]) => sum + count, 0);

        // Sort by count descending
        entries.sort((a, b) => b[1] - a[1]);

        entries.forEach(([type, count]) => {
            const percentage = total > 0 ? (count / total) * 100 : 0;

            const item = document.createElement("div");
            item.className = "distribution-item";
            item.innerHTML = `
                <span class="distribution-label">${type}</span>
                <div class="distribution-count">
                    <div class="distribution-bar">
                        <div class="distribution-fill" style="width: ${percentage}%"></div>
                    </div>
                    <span>${count} (${percentage.toFixed(1)}%)</span>
                </div>
            `;
            container.appendChild(item);
        });
    }

    displayUnidentified(unidentified) {
        const container = document.getElementById("unidentified-info");
        const count = unidentified.count || 0;
        const ids = unidentified.conversation_ids || [];

        container.innerHTML = `
            <p><strong>${count}</strong> conversations could not be classified.</p>
            ${
                count > 0
                    ? '<div class="unidentified-list">' +
                      ids
                          .map(
                              (id) =>
                                  `<div class="unidentified-item">${id}</div>`
                          )
                          .join("") +
                      "</div>"
                    : ""
            }
        `;
    }

    showNoDataMessage() {
        const mainContent = document.querySelector(".main-content");
        const analyticsView = document.getElementById("analytics-view");
        analyticsView.innerHTML = `
            <h1>Analytics Dashboard</h1>
            <div style="text-align: center; padding: 50px;">
                <h2>No Analytics Data Available</h2>
                <p>Analytics will be available once conversations have been processed.</p>
                <button class="btn btn-primary" onclick="adminApp.runAnalytics()">Run Analytics Now</button>
            </div>
        `;
    }

    showErrorMessage() {
        const analyticsView = document.getElementById("analytics-view");
        analyticsView.innerHTML = `
            <h1>Analytics Dashboard</h1>
            <div style="text-align: center; padding: 50px; color: #e74c3c;">
                <h2>Error Loading Analytics</h2>
                <p>Failed to load analytics data. Please try again.</p>
                <button class="btn btn-primary" onclick="adminApp.loadAnalytics()">Retry</button>
            </div>
        `;
    }

    async runAnalytics() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/analytics`, {
                method: "POST",
            });
            if (response.ok) {
                alert("Analytics processing started. Refreshing data...");
                setTimeout(() => this.loadAnalytics(), 2000);
            }
        } catch (error) {
            console.error("Failed to run analytics:", error);
            alert("Failed to run analytics");
        }
    }

    async loadCases() {
        try {
            console.log(
                "Loading cases from:",
                `${this.apiBaseUrl}${AdminConfig.api.endpoints.knowledge.cases}`
            );

            const response = await fetch(
                `${this.apiBaseUrl}${AdminConfig.api.endpoints.knowledge.cases}`
            );

            console.log("Response status:", response.status);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log("Cases data:", data);
            console.log("Number of cases:", data.cases?.length || 0);

            const tbody = document.getElementById("cases-tbody");

            if (!data.cases || data.cases.length === 0) {
                tbody.innerHTML =
                    '<tr><td colspan="5" style="text-align: center;">No cases found</td></tr>';
                return;
            }

            tbody.innerHTML = data.cases
                .map(
                    (item) => `
                <tr class="clickable-row" onclick="adminApp.editCase('${
                    item.id
                }')">
                    <td>${item.id}</td>
                    <td>${item.issue_type}</td>
                    <td>${item.case_name}</td>
                    <td>${item.description?.substring(0, 50)}...</td>
                    <td onclick="event.stopPropagation()">
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
            const tbody = document.getElementById("cases-tbody");
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: red;">Error loading cases: ${error.message}</td></tr>`;
        }
    }

    // Case Editor Methods
    openCaseEditor(caseId = null) {
        this.currentCaseId = caseId;
        const overlay = document.getElementById("caseEditorOverlay");
        const title = document.getElementById("overlayTitle");

        if (caseId) {
            title.textContent = "Edit Case";
            this.loadCaseData(caseId);
        } else {
            title.textContent = "Create New Case";
            this.clearCaseForm();
        }

        overlay.style.display = "block";
    }

    closeCaseEditor() {
        document.getElementById("caseEditorOverlay").style.display = "none";
        this.currentCaseId = null;
    }

    clearCaseForm() {
        document.getElementById("issueDescription").value = "";
        document.getElementById("issueType").value = "";
        document.getElementById("issueName").value = "";
        document.getElementById("caseType").value = "";
        document.getElementById("caseName").value = "";
        document.getElementById("description").value = "";
        document.getElementById("keywords").value = "";
        document.getElementById("solutionSteps").value = "";
    }

    async loadCaseData(caseId) {
        try {
            const response = await fetch(
                `${this.apiBaseUrl}/api/knowledge/cases/${caseId}`
            );
            const case_data = await response.json();

            // Populate form with case data
            document.getElementById("issueType").value =
                case_data.issue_type || "";
            document.getElementById("issueName").value =
                case_data.issue_name || "";
            document.getElementById("caseType").value =
                case_data.case_type || "";
            document.getElementById("caseName").value =
                case_data.case_name || "";
            document.getElementById("description").value =
                case_data.description || "";
            document.getElementById("keywords").value = (
                case_data.keywords || []
            ).join(", ");
            document.getElementById("solutionSteps").value = (
                case_data.solution_steps || []
            ).join("\n");
        } catch (error) {
            console.error("Failed to load case:", error);
            alert("Failed to load case data");
        }
    }

    async generateFromDescription() {
        const description = document.getElementById("issueDescription").value;
        if (!description.trim()) {
            alert("Please describe the issue first");
            return;
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/api/admin/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: `Create a case from this description: ${description}`,
                    session_id: `admin_${Date.now()}`,
                }),
            });

            const data = await response.json();
            console.log("Admin chat response:", data);
            console.log("Case data:", data.case_data); // Debug log

            // Check if case data was generated
            if (data.case_data) {
                // Debug - log each field as we set it
                console.log("Setting issue_type:", data.case_data.issue_type);
                document.getElementById("issueType").value =
                    data.case_data.issue_type || "";

                console.log("Setting issue_name:", data.case_data.issue_name);
                document.getElementById("issueName").value =
                    data.case_data.issue_name || "";

                console.log("Setting case_type:", data.case_data.case_type);
                document.getElementById("caseType").value =
                    data.case_data.case_type || "";

                console.log("Setting case_name:", data.case_data.case_name);
                document.getElementById("caseName").value =
                    data.case_data.case_name || "";

                console.log("Setting description:", data.case_data.description);
                document.getElementById("description").value =
                    data.case_data.description || "";

                console.log("Setting keywords:", data.case_data.keywords);
                document.getElementById("keywords").value = (
                    data.case_data.keywords || []
                ).join(", ");

                console.log(
                    "Setting solution_steps:",
                    data.case_data.solution_steps
                );
                document.getElementById("solutionSteps").value = (
                    data.case_data.solution_steps || []
                ).join("\n");

                alert(
                    "Case data generated successfully! Review and edit as needed before saving."
                );
            } else {
                alert(
                    "Could not generate case data. Please try again with more details."
                );
            }
        } catch (error) {
            console.error("Failed to generate from description:", error);
            alert("Failed to generate case from description");
        }
    }

    async saveCase() {
        // Gather form data
        const caseData = {
            issue_type: document.getElementById("issueType").value,
            issue_name: document.getElementById("issueName").value,
            case_type: document.getElementById("caseType").value,
            case_name: document.getElementById("caseName").value,
            description: document.getElementById("description").value,
            keywords: document
                .getElementById("keywords")
                .value.split(",")
                .map((k) => k.trim())
                .filter((k) => k),
            solution_steps: document
                .getElementById("solutionSteps")
                .value.split("\n")
                .filter((s) => s.trim()),
        };

        // Validate required fields
        const required = ["issue_type", "issue_name", "case_type", "case_name"];
        for (const field of required) {
            if (!caseData[field]) {
                alert(`Please fill in the ${field.replace("_", " ")}`);
                return;
            }
        }

        try {
            let response;
            if (this.currentCaseId) {
                // Update existing case
                response = await fetch(
                    `${this.apiBaseUrl}/api/knowledge/cases/${this.currentCaseId}`,
                    {
                        method: "PUT",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(caseData),
                    }
                );
            } else {
                // Create new case
                caseData.id = `${caseData.issue_type}_${
                    caseData.case_type
                }_${Date.now()}`;
                response = await fetch(
                    `${this.apiBaseUrl}/api/knowledge/cases`,
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(caseData),
                    }
                );
            }

            if (response.ok) {
                alert(
                    this.currentCaseId
                        ? "Case updated successfully!"
                        : "Case created successfully!"
                );
                this.closeCaseEditor();
                this.loadCases(); // Refresh the list
            } else {
                const error = await response.json();
                alert(`Failed to save case: ${error.error || "Unknown error"}`);
            }
        } catch (error) {
            console.error("Failed to save case:", error);
            alert("Failed to save case");
        }
    }

    editCase(id) {
        this.openCaseEditor(id);
    }

    async deleteCase(id) {
        if (confirm(`Are you sure you want to delete case ${id}?`)) {
            try {
                const response = await fetch(
                    `${this.apiBaseUrl}/api/knowledge/cases/${id}`,
                    {
                        method: "DELETE",
                    }
                );

                if (response.ok) {
                    alert("Case deleted successfully!");
                    this.loadCases(); // Refresh the list
                } else {
                    const error = await response.json();
                    alert(
                        `Failed to delete case: ${
                            error.error || "Unknown error"
                        }`
                    );
                }
            } catch (error) {
                console.error("Failed to delete case:", error);
                alert("Failed to delete case");
            }
        }
    }

    showUnsolvedIssues() {
        // TODO: Implement unsolved issues selection
        alert("Feature coming soon: Select from unsolved VoC issues");
    }

    refreshCases() {
        this.loadCases();
    }

    showCreateCase() {
        this.openCaseEditor();
    }

    closeModal() {
        document.getElementById("case-modal").style.display = "none";
    }
}

// Initialize app when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
    window.adminApp = new AdminApp();
});
