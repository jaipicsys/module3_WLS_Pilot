import { getApiBaseUrl } from "./config";

//for the register page
export const registerUser = async (payload) => {
    try {
        const API_BASE_URL = await getApiBaseUrl();
        const res = await fetch(`${API_BASE_URL}/api/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.error || "Registration failed");
        }

        return await res.json();
    } catch (err) {
        console.error("Failed to register user:", err);
        throw err;
    }
};

export const loginUser = async (payload) => {
    try {
        const API_BASE_URL = await getApiBaseUrl();
        const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
            credentials: "include", // required if using cookies later
        });

        if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.error || "Login failed");
        }

        return await res.json(); // expects { token: '...' }
    } catch (err) {
        console.error("Failed to login user:", err);
        throw err;
    }
};

export const fetchCurrentUser = async () => {
    try {
        const API_BASE_URL = await getApiBaseUrl();

        const res = await fetch(`${API_BASE_URL}/api/auth/me`, {
            method: "GET",
            credentials: "include",  // Send HTTP-only cookies with request
        });

        if (!res.ok) {
            throw new Error("Failed to fetch user details");
        }

        return await res.json();
    } catch (err) {
        console.error("Failed to fetch user info:", err);
        throw err;
    }
};

export const logoutUser = async () => {
    try {
        const API_BASE_URL = await getApiBaseUrl();
        const res = await fetch(`${API_BASE_URL}/api/auth/logout`, {
            method: "POST",
            credentials: "include", // Send cookies with request
        });

        if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.error || "Logout failed");
        }

        return await res.json();
    } catch (err) {
        console.error("Logout failed:", err);
        throw err;
    }
};

export const fetchReports = async (filters) => {
    const API_BASE_URL = await getApiBaseUrl();

    const params = new URLSearchParams();

    Object.entries(filters).forEach(([key, value]) => {
        if (value !== "" && value !== null && value !== undefined) {
            params.append(key, value);
        }
    });

    const res = await fetch(
        `${API_BASE_URL}/api/reports?${params.toString()}`,
        {
            method: "GET",
            headers: {
                Accept: "application/pdf",
            },
        }
    );

    if (!res.ok) {
        throw new Error("Report fetch failed");
    }

    const blob = await res.blob();
    const contentType = res.headers.get("content-type") || "";

    return {
        blob,
        contentType,
    };
};

export const uploadExcelFile = async (file) => {
    const API_BASE_URL = await getApiBaseUrl();
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE_URL}/api/upload_excel`, {
        method: 'POST',
        body: formData,
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || "Upload failed");
    }

    return await res.json();
};

export const fetchHealthNotifications = async () => {
    try {
        const API_BASE_URL = await getApiBaseUrl();
        const res = await fetch(`${API_BASE_URL}/api/camera_history`);

        if (!res.ok) throw new Error("Failed to fetch health notifications");

        return await res.json(); // [{ id, message, timestamp }]
    } catch (err) {
        console.error("Error fetching health notifications:", err);
        return [];
    }
};

export const fetchCameraStatus = async () => {
    try {
        const API_BASE_URL = await getApiBaseUrl();
        const res = await fetch(`${API_BASE_URL}/api/camera_status`);

        if (!res.ok) throw new Error("Failed to fetch camera status");

        return await res.json(); // [{ camera_id, status, last_update }]
    } catch (err) {
        console.error("Error fetching camera status:", err);
        return [];
    }
};

export const fetchEmailConfig = async () => {
    try {
        const API_BASE_URL = await getApiBaseUrl();
        const res = await fetch(`${API_BASE_URL}/api/get_email_config`);
        if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.message || "Failed to fetch email config");
        }
        const data = await res.json();
        return data.email_config;
    } catch (err) {
        console.error("Error fetching email config:", err);
        throw err;
    }
};

export const updateEmailConfig = async (newConfig) => {
    try {
        const API_BASE_URL = await getApiBaseUrl();
        const res = await fetch(`${API_BASE_URL}/api/update_email_config`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(newConfig),
        });
        if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.message || "Failed to update email config");
        }
        return await res.json();
    } catch (err) {
        console.error("Error updating email config:", err);
        throw err;
    }
};

// ✅ Fetch all users
export const fetchUsers = async () => {
    const API_BASE_URL = await getApiBaseUrl();
    const res = await fetch(`${API_BASE_URL}/api/auth/users`);
    if (!res.ok) throw new Error("Failed to fetch users");
    return res.json();
};

