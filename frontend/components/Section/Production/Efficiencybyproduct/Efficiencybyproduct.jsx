import React from "react";
import { Box, Typography } from "@mui/material";
import Panel from "../../Overview/Panel/Panel";
import useDashboardColors from "../../Overview/Tokens/Tokens";

const DEFAULT_DATA = [
  { label: "Towel – Standard", pct: 92 },
  { label: "Towel – Premium", pct: 89 },
  { label: "Hand Towel", pct: 86 },
  { label: "Bath Towel", pct: 84 },
  { label: "Others", pct: 76 },
];

const greenShades = ["#0f9d63", "#19b26e", "#37c184", "#66d29e", "#9ce0bf"];

export default function EfficiencyByProduct({ data = DEFAULT_DATA }) {
  const c = useDashboardColors();

  return (
    <Panel title="Efficiency by Product">
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1.75 }}>
        {data.map((row, i) => {
          const isOther = row.label.toLowerCase().startsWith("other");
          const color = isOther
            ? "#c7bfb8"
            : greenShades[Math.min(i, greenShades.length - 1)];

          return (
            <Box
              key={row.label}
              sx={{ display: "flex", alignItems: "center", gap: 1.5 }}
            >
              <Typography
                sx={{
                  width: 110,
                  flexShrink: 0,
                  fontSize: 12.5,
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
                    width: `${row.pct}%`,
                    height: "100%",
                    borderRadius: "4px",
                    bgcolor: color,
                    transition: "width 0.4s ease",
                  }}
                />
              </Box>

              <Typography
                sx={{
                  width: 38,
                  flexShrink: 0,
                  textAlign: "right",
                  fontSize: 12.5,
                  fontWeight: 700,
                  color: c.title,
                }}
              >
                {row.pct}%
              </Typography>
            </Box>
          );
        })}
      </Box>
    </Panel>
  );
}
