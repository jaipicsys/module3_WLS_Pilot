import React from "react";
import { Box, Typography } from "@mui/material";
import Panel from "../Panel/Panel";
import useDashboardColors from "../Tokens/Tokens";

/*
 * rows: { label, pct, amount }  (pct drives bar width + shown in the label)
 */
const buildDefault = (c) => [
    { label: "Material Waiting", pct: 41, amount: "32m", color: "#f0563a" },
    { label: "QC Waiting", pct: 23, amount: "18m", color: c.orange },
    { label: "Changeover", pct: 21, amount: "16m", color: "#f47a4e" },
    { label: "Personal Break", pct: 10, amount: "8m", color: "#f89b78" },
    { label: "Others", pct: 5, amount: "4m", color: c.gray },
];

export default function LossBreakdown({ data }) {
    const c = useDashboardColors();
    const rows = data || buildDefault(c);
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
                                width: 100,
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
                                width: 78,
                                flexShrink: 0,
                                textAlign: "right",
                                fontSize: 12,
                                fontWeight: 600,
                                color: c.muted,
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