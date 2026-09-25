import React from "react";
import { Box, Typography } from "@mui/material";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import Panel from "../../Overview/Panel/Panel";
import useDashboardColors from "../../Overview/Tokens/Tokens";

const DEFAULT_DATA = [
  { label: "Incorrect Folding", pct: 42, color: "#ef4444" },
  { label: "Missing Packing Tag", pct: 18, color: "#f59e0b" },
  { label: "Incorrect Count", pct: 16, color: "#eab308" },
  { label: "Wrong Sequence", pct: 12, color: "#f97316" },
  { label: "Seal Not Applied", pct: 8, color: "#a89b91" },
  { label: "Others", pct: 4, color: "#cbc6c0" },
];

export default function DeviationCategories({
  data = DEFAULT_DATA,
  centerValue = "100",
  centerLabel = "Non-Compliant Cycles",
  height = 300,
}) {
  const c = useDashboardColors();

  return (
    <Panel title="Deviation Categories" sx={{ minHeight: height }}>
      <Box
        sx={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          gap: 2,
          flexWrap: "wrap",
        }}
      >
        {/* Donut */}
        <Box
          sx={{ position: "relative", width: 170, height: 170, flexShrink: 0 }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="pct"
                nameKey="label"
                innerRadius={55}
                outerRadius={80}
                paddingAngle={2}
                startAngle={90}
                endAngle={-270}
                stroke="none"
              >
                {data.map((r) => (
                  <Cell key={r.label} fill={r.color} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>

          <Box
            sx={{
              position: "absolute",
              inset: 0,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              pointerEvents: "none",
              px: 2,
              textAlign: "center",
            }}
          >
            <Typography sx={{ fontSize: 26, fontWeight: 800, color: c.title }}>
              {centerValue}
            </Typography>
            <Typography
              sx={{ fontSize: 10.5, color: c.muted, lineHeight: 1.2 }}
            >
              {centerLabel}
            </Typography>
          </Box>
        </Box>

        {/* Legend */}
        <Box
          sx={{
            flex: 1,
            minWidth: 170,
            display: "flex",
            flexDirection: "column",
            gap: 1,
          }}
        >
          {data.map((r) => (
            <Box
              key={r.label}
              sx={{ display: "flex", alignItems: "center", gap: 1 }}
            >
              <Box
                sx={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  bgcolor: r.color,
                  flexShrink: 0,
                }}
              />
              <Typography sx={{ flex: 1, fontSize: 12.5, color: c.text }}>
                {r.label}
              </Typography>
              <Typography
                sx={{ fontSize: 12.5, fontWeight: 700, color: c.title }}
              >
                {r.pct}%
              </Typography>
            </Box>
          ))}
        </Box>
      </Box>
    </Panel>
  );
}
