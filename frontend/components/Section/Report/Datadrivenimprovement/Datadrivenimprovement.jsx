import React from "react";
import { Box, Card, Typography } from "@mui/material";
import InsightsIcon from "@mui/icons-material/Insights";
import useDashboardColors from "../../Overview/Tokens/Tokens";
import Panel from "../../Overview/Panel/Panel";

export default function DataDrivenImprovement({
  text = "Use reports and trends to identify opportunities, take action and drive higher productivity, quality and compliance.",
  quote = "What gets measured, gets improved.",
}) {
  const c = useDashboardColors();

  return (
    <Panel>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, mb: 1.5 }}>
        <InsightsIcon sx={{ fontSize: 24, color: c.accent }} />
        <Typography sx={{ fontSize: 16, fontWeight: 700, color: c.title }}>
          Data-Driven Improvement
        </Typography>
      </Box>

      <Typography sx={{ fontSize: 13, color: c.text, lineHeight: 1.6, mb: 2 }}>
        {text}
      </Typography>

      <Box
        sx={{
          p: 1.5,
          borderRadius: "10px",
          bgcolor: "#036b4c27",
          textAlign: "center",
        }}
      >
        <Typography
          sx={{
            fontSize: 14,
            fontWeight: 700,
            fontStyle: "italic",
            color: c.accent,
          }}
        >
          “{quote}”
        </Typography>
      </Box>
    </Panel>
  );
}
