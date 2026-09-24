import React from "react";
import {
    Table,
    TableHead,
    TableBody,
    TableRow,
    TableCell,
    Box,
    Typography,
} from "@mui/material";
import Panel from "../Panel/Panel";
import useDashboardColors from "../Tokens/Tokens";

const buildDefault = (c) => [
    {
        time: "13:42",
        station: "Line 1 – Packing",
        event: "Idle Start",
        color: c.orange,
        details: "No activity detected",
    },
    {
        time: "13:36",
        station: "Line 2 – Carton",
        event: "Changeover",
        color: "#7a1f1f",
        details: "Product change: Towel – Standard → Towel – Premium",
    },
    {
        time: "13:28",
        station: "Line 1 – Packing",
        event: "Output Update",
        color: c.green,
        details: "+20 units detected",
    },
    {
        time: "13:15",
        station: "Line 3 – Packing",
        event: "Material Waiting",
        color: c.red,
        details: "Waiting for cartons",
    },
    {
        time: "12:58",
        station: "Line 2 – Carton",
        event: "SOP Deviation",
        color: "#eab308",
        details: "Carton not sealed (1 occurrence)",
    },
];

export default function RecentEvents({ data, onViewAll }) {
    const c = useDashboardColors();
    const rows = data || buildDefault(c);

    const headCell = {
        fontSize: 11.5,
        fontWeight: 600,
        color: c.muted,
        borderBottom: `1px solid ${c.cardBorder}`,
        py: 1,
    };
    const bodyCell = {
        fontSize: 13,
        color: c.text,
        borderBottom: `1px solid ${c.cardBorder}`,
        py: 1,
        verticalAlign: "top",
    };

    return (
        <Panel title="Recent Events" action="View All Events" onActionClick={onViewAll}>
            <Table size="small" sx={{ "& td, & th": { px: 1 } }}>
                <TableHead>
                    <TableRow>
                        <TableCell sx={{ ...headCell, width: 60 }}>Time</TableCell>
                        <TableCell sx={headCell}>Station</TableCell>
                        <TableCell sx={headCell}>Event</TableCell>
                        <TableCell sx={headCell}>Details</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {rows.map((row, i) => (
                        <TableRow key={i} hover>
                            <TableCell sx={{ ...bodyCell, color: c.muted }}>
                                {row.time}
                            </TableCell>
                            <TableCell sx={bodyCell}>{row.station}</TableCell>
                            <TableCell sx={bodyCell}>
                                <Box
                                    sx={{
                                        display: "flex",
                                        alignItems: "center",
                                        gap: 0.75,
                                    }}
                                >
                                    <Box
                                        sx={{
                                            width: 9,
                                            height: 9,
                                            borderRadius: "50%",
                                            bgcolor: row.color,
                                            flexShrink: 0,
                                        }}
                                    />
                                    {row.event}
                                </Box>
                            </TableCell>
                            <TableCell sx={{ ...bodyCell, color: c.muted }}>
                                {row.details}
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </Panel>
    );
}