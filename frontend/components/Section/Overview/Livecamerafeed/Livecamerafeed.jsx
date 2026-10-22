import React, { useCallback, useEffect, useState } from "react";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import VideocamOutlinedIcon from "@mui/icons-material/VideocamOutlined";
import RefreshIcon from "@mui/icons-material/Refresh";
import SignalWifiStatusbar4BarIcon from "@mui/icons-material/SignalWifiStatusbar4Bar";
import { getLiveCameraFeed } from "../../../../utils/api";

const RECONNECT_DELAY = 5000; // Retry every 5 seconds

export default function LiveCameraFeed({
  cameraId = "cam1",
  title = "Live Camera Feed",
  height = 420,
  mode = "live",
}) {
  const [streamUrl, setStreamUrl] = useState("");
  const [status, setStatus] = useState("connecting");
  const [error, setError] = useState("");

  const loadFeed = useCallback(async () => {
    setStatus("connecting");
    setError("");
    setStreamUrl("");

    try {
      const response = await getLiveCameraFeed(cameraId);

      if (!response?.streamUrl) {
        throw new Error("Stream URL is not available.");
      }

      setStreamUrl(response.streamUrl);
      setStatus("live");
    } catch (err) {
      console.error("Failed to load camera feed:", err);
      setStatus("disconnected");
      setError(err.message || "Unable to connect to the camera.");
    }
  }, [cameraId]);

  useEffect(() => {
    if (mode === "recorded") return; // no live connection while viewing a recording
    loadFeed();
  }, [loadFeed, mode]);

  const handleStreamError = () => {
    setStatus("disconnected");
    setError("The video stream could not be played.");
  };

  /* Recorded section: the live camera is not shown */
  if (mode === "recorded") {
    return (
      <Paper
        variant="outlined"
        sx={{
          borderRadius: 2,
          overflow: "hidden",
          bgcolor: "background.paper",
        }}
      >
        <Stack direction="row" alignItems="center" spacing={1.25} sx={{ p: 2 }}>
          <VideocamOutlinedIcon color="action" />
          <Typography variant="subtitle1" fontWeight={600}>
            {title}
          </Typography>
        </Stack>

        <Box
          sx={{
            bgcolor: "#111",
            width: "100%",
            height,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            px: 3,
            textAlign: "center",
          }}
        >
          <Stack alignItems="center" spacing={1}>
            <SignalWifiStatusbar4BarIcon sx={{ fontSize: 42, color: "#999" }} />
            <Typography color="white" fontWeight={500}>
              Feed not available
            </Typography>
            <Typography variant="body2" sx={{ color: "#bbb" }}>
              You are in the Recorded section. Switch to Live to see the camera.
            </Typography>
          </Stack>
        </Box>
      </Paper>
    );
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        borderRadius: 2,
        overflow: "hidden",
        bgcolor: "background.paper",
      }}
    >
      {/* Header */}
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        spacing={2}
        sx={{ p: 2 }}
      >
        <Stack direction="row" alignItems="center" spacing={1.25}>
          <VideocamOutlinedIcon color="action" />

          <Box>
            <Typography variant="subtitle1" fontWeight={600}>
              {title}
            </Typography>

            <Typography variant="caption" color="text.secondary">
              Camera ID: {cameraId}
            </Typography>
          </Box>
        </Stack>

        <Stack direction="row" alignItems="center" spacing={1}>
          <Chip
            size="small"
            label={
              status === "live"
                ? "Live"
                : status === "connecting"
                  ? "Connecting"
                  : "Disconnected"
            }
            color={
              status === "live"
                ? "success"
                : status === "connecting"
                  ? "warning"
                  : "error"
            }
            variant="outlined"
          />

          <Button
            size="small"
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={loadFeed}
            disabled={status === "connecting"}
          >
            Refresh
          </Button>
        </Stack>
      </Stack>

      {/* Live picture (the backend sends MJPEG, which an <img> plays natively) */}
      <Box
        sx={{
          position: "relative",
          bgcolor: "#111",
          width: "100%",
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          overflow: "hidden",
        }}
      >
        {status === "live" && streamUrl ? (
          <img
            key={streamUrl}
            src={streamUrl}
            alt={`Live feed from ${cameraId}`}
            onError={handleStreamError}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "contain",
            }}
          />
        ) : (
          <Stack
            alignItems="center"
            justifyContent="center"
            spacing={1.5}
            sx={{ px: 3, textAlign: "center" }}
          >
            {status === "connecting" ? (
              <CircularProgress size={34} />
            ) : (
              <SignalWifiStatusbar4BarIcon
                sx={{ fontSize: 42, color: "#999" }}
              />
            )}

            <Typography color="white" fontWeight={500}>
              {status === "connecting"
                ? "Connecting to camera..."
                : "Camera feed unavailable"}
            </Typography>

            {status === "disconnected" && (
              <Typography variant="body2" sx={{ color: "#bbb" }}>
                {error}
              </Typography>
            )}
          </Stack>
        )}
      </Box>

      {/* Footer */}
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        sx={{ px: 2, py: 1.25 }}
      >
        <Typography variant="caption" color="text.secondary">
          {status === "live"
            ? "Stream connected"
            : status === "connecting"
              ? "Establishing connection"
              : "Check the camera or backend connection"}
        </Typography>

        <Typography variant="caption" color="text.secondary">
          {status === "live" ? "Video stream" : "No active stream"}
        </Typography>
      </Stack>
    </Paper>
  );
}