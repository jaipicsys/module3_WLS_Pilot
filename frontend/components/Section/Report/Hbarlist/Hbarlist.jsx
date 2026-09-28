import React from "react";
import { Box, Typography } from "@mui/material";
import Panel from "../../Overview/Panel/Panel";
import useDashboardColors from "../../Overview/Tokens/Tokens";

/*
 * Generic labelled horizontal bar list.
 *
 * Props:
 *   title, action, onActionClick   panel header
 *   rows: [{ label, display, pct (0-100 width), color }]
 *   labelWidth, valueWidth, barHeight, gap   layout tuning
 */
export default function HBarList({
  title,
  action,
  onActionClick,
  rows = [],
  labelWidth = 110,
  valueWidth = 64,
  barHeight = 20,
  gap = 1.75,
}) {
  const c = useDashboardColors();

  return (
    <Panel title={title} action={action} onActionClick={onActionClick}>
      <Box sx={{ display: "flex", flexDirection: "column", gap }}>
        {rows.map((row) => (
          <Box
            key={row.label}
            sx={{ display: "flex", alignItems: "center", gap: 1.5 }}
          >
            <Typography
              sx={{
                width: labelWidth,
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
                height: barHeight,
                borderRadius: "4px",
                bgcolor: c.track,
                overflow: "hidden",
              }}
            >
              <Box
                sx={{
                  width: `${Math.min(row.pct, 100)}%`,
                  height: "100%",
                  borderRadius: "4px",
                  bgcolor: row.color,
                  transition: "width 0.4s ease",
                }}
              />
            </Box>

            <Typography
              sx={{
                width: valueWidth,
                flexShrink: 0,
                textAlign: "right",
                fontSize: 12.5,
                fontWeight: 700,
                color: c.title,
              }}
            >
              {row.display}
            </Typography>
          </Box>
        ))}
      </Box>
    </Panel>
  );
}
