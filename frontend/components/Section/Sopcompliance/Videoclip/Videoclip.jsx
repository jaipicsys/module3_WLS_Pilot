import React from "react";
import { Box, Card, Typography } from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import useDashboardColors from "../../Overview/Tokens/Tokens";

/*
 * A recorded clip card (play button overlay + progress time).
 *
 * Props: title, caption, progress ("00:19 / 01:17"), src, poster, onPlay, height
 */
export default function VideoClip({
  title = "Video Clip – SOP Deviation",
  caption = "Line 1 – Incorrect Folding Sequence",
  progress = "00:19 / 01:17",
  src,
  poster,
  onPlay,
  height = 300,
}) {
  const c = useDashboardColors();

  return (
    <Card
      variant="outlined"
      sx={{
        height: "100%",
        minHeight: height,
        display: "flex",
        flexDirection: "column",
        borderRadius: "14px",
        bgcolor: c.cardBg,
        border: `1px solid ${c.cardBorder}`,
        boxShadow: "none",
        p: 2,
      }}
    >
      <Typography
        sx={{ fontSize: 15, fontWeight: 700, color: c.title, mb: 1.5 }}
      >
        {title}
      </Typography>

      <Box
        sx={{
          position: "relative",
          flex: 1,
          minHeight: 0,
          borderRadius: "10px",
          overflow: "hidden",
          bgcolor: "#0d1b24",
          backgroundImage: poster ? `url(${poster})` : "none",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        {src && (
          <Box
            component="video"
            src={src}
            poster={poster}
            sx={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        )}

        {/* Play button */}
        <Box
          onClick={onPlay}
          sx={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
          }}
        >
          <Box
            sx={{
              width: 52,
              height: 52,
              borderRadius: "50%",
              bgcolor: "#1e88e5",
              color: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 4px 14px rgba(0,0,0,0.4)",
              transition: "transform 0.15s",
              "&:hover": { transform: "scale(1.08)" },
            }}
          >
            <PlayArrowIcon sx={{ fontSize: 30 }} />
          </Box>
        </Box>

        {/* Caption bottom-left */}
        <Typography
          sx={{
            position: "absolute",
            left: 10,
            bottom: 8,
            color: "#fff",
            fontSize: 12,
            fontWeight: 600,
            textShadow: "0 1px 3px rgba(0,0,0,0.6)",
          }}
        >
          {caption}
        </Typography>

        {/* Progress bottom-right */}
        <Typography
          sx={{
            position: "absolute",
            right: 10,
            bottom: 8,
            color: "#fff",
            fontSize: 11.5,
            fontWeight: 500,
            fontVariantNumeric: "tabular-nums",
            textShadow: "0 1px 3px rgba(0,0,0,0.6)",
          }}
        >
          {progress}
        </Typography>
      </Box>
    </Card>
  );
}