// ✅ Add new user
export const addUser = async (user) => {
    const API_BASE_URL = await getApiBaseUrl();
    const res = await fetch(`${API_BASE_URL}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(user),
    });
    if (!res.ok) throw new Error("Failed to add user");
    return res.json();
};

// ✅ Update user role
export const updateUserRole = async (userId, role) => {
    const API_BASE_URL = await getApiBaseUrl();
    const res = await fetch(`${API_BASE_URL}/api/auth/users/${userId}/role`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role }),
    });
    if (!res.ok) throw new Error("Failed to update role");
    return res.json();
};

// ✅ Delete user
export const deleteUser = async (userId) => {
    const API_BASE_URL = await getApiBaseUrl();
    const res = await fetch(`${API_BASE_URL}/api/auth/users/${userId}`, {
        method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete user");
    return res.json();
};

export const changePassword = async (payload) => {
    try {
        const API_BASE_URL = await getApiBaseUrl();
        const res = await fetch(`${API_BASE_URL}/api/auth/change-password`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.error || "Failed to change password");
        }

        return await res.json();
    } catch (err) {
        console.error("Failed to change password:", err);
        throw err;
    }
};

// Forgot Password: request OTP
export const requestPasswordReset = async (email) => {
    try {
        const API_BASE_URL = await getApiBaseUrl();
        const res = await fetch(`${API_BASE_URL}/api/auth/forgot-password`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email }),
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to send reset link");
        return data;
    } catch (err) {
        console.error("Forgot password failed:", err);
        throw err;
    }
};

// Reset Password with OTP
export const resetPassword = async (payload) => {
    try {
        const API_BASE_URL = await getApiBaseUrl();
        const res = await fetch(`${API_BASE_URL}/api/auth/reset-password`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload), // { email, otp, newPassword, confirmPassword }
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Password reset failed");
        return data;
    } catch (err) {
        console.error("Reset password failed:", err);
        throw err;
    }
};

// ✅ Get current configuration
export const fetchConfigData = async () => {
    try {
        const API_BASE_URL = await getApiBaseUrl();
        const res = await fetch(`${API_BASE_URL}/api/config`);
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        return await res.json();
    } catch (err) {
        console.error("Error fetching config data:", err);
        throw err;
    }
};

// ✅ Update configuration
export const updateConfigData = async (configData) => {
    try {
        const API_BASE_URL = await getApiBaseUrl();
        const res = await fetch(`${API_BASE_URL}/api/config/update`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(configData),
        });
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        return await res.json();
    } catch (err) {
        console.error("Error updating config data:", err);
        throw err;
    }
};

export const fetchCameraFrame = async (camId) => {
    const API_BASE_URL = await getApiBaseUrl();
    const res = await fetch(`${API_BASE_URL}/api/camera_frame/${camId}`);
    if (!res.ok) throw new Error(`Failed to fetch frame for ${camId}`);
    const data = await res.json();
    if (!data.image) throw new Error(`No image returned for ${camId}`);
    return `data:image/jpeg;base64,${data.image}`;
};

export const fetchStations = async () => {
    const API_BASE_URL = await getApiBaseUrl();
    const res = await fetch(`${API_BASE_URL}/api/stations`);
    if (!res.ok) throw new Error("Failed to fetch stations");
    return res.json();
};

// export const fetchDashboardKpi = async () => {
//     const API_BASE_URL = await getApiBaseUrl();
//     const res = await fetch(`${API_BASE_URL}/api/dashboard/kpi`);
//     if (!res.ok) throw new Error("Failed to fetch KPI data");
//     return res.json();
// };

// export const fetchDashboardAlerts = async () => {
//     const API_BASE_URL = await getApiBaseUrl();
//     const res = await fetch(`${API_BASE_URL}/api/dashboard/alerts`);
//     if (!res.ok) throw new Error("Failed to fetch alerts");
//     return res.json();
// };

// export const fetchDashboardStations = async () => {
//     const API_BASE_URL = await getApiBaseUrl();
//     const res = await fetch(`${API_BASE_URL}/api/dashboard/stations`);
//     if (!res.ok) throw new Error("Failed to fetch stations");
//     return res.json();
// };

// export const fetchProductionRate = async () => {
//     const API_BASE_URL = await getApiBaseUrl();
//     const res = await fetch(`${API_BASE_URL}/api/dashboard/production-rate`);
//     if (!res.ok) throw new Error("Failed to fetch production rate");
//     return res.json();
// };

export const fetchLines = async () => {
    const API_BASE = await getApiBaseUrl();
    const res = await fetch(`${API_BASE}/api/lines`);
    if (!res.ok) throw new Error(`Failed to fetch lines: ${res.status}`);
    return res.json();
};

export const fetchDashboardKpi = async (lineId, productId) => {
    const API_BASE = await getApiBaseUrl();
    const res = await fetch(`${API_BASE}/api/dashboard/kpi?line_id=${lineId}&product_id=${productId}`);
    if (!res.ok) throw new Error(`Failed to fetch KPI: ${res.status}`);
    return res.json();
};

export const fetchDashboardAlerts = async (lineId) => {
    const API_BASE = await getApiBaseUrl();
    const res = await fetch(`${API_BASE}/api/dashboard/alerts?line_id=${lineId}`);
    if (!res.ok) throw new Error(`Failed to fetch alerts: ${res.status}`);
    return res.json();
};

export const fetchProductionRate = async (lineId) => {
    const API_BASE = await getApiBaseUrl();
    const res = await fetch(`${API_BASE}/api/dashboard/production-rate?line_id=${lineId}`);
    if (!res.ok) throw new Error(`Failed to fetch production rate: ${res.status}`);
    return res.json();
};

const sanitizeOperatorStatus = (stations) => {
    // Create a copy so the original API response is not modified
    const updatedStations = stations.map((station) => ({
        ...station,
    }));

    // Group only active stations by operator_id
    const operatorStations = {};

    updatedStations.forEach((station) => {
        const isActive =
            station.status === "running" ||
            station.status === "idle";

        const operatorId = station.operator_id;

        // Ignore stations where:
        // 1. Operator is not active
        // 2. operator_id is empty/null
        if (!isActive || !operatorId) {
            return;
        }

        if (!operatorStations[operatorId]) {
            operatorStations[operatorId] = [];
        }

        operatorStations[operatorId].push(station);
    });

    // Process each operator separately
    Object.values(operatorStations).forEach((stationsForOperator) => {

        // If operator is active at only one station,
        // keep its existing status
        if (stationsForOperator.length <= 1) {
            return;
        }

        // Sort active stations by station number
        // ST01 < ST02 < ST03 < ST04 ...
        stationsForOperator.sort((a, b) => {
            const aNumber = parseInt(
                a.station_name.replace("ST", ""),
                10
            );

            const bNumber = parseInt(
                b.station_name.replace("ST", ""),
                10
            );

            return aNumber - bNumber;
        });

        // Lowest-numbered active station gets priority
        stationsForOperator[0].status = "running";

        // All other active stations become away
        for (let i = 1; i < stationsForOperator.length; i++) {
            stationsForOperator[i].status = "away";
        }
    });

    return updatedStations;
};
export const fetchDashboardStations = async (lineId, productId) => {
    const API_BASE = await getApiBaseUrl();

    const res = await fetch(
        `${API_BASE}/api/dashboard/stations?line_id=${lineId}&product_id=${productId}`
    );

    if (!res.ok) {
        throw new Error("Failed to fetch stations");
    }

    const data = await res.json();

    // data.forEach((station) => {
    //     console.log(
    //         "--------------------",
    //         station.station_name,
    //         ":",
    //         station.status,
    //         "operator:",
    //         station.operator_id
    //     );
    // });

    // Apply operator status sanitization
    const updatedStations = sanitizeOperatorStatus(data);

    // Optional: check final result
    // updatedStations.forEach((station) => {
    //     console.log(
    //         "SANITIZED:",
    //         station.station_name,
    //         ":",
    //         station.status,
    //         "operator:",
    //         station.operator_id
    //     );
    // });

    return updatedStations;
};

export const fetchStationPerformance = async (lineId, stationId) => {
    const API_BASE = await getApiBaseUrl();
    const res = await fetch(`${API_BASE}/api/lines/${lineId}/stations/${stationId}/performance`);
    if (!res.ok) throw new Error(`Failed to fetch station performance: ${res.status}`);
    return res.json();
};

export const fetchStationSteps = async (lineId, productId) => {
    const API_BASE = await getApiBaseUrl();
    const res = await fetch(`${API_BASE}/api/stations/steps?line_id=${lineId}&product_id=${productId}`);
    if (!res.ok) throw new Error(`Failed to fetch station steps: ${res.status}`);
    return res.json();
};

export const fetchStationCards = async (
    stationId,
    lineId,
    productId
) => {
    const API_BASE = await getApiBaseUrl();

    const res = await fetch(
        `${API_BASE}/api/station-cards?station_id=${stationId}&line_id=${lineId}&product_id=${productId}`
    );

    if (!res.ok) {
        throw new Error(
            `Failed to fetch station cards: ${res.status}`
        );
    }

    const d = await res.json();

    return {
        // ─────────────────────────────────────────────
        // Basic Station Metrics
        // ─────────────────────────────────────────────

        ct: d.cycle_time,
        takt: d.takt_time,
        units: d.units_this_shift,
        productivity: d.operator_productivity,
        target: d.target_units,

        // ─────────────────────────────────────────────
        // Utilization
        // Comes directly from API
        // ─────────────────────────────────────────────

        util: d.utilization,

        // ─────────────────────────────────────────────
        // Operator Idle
        // ─────────────────────────────────────────────

        idleMin: Number(
            d.operator_idle_minutes ?? 0
        ),

        idlePct:
            d.operator_idle_pct ??
            d.operator_idle_percentage ??
            0,

        // ─────────────────────────────────────────────
        // Active
        // running_minutes = Active time
        //
        // Active percentage is calculated inside
        // StationCards using:
        //
        // running /
        // (running + idle + away) * 100
        // ─────────────────────────────────────────────

        activeMin: Number(
            d.running_minutes ?? 0
        ),

        // ─────────────────────────────────────────────
        // Away
        // ─────────────────────────────────────────────

        awayMin: Number(
            d.away_minutes ?? 0
        ),

        awayPct:
            d.away_percentage ?? 0,
    };
};


export const fetchPPEAlerts = async (
    stationId,
    lineId,
    productId
) => {
    const API_BASE = await getApiBaseUrl();

    const res = await fetch(
        `${API_BASE}/api/ppe/alerts?station_id=${stationId}&line_id=${lineId}&product_id=${productId}`
    );

    if (!res.ok) {
        throw new Error(
            `Failed to fetch PPE alerts: ${res.status}`
        );
    }

    const d = await res.json();

    return {
        shift: d.shift ?? "",
        sop_compliance: Number(
            d.sop_compliance ?? 0
        ),
        alerts: (d.alerts || []).map((a) => ({
            line: a.line_id ?? "Unknown",
            station: a.station_name ?? "Unknown",
            alert: a.violation_type ?? "PPE Violation",
            time: a.timestamp
                ? formatTimestamp(a.timestamp)
                : "—",
        })),
    };
};


export const fetchOperationProgress = async (stationId, lineId, productId) => {
    const API_BASE = await getApiBaseUrl();
    const res = await fetch(`${API_BASE}/api/operation/progress?station_id=${stationId}&line_id=${lineId}&product_id=${productId}`);
    if (!res.ok) throw new Error(`Failed to fetch operation progress: ${res.status}`);
    const d = await res.json();

    const mapStatus = (status) => {
        if (!status) return 'pending';

        const s = status.toLowerCase();

        if (['pass', 'completed', 'done'].includes(s)) {
            return 'done';
        }

        if (['in_progress', 'active', 'running'].includes(s)) {
            return 'active';
        }

        if (['fail', 'failed', 'missed'].includes(s)) {
            return 'failed';
        }

        return 'pending';
    };
    const steps = (d.steps || []).map((step) => {
        const state = mapStatus(step.status);
        const ts = state === 'done' ? step.completed_at : step.started_at;
        return {
            id: String(step.step_id ?? step.id ?? Math.random()),
            t: step.step_name ?? step.name ?? `Step ${step.step_id}`,
            s: state,
            time: ts ? formatTimestamp(ts) : undefined,
        };
    });

    return [{
        name: d.operation_name ?? 'Operation',
        pct: d.completion_percentage ?? 0,
        steps,
    }];
};

//this is function not api
function formatTimestamp(ts) {
    if (!ts) return '';
    try {
        return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
        return ts;
    }
}

export const fetchProductivity = async (lineId, stationId, productId) => {
    const API_BASE = await getApiBaseUrl();
    if (!lineId || !stationId) {
        throw new Error(
            "lineId and stationId are required"
        );
    }

    const url =
        `${API_BASE}/api/productivity` +
        `?line_id=${encodeURIComponent(lineId)}` +
        `&station_id=${encodeURIComponent(stationId)}` +
        `&product_id=${encodeURIComponent(productId)}`;

    console.log("Productivity API:", url);

    const res = await fetch(url);

    if (!res.ok) {
        throw new Error(
            `Failed to fetch productivity: ${res.status}`
        );
    }

    const d = await res.json();

    return (d.data || []).map((item) => ({
        shift: item.shift,
        uhr: Number(item.u_hr ?? 0),
    }));
};

export const fetchStationTimeline = async (lineId) => {
    const API_BASE = await getApiBaseUrl();

    const res = await fetch(
        `${API_BASE}/api/station/timeline?line_id=${lineId}`
    );

    if (!res.ok) {
        throw new Error(
            `Failed to fetch station timeline: ${res.status}`
        );
    }

    return res.json();
};

export const fetchLossTreeSummary = async (lineId = "line_1") => {
    const API_BASE = await getApiBaseUrl();

    const res = await fetch(
        `${API_BASE}/api/analytics/loss-tree?line_id=${lineId}`
    );

    if (!res.ok) {
        throw new Error(
            `Failed to fetch loss tree summary: ${res.status}`
        );
    }

    return res.json();
};

export const fetchShiftCycleTime = async (lineId, productId) => {
    const API_BASE = await getApiBaseUrl();

    const res = await fetch(
        `${API_BASE}/api/analytics/cycle-time-vs-takt-time?line_id=${lineId}`
    );

    if (!res.ok) {
        throw new Error(
            `Failed to fetch shift cycle time: ${res.status}`
        );
    }

    return res.json();
};

export const fetchStationCycleTime = async (lineId) => {
    const API_BASE = await getApiBaseUrl();

    const res = await fetch(
        `${API_BASE}/api/analytics/station-cycle-time?line_id=${lineId}`
    );

    if (!res.ok) {
        throw new Error(
            `Failed to fetch station cycle time: ${res.status}`
        );
    }

    return res.json();
};

export const fetchShiftPerformanceHeat = async (lineId) => {
    const API_BASE = await getApiBaseUrl();

    const res = await fetch(
        `${API_BASE}/api/analytics/shift-performance?line_id=${lineId}`
    );

    if (!res.ok) {
        throw new Error(
            `Failed to fetch shift performance heat: ${res.status}`
        );
    }

    return res.json();
};

export const fetchTopBottleneck = async (lineId) => {
    const API_BASE = await getApiBaseUrl();
    const res = await fetch(`${API_BASE}/api/dashboard/downtime?line_id=${lineId}`);
    if (!res.ok) throw new Error(`Failed to fetch top bottleneck: ${res.status}`);
    return res.json();
};

export const fetchSopComplianceScore = async (lineId) => {
    const API_BASE = await getApiBaseUrl();
    const res = await fetch(`${API_BASE}/api/overview/sop-compliance-score?line_id=${lineId}`);
    if (!res.ok) throw new Error(`Failed to fetch SOP compliance score: ${res.status}`);
    return res.json();
};

export const fetchOperatorComparison = async (lineId, productId) => {
    const API_BASE = await getApiBaseUrl();
    const res = await fetch(`${API_BASE}/api/operator-comparison?line_id=${lineId}&product_id=${productId}`);
    if (!res.ok) {
        throw new Error(`Failed to fetch operator comparison: ${res.status}`);
    }
    return res.json();
};

export const fetchAlerts = async (severity = "ALL", page = 1, limit = 10) => {
    const API_BASE = await getApiBaseUrl();
    const params = new URLSearchParams({ page, limit, });

    if (severity !== "ALL") {
        params.append("severity", severity);
    }

    const res = await fetch(`${API_BASE}/api/alerts?${params}`);

    if (!res.ok) {
        throw new Error(`Failed to fetch alerts: ${res.status}`);
    }
    return res.json();
};

export const fetchVideo = async (id) => {
    const API_BASE = await getApiBaseUrl();
    const res = await fetch(`${API_BASE}/api/video?id=${id}`);
    if (!res.ok) {
        throw new Error(`Failed to fetch video: ${res.status}`);
    }
    return res.blob(); // if backend returns mp4 directly
};

export const fetchHighCycleCounts = async (lineId, productId) => {
    const API_BASE = await getApiBaseUrl();

    const params = new URLSearchParams({
        line_id: lineId,
        product_id: productId,
    });

    const res = await fetch(
        `${API_BASE}/api/dashboard/handle_high_cycle_counts?${params.toString()}`
    );

    if (!res.ok) {
        throw new Error(`Failed to fetch high cycle counts: ${res.status}`);
    }

    return res.json();
};

export const fetchHighCycleDetails = async (lineId, productId, date, page = 1, limit = 10) => {
    const API_BASE = await getApiBaseUrl();
    const params = new URLSearchParams({ line_id: lineId, product_id: productId, date, page, limit, });
    const res = await fetch(`${API_BASE}/api/dashboard/handle_high_cycle_details?${params.toString()}`);

    if (!res.ok) {
        throw new Error(`Failed to fetch high cycle details: ${res.status}`);
    }

    return res.json();
};


// export const selectShift = async (shift, deleteDb) => {
//     try {
//         //  console.log(shift, deleteDb)
//         const API_BASE = await getApiBaseUrl();
//         const response = await fetch(`${API_BASE}/api/system/restart`, {
//             method: "POST",
//             headers: {
//                 "Content-Type": "application/json",
//             },
//             body: JSON.stringify({
//                 shift,
//                 delete_db: deleteDb,
//             }),
//         });
//         if (!response.ok) {
//             console.log("error: ", response.status)
//             throw new Error("Failed to select shift");

//         }
//         return await response.json();
//     } catch (error) {
//         console.error("Error selecting shift:", error);
//         throw error;
//     }
// };


export const selectShift = async (shift, deleteDb, load = false) => {
    try {
        const API_BASE = await getApiBaseUrl();

        const response = await fetch(
            `${API_BASE}/api/system/restart`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    shift: Number(shift),
                    delete_db: Boolean(deleteDb),
                    load: Boolean(load),
                }),
            }
        );

        console.log("Request:", {
            shift: Number(shift),
            delete_db: Boolean(deleteDb),
            load: Boolean(load),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            console.error("API error:", errorData);
            throw new Error("Failed to select shift");
        }

        return await response.json();

    } catch (error) {
        console.error("Error selecting shift:", error);
        throw error;
    }
};

export const fetchStationVideo = async (
    stationName,
    lineId,
    productId
) => {
    const API_BASE = await getApiBaseUrl();

    return `${API_BASE}/api/dashboard/station/video?station_name=${encodeURIComponent(
        stationName
    )}&line_id=${encodeURIComponent(
        lineId
    )}&product_id=${encodeURIComponent(
        productId
    )}`;
};




export const fetchUnitCycleTimes = async (
    lineId,
    productId
) => {
    const API_BASE = await getApiBaseUrl();

    console.log("lineId:", lineId);
    console.log("productId:", productId);

    const res = await fetch(
        `${API_BASE}/api/dashboard/unit-cycle-times?line_id=${lineId}&product_id=${productId}`
    );

    if (!res.ok) {
        throw new Error(
            `Failed to fetch unit cycle times: ${res.status}`
        );
    }

    const d = await res.json();

    return {
        xAxis: "Hour",
        yAxis: "Cycle Time (sec)",

        units: (d.data?.units || []).map((u) => ({
            unit: u.unit,
            cycleTime: Number(u.cycleTime),
            hour: u.hour,
        })),
    };
};






export async function fetchUnit_station_CycleTimes(
    lineId,
    stationId,
    productId
) {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(

        `${API_BASE}/api/dashboard/unit-station-times?line_id=${lineId}&station_id=${stationId}&product_id=${productId}`
    );

    if (!response.ok) {
        throw new Error("Failed to fetch unit station cycle times");
    }

    const json = await response.json();

    if (!json.success) {
        throw new Error("API returned unsuccessful response");
    }

    // Returns:
    // [
    //   { shift: "SHIFT 3", units: [...] },
    //   { shift: "SHIFT 1", units: [...] },
    //   { shift: "SHIFT 2", units: [...] }
    // ]
    return json.data;
}

export const acknowledgeAlert = async (alertId) => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(
        `${API_BASE}/api/alerts/${alertId}/acknowledge`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
        }
    );

    const data = await response.json();

    if (!response.ok) {
        throw new Error(
            data?.message ||
            "Failed to acknowledge alert"
        );
    }

    return data;
};

export const getStationPageOverview = async (lineId = "line_1") => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(
        `${API_BASE}/api/station-page/overview?line_id=${lineId}`
    );

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(
            data?.message || "Failed to fetch station page overview"
        );
    }

    return data;
};


export const getLossTree = async (
    lineId = "line_1",
    startDate,
    endDate
) => {
    const API_BASE = await getApiBaseUrl();

    // const params = new URLSearchParams({
    //     line_id: lineId,
    // });

    // if (startDate) {
    //     params.append("start_date", startDate);
    // }

    // if (endDate) {
    //     params.append("end_date", endDate);
    // }

    // const response = await fetch(
    //     `${API_BASE}/api/dashboard/loss-tree?${params.toString()}`
    // );
    const response = await fetch(
        `${API_BASE}/api/loss-tree`
    );

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(
            data?.message || "Failed to fetch loss tree"
        );
    }

    return data;
};

export const getOperatorIntelligence = async (lineId = "line_1") => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(
        `${API_BASE}/api/operator-intelligence?line_id=${lineId}`
    );

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(
            data?.message || "Failed to fetch operator intelligence"
        );
    }

    return data;
};

export const getOverviewCards = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/overview/cards`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch overview cards");
    }

    return data;
};

