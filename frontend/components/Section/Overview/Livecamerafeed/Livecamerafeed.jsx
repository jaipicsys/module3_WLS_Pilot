import React from "react";
import { Box, Chip, Paper, Stack, Typography } from "@mui/material";
import VideocamOutlinedIcon from "@mui/icons-material/VideocamOutlined";

const IMAGE_SRC = "/dummy_1.jpg"; // served from public/dummy_1.jpg

export default function LiveCameraFeed({
  cameraId = "cam1",
  title = "Live Camera Feed",
  height = 420,
}) {
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

        <Chip size="small" label="Live" color="success" variant="outlined" />
      </Stack>

      {/* Picture */}
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
        <img
          src={IMAGE_SRC}
          alt={`Live feed from ${cameraId}`}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "contain",
          }}
        />
      </Box>

      {/* Footer */}
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        sx={{ px: 2, py: 1.25 }}
      >
        <Typography variant="caption" color="text.secondary">
          Stream connected
        </Typography>

        <Typography variant="caption" color="text.secondary">
          Video stream
        </Typography>
      </Stack>
    </Paper>
  );
}
