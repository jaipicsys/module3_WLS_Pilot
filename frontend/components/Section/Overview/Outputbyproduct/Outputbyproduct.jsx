import React from "react";
import { Box, Typography } from "@mui/material";
import Panel from "../Panel/Panel";
import useDashboardColors, { barShades } from "../Tokens/Tokens";

/* Static output per product */
const ROWS = [
  { label: "Towel-Standard", value: 11 },
  { label: "Towel – Premium", value: 6 },
  { label: "Hand Towel", value: 4 },
  { label: "Bath Towel", value: 18 },
  { label: "Others", value: 4 },
];

export default function OutputByProduct() {
  const c = useDashboardColors();

  const max = Math.max(...ROWS.map((d) => d.value), 1);

  return (
    <Panel title="Output by Product">
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1.75 }}>
        {ROWS.map((row, i) => {
          const isOther = row.label.toLowerCase().startsWith("other");
          const color = isOther
            ? c.gray
            : barShades[Math.min(i, barShades.length - 1)];

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
                    width: `${(row.value / max) * 100}%`,
                    height: "100%",
                    borderRadius: "4px",
                    bgcolor: color,
                    transition: "width 0.4s ease",
                  }}
                />
              </Box>

              <Typography
                sx={{
                  width: 40,
                  flexShrink: 0,
                  textAlign: "right",
                  fontSize: 12.5,
                  fontWeight: 700,
                  color: c.title,
                }}
              >
                {row.value}
              </Typography>
            </Box>
          );
        })}
      </Box>
    </Panel>
  );
}