export const getProcessQualityFlow = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/overview/process-quality-flow`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch process quality flow");
    }

    return data;
};

export const getQualityTrend = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/overview/quality-trend`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch quality trend");
    }

    return data;
};

export const getVariantQualityPerformance = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/overview/variant-quality-performance`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch variant quality performance");
    }

    return data;
};

export const getShiftQualityComparison = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/overview/shift-quality-comparison`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch shift quality comparison");
    }

    return data;
};

export const getActiveQualityAlerts = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/overview/active-quality-alerts`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch active quality alerts");
    }

    return data;
};

export const getTopQualityEvents = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/overview/top-quality-events`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch top quality events");
    }

    return data;
};

export const getQualityExceptionsByType = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/overview/quality-exceptions-by-type`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch quality exceptions by type");
    }

    return data;
};

export const getProcessComplianceCards = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/process-compliance/cards`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch process compliance cards");
    }

    return data;
};

export const getVariantProcessView = async (variant, sopRevision) => {
    const API_BASE = await getApiBaseUrl();

    const params = new URLSearchParams();
    if (variant) params.set("variant", variant);
    if (sopRevision) params.set("sop_revision", sopRevision);
    const query = params.toString();

    const response = await fetch(
        `${API_BASE}/api/process-compliance/variant-process-view${query ? `?${query}` : ""}`
    );

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch variant process view");
    }

    return data;
};

