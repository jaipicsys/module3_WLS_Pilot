import React from "react";
import { Box, Typography } from "@mui/material";
import Panel from "../../Overview/Panel/Panel";
import useDashboardColors, { barShades } from "../../Overview/Tokens/Tokens";

const DEFAULT_DATA = [
    { label: "OP-104", value: 220 },
    { label: "OP-087", value: 198 },
    { label: "OP-118", value: 186 },
    { label: "OP-095", value: 148 },
    { label: "OP-132", value: 142 },
];

export default function OutputByOperator({ data = DEFAULT_DATA, onViewAll }) {
    const c = useDashboardColors();
    const max = Math.max(...data.map((d) => d.value), 1);

    return (
        <Panel title="Output by Operator (Top 5)" action="View All" onActionClick={onViewAll}>
            <Box sx={{ display: "flex", flexDirection: "column", gap: 1.75 }}>
                {data.map((row, i) => (
                    <Box key={row.label} sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                        <Typography
                            sx={{ width: 56, flexShrink: 0, fontSize: 12.5, fontWeight: 600, color: c.text }}
                        >
                            {row.label}
                        </Typography>

                        <Box
                            sx={{
                                flex: 1,
                                height: 22,
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
                                    bgcolor: barShades[Math.min(i, barShades.length - 1)],
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
                ))}
            </Box>
        </Panel>
    );
}