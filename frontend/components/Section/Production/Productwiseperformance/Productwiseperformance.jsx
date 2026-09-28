import React from "react";
import {
    Table,
    TableHead,
    TableBody,
    TableRow,
    TableCell,
} from "@mui/material";
import Panel from "../../Overview/Panel/Panel";
import useDashboardColors from "../../Overview/Tokens/Tokens";

const DEFAULT_DATA = [
    { product: "Towel – Standard", target: 500, actual: 520, achievement: 104, eff: "92%", cycle: "26 sec" },
    { product: "Towel – Premium", target: 300, actual: 310, achievement: 103, eff: "89%", cycle: "28 sec" },
    { product: "Hand Towel", target: 200, actual: 198, achievement: 99, eff: "86%", cycle: "30 sec" },
    { product: "Bath Towel", target: 150, actual: 150, achievement: 100, eff: "84%", cycle: "32 sec" },
    { product: "Others", target: 80, actual: 70, achievement: 88, eff: "76%", cycle: "35 sec" },
];

export default function ProductWisePerformance({ data = DEFAULT_DATA }) {
    const c = useDashboardColors();

    const achievementColor = (v) => (v >= 95 ? c.green : v >= 90 ? c.orange : c.red);

    const headCell = {
        fontSize: 11.5,
        fontWeight: 600,
        color: c.muted,
        borderBottom: `1px solid ${c.cardBorder}`,
        py: 1.1,
        whiteSpace: "nowrap",
    };
    const bodyCell = {
        fontSize: 12.5,
        color: c.text,
        borderBottom: `1px solid ${c.cardBorder}`,
        py: 1.1,
        whiteSpace: "nowrap",
    };

    return (
        <Panel title="Product-wise Performance">
            <Table size="small" sx={{ "& td, & th": { px: 1 } }}>
                <TableHead>
                    <TableRow>
                        <TableCell sx={{ ...headCell, width: 28 }}>#</TableCell>
                        <TableCell sx={headCell}>Product</TableCell>
                        <TableCell sx={headCell} align="right">Target</TableCell>
                        <TableCell sx={headCell} align="right">Actual Output</TableCell>
                        <TableCell sx={headCell} align="right">Achievement</TableCell>
                        <TableCell sx={headCell} align="right">Efficiency</TableCell>
                        <TableCell sx={headCell} align="right">Avg. Cycle Time</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {data.map((r, i) => (
                        <TableRow key={r.product} hover>
                            <TableCell sx={{ ...bodyCell, color: c.muted }}>{i + 1}</TableCell>
                            <TableCell sx={{ ...bodyCell, fontWeight: 600, color: c.title }}>
                                {r.product}
                            </TableCell>
                            <TableCell sx={bodyCell} align="right">{r.target}</TableCell>
                            <TableCell sx={bodyCell} align="right">{r.actual}</TableCell>
                            <TableCell
                                sx={{
                                    ...bodyCell,
                                    fontWeight: 700,
                                    color: achievementColor(r.achievement),
                                }}
                                align="right"
                            >
                                {r.achievement}%
                            </TableCell>
                            <TableCell sx={bodyCell} align="right">{r.eff}</TableCell>
                            <TableCell sx={bodyCell} align="right">{r.cycle}</TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </Panel>
    );
}