export const getProcessAdherenceTrend = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/process-compliance/process-adherence-trend`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch process adherence trend");
    }

    return data;
};

export const getProcessExceptionsByType = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/process-compliance/exceptions-by-type`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch exceptions by type");
    }

    return data;
};

export const getRecentProcessExceptions = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/process-compliance/recent-process-exceptions`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch recent process exceptions");
    }

    return data;
};

export const getUnitGenealogy = async (serialNumber) => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(
        `${API_BASE}/api/unit-genealogy?serial_number=${encodeURIComponent(serialNumber)}`
    );

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch unit genealogy");
    }

    return data;
};

export const getEolRecoveryCards = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/eol-recovery/cards`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch EOL recovery cards");
    }

    return data;
};

export const getEolOutcomeJourney = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/eol-recovery/eol-outcome-journey`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch EOL outcome journey");
    }

    return data;
};

export const getEolRecoveryTrend = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/eol-recovery/eol-recovery-trend`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch EOL recovery trend");
    }

    return data;
};

export const getEolAttemptsPerUnit = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/eol-recovery/eol-attempts-per-unit`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch EOL attempts per unit");
    }

    return data;
};

export const getRecoveryRateByHour = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/eol-recovery/recovery-rate-by-hour`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch recovery rate by hour");
    }

    return data;
};

