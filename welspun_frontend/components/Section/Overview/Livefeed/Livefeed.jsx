import React from "react";
import { Box, Card, Typography } from "@mui/material";
import FullscreenIcon from "@mui/icons-material/Fullscreen";
import useDashboardColors from "../Tokens/Tokens";

/*
 * Live feed card. Pass a `src` (mp4/stream) to show <video>, or a `poster`
 * image URL for a still. With neither, a neutral placeholder is shown.
 *
 * Props: title, caption, src, poster, onExpand, height
 */
export default function LiveFeed({
  title = "Live Feed (Line 1 – Towel Packing)",
  caption = "Line 1 – Towel Packing",
  src,
  poster,
  onExpand,
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
      {/* Header */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          mb: 1.5,
        }}
      >
        <Typography sx={{ fontSize: 15, fontWeight: 700, color: c.title }}>
          {title}
        </Typography>

        <Box
          sx={{
            display: "inline-flex",
            alignItems: "center",
            gap: 0.6,
            px: 1,
            py: 0.3,
            borderRadius: "6px",
            bgcolor: "#0f7a3d",
            color: "#fff",
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "0.04em",
          }}
        >
          <Box
            sx={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              bgcolor: "#fff",
              animation: "pulse 1.5s infinite",
            }}
          />
          LIVE
        </Box>
      </Box>

      {/* Media */}
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
            autoPlay
            muted
            loop
            playsInline
            sx={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        )}

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

        {/* Fullscreen bottom-right */}
        <Box
          onClick={onExpand}
          sx={{
            position: "absolute",
            right: 8,
            bottom: 8,
            width: 28,
            height: 28,
            borderRadius: "6px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            bgcolor: "rgba(0,0,0,0.45)",
            color: "#fff",
            cursor: "pointer",
            "&:hover": { bgcolor: "rgba(0,0,0,0.65)" },
          }}
        >
          <FullscreenIcon sx={{ fontSize: 18 }} />
        </Box>
      </Box>
    </Card>
  );
}
