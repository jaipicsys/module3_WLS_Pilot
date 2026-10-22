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
}) {
  const [streamUrl, setStreamUrl] = useState("");
  const [status, setStatus] = useState("connecting");
  const [error, setError] = useState("");
  const [retryCount, setRetryCount] = useState(0);

  // Fetch the stream URL from the API
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
      setRetryCount(0);
    } catch (err) {
      console.error("Failed to load camera feed:", err);

      setStatus("disconnected");
      setError(err.message || "Unable to connect to the camera.");

      setRetryCount((count) => count + 1);
    }
  }, [cameraId]);

  // Initial connection and reconnect when the camera ID changes
  useEffect(() => {
    loadFeed();
  }, [loadFeed]);

  // Automatically retry when disconnected
  useEffect(() => {
    if (status !== "disconnected") return undefined;

    const timer = setTimeout(() => {
      loadFeed();
    }, RECONNECT_DELAY);

    return () => clearTimeout(timer);
  }, [status, retryCount, loadFeed]);

  // Handle MJPEG stream errors
  const handleStreamError = () => {
    setStatus("disconnected");
    setError("The video stream could not be played.");
    setStreamUrl("");
    setRetryCount((count) => count + 1);
  };

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
        sx={{
          p: 2,
          flexWrap: "wrap",
          rowGap: 1.5,
        }}
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

        </Stack>
      </Stack>

      {/* Live camera feed */}
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
            sx={{
              px: 3,
              textAlign: "center",
            }}
          >
            {status === "connecting" ? (
              <CircularProgress size={34} />
            ) : (
              <SignalWifiStatusbar4BarIcon
                sx={{
                  fontSize: 42,
                  color: "#999",
                }}
              />
            )}

            <Typography color="white" fontWeight={500}>
              {status === "connecting"
                ? "Connecting to camera..."
                : "Camera feed unavailable"}
            </Typography>

            {status === "disconnected" && (
              <>
                <Typography variant="body2" sx={{ color: "#bbb" }}>
                  {error}
                </Typography>

                <Typography variant="caption" sx={{ color: "#bbb" }}>
                  Retrying in 5 seconds... (Attempt {retryCount})
                </Typography>
              </>
            )}
          </Stack>
        )}
      </Box>

      {/* Footer */}
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        spacing={1}
        sx={{
          px: 2,
          py: 1.25,
          flexWrap: "wrap",
        }}
      >
        <Typography variant="caption" color="text.secondary">
          {status === "live"
            ? "Stream connected"
            : status === "connecting"
              ? "Establishing connection"
              : "Waiting to reconnect"}
        </Typography>

        <Typography variant="caption" color="text.secondary">
          {status === "live"
            ? "Video stream"
            : status === "connecting"
              ? "Connection in progress"
              : `Retry attempt: ${retryCount}`}
        </Typography>
      </Stack>
    </Paper>
  );
}