export const getRecoveryRateByVariant = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/eol-recovery/recovery-rate-by-variant`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch recovery rate by variant");
    }

    return data;
};

export const getEolRecoveryEvents = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/eol-recovery/eol-recovery-events`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch EOL recovery events");
    }

    return data;
};

export const getUnitEolJourney = async (serialNumber) => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(
        `${API_BASE}/api/eol-recovery/unit-eol-journey?serial_number=${encodeURIComponent(serialNumber)}`
    );

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch unit EOL journey");
    }

    return data;
};

export const getDefectRateHeatmap = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/final-inspection/defect-rate-heatmap`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch defect rate heatmap");
    }

    return data;
};

export const getComplianceByShift = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/process-compliance/compliance-by-shift`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch compliance by shift");
    }

    return data;
};

export const getExceptionsByVariant = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/process-compliance/exception-by-variant`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch exceptions by variant");
    }

    return data;
};

export const getFinalInspectionCards = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/final-inspection/cards`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch final inspection cards");
    }

    return data;
};

export const getFinalInspectionOutcomeBreakdown = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/final-inspection/outcome-breakdown`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch final inspection outcome breakdown");
    }

    return data;
};

export const getFpyTrend = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/final-inspection/fpy-trend`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch FPY trend");
    }

    return data;
};

