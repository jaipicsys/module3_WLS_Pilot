import React from "react";
import { Box, Typography } from "@mui/material";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import Panel from "../../Overview/Panel/Panel";
import useDashboardColors from "../../Overview/Tokens/Tokens";

const DEFAULT_DATA = [
  {
    title: "Daily Production Report",
    detail: "Output, efficiency, losses",
    color: "#ef5323",
  },
  {
    title: "Operator Performance Report",
    detail: "Individual & team performance",
    color: "#8b5cf6",
  },
  {
    title: "Loss Analysis Report",
    detail: "Idle time, reasons, trends",
    color: "#ef4444",
  },
  {
    title: "SOP Compliance Report",
    detail: "Adherence, deviations",
    color: "#12b76a",
  },
  {
    title: "Shift Comparison Report",
    detail: "Compare performance across shifts",
    color: "#f59e0b",
  },
  {
    title: "Custom Report",
    detail: "Configure and download",
    color: "#9ca3af",
  },
];

export default function QuickReports({ data = DEFAULT_DATA, onSelect }) {
  const c = useDashboardColors();

  return (
    <Panel title="Quick Reports">
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
        {data.map((r) => (
          <Box
            key={r.title}
            onClick={() => onSelect?.(r)}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1.25,
              p: 1,
              borderRadius: "10px",
              border: `1px solid ${c.cardBorder}`,
              cursor: "pointer",
              transition: "background-color 0.15s",
              "&:hover": { bgcolor: c.track },
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
              <DescriptionOutlinedIcon />
            </Box>

            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography
                sx={{ fontSize: 13, fontWeight: 700, color: c.title }}
              >
                {r.title}
              </Typography>
              <Typography sx={{ fontSize: 11.5, color: c.muted }}>
                {r.detail}
              </Typography>
            </Box>

            <ChevronRightIcon
              sx={{ fontSize: 20, color: c.muted, flexShrink: 0 }}
            />
          </Box>
        ))}
      </Box>
    </Panel>
  );
}
