import React, { useEffect, useState } from "react";
import { Box, Typography } from "@mui/material";
import Panel from "../Panel/Panel";
import useDashboardColors from "../Tokens/Tokens";
import { getLossBreakdown } from "../../../../utils/api";

/*
 * rows: { label, pct, amount, color }  (pct drives bar width + shown in the label)
 * Loads idle + away reasons from the API and refreshes every 10 seconds.
 * Pass `data` to override the API.
 */
export default function LossBreakdown({ data, mode = "live" }) {
  const c = useDashboardColors();
  const [items, setItems] = useState([]);

  useEffect(() => {
    if (data) return undefined;

    let active = true;
    setItems([]); // clear the other mode's data

    const load = async () => {
      try {
        const res = await getLossBreakdown(mode);
        if (active) {
          setItems(
            (res.items || []).map((item) => ({
              label: item.label,
              pct: Math.round(item.pct),
              amount: item.display,
            })),
          );
        }
      } catch (err) {
        console.error("Failed to fetch loss breakdown:", err);
      }
    };

    load();
    const intervalId = setInterval(load, 10000);

    return () => {
      active = false;
      clearInterval(intervalId);
    };
  }, [data, mode]);

  const palette = ["#f0563a", c.orange, "#f47a4e", "#f89b78"];
  const rows =
    data ||
    items.map((row, i) => ({
      ...row,
      color: row.label.toLowerCase().startsWith("other")
        ? c.gray
        : palette[Math.min(i, palette.length - 1)],
    }));
  const max = Math.max(...rows.map((r) => r.pct), 1);

  return (
    <Panel title="Loss Breakdown">
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1.75 }}>
        {rows.map((row) => (
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
                  bgcolor: row.color,
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