export const getDefectsByCategory = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/final-inspection/defects-by-category`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch defects by category");
    }

    return data;
};

export const getRejectReasonBreakdown = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/final-inspection/reject-reason-breakdown`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch reject reason breakdown");
    }

    return data;
};

export const getEscapeRateTrend = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/final-inspection/escape-rate-trend`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch escape rate trend");
    }

    return data;
};

export const getTopDefectContributors = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/final-inspection/top-defect-contributors`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch top defect contributors");
    }

    return data;
};

export const getFinalInspectionEvents = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/final-inspection/event`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch final inspection events");
    }

    return data;
};

export const getFieldFailureInvestigation = async (query) => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(
        `${API_BASE}/api/field-failure-investigation?query=${encodeURIComponent(query)}`
    );

    if (response.status === 404) {
        const body = await response.json().catch(() => ({}));
        return { notFound: true, message: body?.message || "No match found for that search." };
    }

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch field failure investigation");
    }

    return data;
};

// POSTs straight to /api/field-failure-investigation itself — NOT
// /:serialNumber/complaint or /complaints (both 404 in testing).
// Body: { case_number, serial_number, customer, customer_ref,
// reported_date, failure_description }. serial_number must be the
// plain numeric id, not the "SN-###" display string.
export const saveFieldFailureComplaint = async (payload) => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/field-failure-investigation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to save complaint");
    }

    return data.data;
};

export const getStationsOverview = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/stations/overall`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch stations overview");
    }

    return data;
};

