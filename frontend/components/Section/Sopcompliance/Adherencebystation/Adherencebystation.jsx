import React from "react";
import { Box, Typography } from "@mui/material";
import Panel from "../../Overview/Panel/Panel";
import useDashboardColors from "../../Overview/Tokens/Tokens";

const DEFAULT_DATA = [
  { label: "Line 1 – Packing 1", pct: 96 },
  { label: "Line 1 – Packing 2", pct: 91 },
  { label: "Line 2 – Packing 1", pct: 86 },
  { label: "Line 2 – Packing 2", pct: 82 },
  { label: "Line 3 – Packing 1", pct: 78 },
  { label: "Line 3 – Packing 2", pct: 72 },
];

const greenShades = [
  "#0f9d63",
  "#19b26e",
  "#37c184",
  "#66d29e",
  "#9ce0bf",
  "#c6eed9",
];

export default function AdherenceByStation({
  data = DEFAULT_DATA,
  height = 320,
}) {
  const c = useDashboardColors();

  return (
    <Panel title="Adherence by Station" sx={{ minHeight: height }}>
      <Box
        sx={{
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          gap: 1.5,
        }}
      >
        {data.map((row, i) => (
          <Box
            key={row.label}
            sx={{ display: "flex", alignItems: "center", gap: 1.5 }}
          >
            <Typography
              sx={{ width: 118, flexShrink: 0, fontSize: 12, color: c.text }}
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
                  bgcolor: greenShades[Math.min(i, greenShades.length - 1)],
                  transition: "width 0.4s ease",
                }}
              />
            </Box>

            <Typography
              sx={{
                width: 34,
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
        ))}
      </Box>
    </Panel>
  );
}
