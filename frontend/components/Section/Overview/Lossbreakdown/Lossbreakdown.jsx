import React from "react";
import { Box, Typography } from "@mui/material";
import Panel from "../Panel/Panel";
import useDashboardColors from "../Tokens/Tokens";

/* Static loss rows (pct drives the bar width and the label) */
const ROWS = [
  { label: "Away", pct: 53, amount: "29m 21s", color: "#f0563a" },
  {
    label: "Waiting for materials",
    pct: 43,
    amount: "23m 53s",
    color: "orange",
  },
  { label: "Others", pct: 4, amount: "2m 2s", color: "gray" },
];

export default function LossBreakdown() {
  const c = useDashboardColors();

  const max = Math.max(...ROWS.map((r) => r.pct), 1);

  return (
    <Panel title="Loss Breakdown">
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1.75 }}>
        {ROWS.map((row) => (
          <Box
            key={row.label}
            sx={{ display: "flex", alignItems: "center", gap: 1.5 }}
          >
            <Typography
              sx={{
                width: 130,
                flexShrink: 0,
                fontSize: 12.5,
                lineHeight: 1.25,
                color: c.text,
              }}
            >
              {row.label}
            </Typography>

            <Box
              sx={{
                flex: 1,
                height: 20,
                borderRadius: "4px",
                bgcolor: c.track,
                overflow: "hidden",
              }}
            >
              <Box
                sx={{
                  width: `${(row.pct / max) * 100}%`,
                  height: "100%",
                  borderRadius: "4px",
                  bgcolor: c[row.color] ?? row.color,
                  transition: "width 0.4s ease",
                }}
              />
            </Box>

            <Typography
              sx={{
                width: 100,
                flexShrink: 0,
                textAlign: "right",
                fontSize: 12,
                fontWeight: 600,
                color: c.muted,
                whiteSpace: "nowrap",
              }}
            >
              {row.amount} ({row.pct}%)
            </Typography>
          </Box>
        ))}
      </Box>
    </Panel>
  );
}