export const getStationPerformanceMatrix = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/stations/performance-matrix`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch station performance matrix");
    }
    return data;
};

export const getStationFlow = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/stations/flow`);
    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch station flow");
    }

    return data;
};

export const getStationsRequiringAttention = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(
        `${API_BASE}/api/stations/requiring-attention`
    );

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(
            data?.message || "Failed to fetch stations requiring attention"
        );
    }

    return data;
};

export const getStationDetails = async (station) => {
    const API_BASE = await getApiBaseUrl();

    const stationMap = {
        main_assembly: "CAA",
        eol: "EOL",
        final_inspection: "INSPECTION",
    };

    const operation = stationMap[station];

    if (!operation) {
        throw new Error(`Invalid station: ${station}`);
    }

    const response = await fetch(
        `${API_BASE}/api/stations/details?station=${encodeURIComponent(operation)}`
    );

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(
            data?.message || "Failed to fetch station details"
        );
    }

    return data;
};

export const getAnalyticsTopCards = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/analytics/top-cards`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch analytics top cards");
    }
    return data;
};

export const getFpyTrendAnalytics = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/analytics/fpy-trend`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch FPY trend");
    }
    return data;
};

export const getEolRecoveryRateTrend = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/analytics/eol-recovery-rate`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch EOL recovery rate trend");
    }
    return data;
};

export const getProcessAdherenceTrendAnalytics = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/analytics/process-adherence`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch process adherence trend");
    }
    return data;
};

