import React from "react";
import { Box, Typography } from "@mui/material";
import Panel from "../Panel/Panel";
import useDashboardColors from "../Tokens/Tokens";

/*
 * rows: { severity: "high" | "medium" | "low", title, detail, time }
 */
const DEFAULT_DATA = [
    {
        severity: "high",
        title: "Material shortfall at Line 2",
        detail: "No cartons available for 5+ minutes",
        time: "13:42",
    },
    {
        severity: "medium",
        title: "SOP deviation increasing",
        detail: "3 occurrences in last 30 minutes",
        time: "13:28",
    },
    {
        severity: "medium",
        title: "High operator idle time",
        detail: "OP-132 idle for 8+ minutes",
        time: "13:15",
    },
    {
        severity: "low",
        title: "Output below target",
        detail: "Line 3 at 75% of target",
        time: "12:50",
    },
];

export default function AlertsNotifications({ data = DEFAULT_DATA, onViewAll }) {
    const c = useDashboardColors();

    const dotColor = {
        high: c.red,
        medium: c.orange,
        low: "#eab308",
    };

    return (
        <Panel title="Alerts & Notifications" action="View All" onActionClick={onViewAll}>
            <Box sx={{ display: "flex", flexDirection: "column" }}>
                {data.map((row, i) => (
                    <Box
                        key={i}
                        sx={{
                            display: "flex",
                            alignItems: "flex-start",
                            gap: 1.25,
                            py: 1.25,
                            borderBottom:
                                i < data.length - 1
                                    ? `1px solid ${c.cardBorder}`
                                    : "none",
                        }}
                    >
                        <Box
                            sx={{
                                mt: "5px",
                                width: 9,
                                height: 9,
                                borderRadius: "50%",
                                bgcolor: dotColor[row.severity] || c.gray,
                                flexShrink: 0,
                            }}
                        />

                        <Box sx={{ flex: 1, minWidth: 0 }}>
                            <Typography
                                sx={{
                                    fontSize: 13,
                                    fontWeight: 700,
                                    color: c.title,
                                }}
                            >
                                {row.title}
                            </Typography>
                            <Typography sx={{ fontSize: 12, color: c.muted }}>
                                {row.detail}
                            </Typography>
                        </Box>

                        <Typography
                            sx={{ fontSize: 12, color: c.muted, flexShrink: 0 }}
                        >
                            {row.time}
                        </Typography>
                    </Box>
                ))}
            </Box>
        </Panel>
    );
}