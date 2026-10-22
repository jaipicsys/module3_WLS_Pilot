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
      credentials: "include", // Send HTTP-only cookies with request
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

  const res = await fetch(`${API_BASE_URL}/api/reports?${params.toString()}`, {
    method: "GET",
    headers: {
      Accept: "application/pdf",
    },
  });

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

/* ---------------- Overview page ---------------- */

// The four KPI cards: total output, output/hour, productive time, idle time.
export const getKpiCards = async (mode = "live") => {
  const API_BASE_URL = await getApiBaseUrl();
  const res = await fetch(
    `${API_BASE_URL}/api/kpi-cards?mode=${encodeURIComponent(mode)}`,
  );

  if (!res.ok) {
    throw new Error(`Failed to fetch KPI cards (${res.status})`);
  }

  return res.json();
};

// Output Trend chart: units per 5 minutes -> { interval_minutes, date, series: [{ time, label, output, target }] }
export const getOutputTrend = async (mode = "live") => {
  const API_BASE_URL = await getApiBaseUrl();
  const res = await fetch(
    `${API_BASE_URL}/api/output-trend?mode=${encodeURIComponent(mode)}`,
  );

  if (!res.ok) {
    throw new Error(`Failed to fetch output trend (${res.status})`);
  }

  return res.json();
};

// Output by Product chart -> { products: [{ name, value, placeholder }] }
export const getOutputByProduct = async (mode = "live") => {
  const API_BASE_URL = await getApiBaseUrl();
  const res = await fetch(
    `${API_BASE_URL}/api/output-by-product?mode=${encodeURIComponent(mode)}`,
  );

  if (!res.ok) {
    throw new Error(`Failed to fetch output by product (${res.status})`);
  }

  return res.json();
};

// Top Operators table -> { operators: [{ rank, operator_id, active_display, idle_display, away_display, utilization_pct, ... }] }
export const getTopOperators = async (mode = "live") => {
  const API_BASE_URL = await getApiBaseUrl();
  const res = await fetch(
    `${API_BASE_URL}/api/top-operators?mode=${encodeURIComponent(mode)}`,
  );

  if (!res.ok) {
    throw new Error(`Failed to fetch top operators (${res.status})`);
  }

  return res.json();
};

// Loss Breakdown chart -> { total_display, items: [{ label, type, display, pct, seconds }] }
export const getLossBreakdown = async (mode = "live") => {
  const API_BASE_URL = await getApiBaseUrl();
  const res = await fetch(
    `${API_BASE_URL}/api/loss-breakdown?mode=${encodeURIComponent(mode)}`,
  );

  if (!res.ok) {
    throw new Error(`Failed to fetch loss breakdown (${res.status})`);
  }

  return res.json();
};

// Live feed: configured cameras -> { cameras: [{ id, online }] }
export const getCameras = async () => {
  const API_BASE_URL = await getApiBaseUrl();
  const res = await fetch(`${API_BASE_URL}/api/cameras`);

  if (!res.ok) {
    throw new Error(`Failed to fetch cameras (${res.status})`);
  }

  return res.json();
};

// Live feed URL for an <img src={...}>. The browser keeps the MJPEG stream open
// and updates the picture by itself, so no polling is needed.
export const getCameraStreamUrl = async (camId) => {
  const API_BASE_URL = await getApiBaseUrl();
  return `${API_BASE_URL}/api/camera/${encodeURIComponent(camId)}/stream`;
};

// Used by LiveCameraFeed: checks the camera is delivering frames and returns
// the URL to show in an <img>.  -> { streamUrl }
export const getLiveCameraFeed = async (camId) => {
  const API_BASE_URL = await getApiBaseUrl();

  const res = await fetch(`${API_BASE_URL}/api/cameras`);
  if (!res.ok) {
    throw new Error(`Failed to reach the camera service (${res.status})`);
  }

  const { cameras = [] } = await res.json();
  const camera = cameras.find((c) => c.id === camId);

  if (!camera) {
    throw new Error(`Camera "${camId}" is not configured.`);
  }
  if (!camera.online) {
    throw new Error("Camera is offline. No frames are arriving.");
  }

  // "t" makes every Refresh open a fresh stream.
  return {
    streamUrl: `${API_BASE_URL}/api/camera/${encodeURIComponent(camId)}/stream?t=${Date.now()}`,
  };
};

// Which modes can be used -> { modes: [{ id: "live", available }, { id: "recorded", available, from, to }] }
export const getModes = async () => {
  const API_BASE_URL = await getApiBaseUrl();
  const res = await fetch(`${API_BASE_URL}/api/modes`);

  if (!res.ok) {
    throw new Error(`Failed to fetch modes (${res.status})`);
  }

  return res.json();
};
