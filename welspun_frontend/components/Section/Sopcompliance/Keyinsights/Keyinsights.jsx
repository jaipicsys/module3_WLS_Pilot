import React from "react";
import { Box, Card, Typography } from "@mui/material";
import LightbulbOutlinedIcon from "@mui/icons-material/LightbulbOutlined";
import WarningAmberRoundedIcon from "@mui/icons-material/WarningAmberRounded";
import SettingsIcon from "@mui/icons-material/Settings";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import useDashboardColors from "../../Overview/Tokens/Tokens";

const buildDefault = (c) => [
  {
    icon: <WarningAmberRoundedIcon />,
    color: c.red,
    title: "Incorrect folding is the top deviation (42%).",
    detail: "Provide additional operator training and visual guides.",
  },
  {
    icon: <WarningAmberRoundedIcon />,
    color: c.orange,
    title: "Pack count deviations (16%).",
    detail: "Implement in-line count validation.",
  },
  {
    icon: <SettingsIcon />,
    color: c.accent,
    title: "Seal not applied (8%).",
    detail: "Add checklist and station-level alerts.",
  },
  {
    icon: <CheckCircleIcon />,
    color: c.green,
    title: "SOP adherence improved by 4% vs. previous shift.",
    detail: "Continue monitoring and recognize top performers.",
  },
];

export default function KeyInsights({ data }) {
  const c = useDashboardColors();
  const rows = data || buildDefault(c);

  return (
    <Card
      variant="outlined"
      sx={{
        height: "100%",
        borderRadius: "14px",
        bgcolor: c.cardBg,
        border: `1px solid ${c.cardBorder}`,
        boxShadow: "none",
        p: 2,
      }}
    >
      {/* Header with lightbulb icon */}
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1.5 }}>
        <LightbulbOutlinedIcon sx={{ fontSize: 20, color: c.accent }} />
        <Typography sx={{ fontSize: 15, fontWeight: 700, color: c.title }}>
          Key Insights & Actions
        </Typography>
      </Box>

      <Box sx={{ display: "flex", flexDirection: "column" }}>
        {rows.map((r, i) => (
          <Box
            key={i}
            sx={{
              display: "flex",
              alignItems: "flex-start",
              gap: 1.5,
              py: 1.25,
              borderBottom:
                i < rows.length - 1 ? `1px solid ${c.cardBorder}` : "none",
            }}
          >
            <Box
              sx={{
                width: 34,
                height: 34,
                borderRadius: "9px",
                flexShrink: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                bgcolor: `${r.color}1f`,
                color: r.color,
                "& svg": { fontSize: 20 },
              }}
            >
              {r.icon}
            </Box>

            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography
                sx={{ fontSize: 13, fontWeight: 700, color: c.title }}
              >
                {r.title}
              </Typography>
              <Typography sx={{ fontSize: 12, color: c.muted }}>
                {r.detail}
              </Typography>
            </Box>
          </Box>
        ))}
      </Box>
    </Card>
  );
}
