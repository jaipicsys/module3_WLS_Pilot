import React from "react";
import {
    Table,
    TableHead,
    TableBody,
    TableRow,
    TableCell,
    Typography,
} from "@mui/material";
import Panel from "../Panel/Panel";
import useDashboardColors from "../Tokens/Tokens";

const DEFAULT_DATA = [
    { id: "OP-104", output: 220, eff: "94%", util: "86%" },
    { id: "OP-087", output: 198, eff: "91%", util: "82%" },
    { id: "OP-118", output: 186, eff: "89%", util: "78%" },
    { id: "OP-132", output: 162, eff: "87%", util: "76%" },
    { id: "OP-095", output: 148, eff: "84%", util: "72%" },
];

export default function TopOperators({ data = DEFAULT_DATA, onViewAll }) {
    const c = useDashboardColors();

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
    };

    return (
        <Panel title="Top Operators by Output" action="View All" onActionClick={onViewAll}>
            <Table size="small" sx={{ "& td, & th": { px: 1 } }}>
                <TableHead>
                    <TableRow>
                        <TableCell sx={{ ...headCell, width: 32 }}>#</TableCell>
                        <TableCell sx={headCell}>Operator ID</TableCell>
                        <TableCell sx={headCell} align="right">Output</TableCell>
                        <TableCell sx={headCell} align="right">Efficiency</TableCell>
                        <TableCell sx={headCell} align="right">Utilization</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {data.map((row, i) => (
                        <TableRow key={row.id} hover>
                            <TableCell sx={{ ...bodyCell, color: c.muted }}>
                                {i + 1}
                            </TableCell>
                            <TableCell sx={{ ...bodyCell, fontWeight: 600, color: c.title }}>
                                {row.id}
                            </TableCell>
                            <TableCell sx={bodyCell} align="right">
                                {row.output}
                            </TableCell>
                            <TableCell sx={bodyCell} align="right">
                                {row.eff}
                            </TableCell>
                            <TableCell sx={bodyCell} align="right">
                                {row.util}
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </Panel>
    );
}