export const getFinalPassRateVsRejectRate = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/analytics/final-pass-rate-vs-reject-rate`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch final pass rate vs reject rate");
    }
    return data;
};

export const getFpyByVariant = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/analytics/fpy-by-variant`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch FPY by variant");
    }
    return data;
};

export const getFpyByLine = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/analytics/fpy-by-line`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch FPY by line");
    }
    return data;
};

export const getQualityMetricsByShift = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/analytics/quality-metrics-by-shift`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch quality metrics by shift");
    }
    return data;
};

export const getTopProcessExceptions = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/analytics/top-process-exceptions`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch top process exceptions");
    }
    return data;
};

export const getFpyByVariantHeatmap = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/analytics/fpy-by-variant-heatmap`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch FPY by variant heatmap");
    }
    return data;
};

export const getDefectiveUnitsByCategory = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/analytics/defective-units-by-category`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch defective units by category");
    }
    return data;
};

export const getEolRecoveryRateByVariant = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/analytics/eol-recovery-rate-by-variant`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch EOL recovery rate by variant");
    }
    return data;
};

export const getKeyInsights = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/analytics/key-insights`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch key insights");
    }
    return data;
};

export const getLossTimeByCategory = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/analytics/loss-time-by-category`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch loss time by category");
    }
    return data;
};

export const getOeeBreakdown = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/analytics/oee-breakdown`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch OEE breakdown");
    }
    return data;
};

export const getProductionPlanVsActual = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/overview/production-plan-vs-actual`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch production plan vs actual");
    }
    return data;
};

export const getShiftWiseProductionComparison = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/overview/shift-wise-production-comparison`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch shift wise production comparison");
    }
    return data;
};

export const getShiftQualityComparisons = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/overview/shift-quality-comparison`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch shift quality comparison");
    }
    return data;
};

export const getTopQualityEventsPareto = async () => {
    const API_BASE = await getApiBaseUrl();
    const response = await fetch(`${API_BASE}/api/overview/top-quality-events-pareto`);
    const data = await response.json();
    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch top quality events (Pareto)");
    }
    return data;
};

export const getStationCounts = async () => {
    const API_BASE = await getApiBaseUrl();

    const response = await fetch(`${API_BASE}/api/overview/station-counts`);

    const data = await response.json();

    if (!response.ok || !data?.success) {
        throw new Error(data?.message || "Failed to fetch station counts");
    }

    return data;
};