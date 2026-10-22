import React, { useEffect, useState } from "react";
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
import { getTopOperators } from "../../../../utils/api";

/*
 * Loads from the API and refreshes every 10 seconds.
 * Pass `data` ([{ id, active, idle, away, util }]) to override the API.
 */
export default function TopOperators({ data, onViewAll }) {
    const c = useDashboardColors();
    const [rows, setRows] = useState([]);

    useEffect(() => {
        if (data) return undefined;

        let active = true;

        const load = async () => {
            try {
                const res = await getTopOperators();
                if (active) {
                    setRows(
                        (res.operators || []).map((o) => ({
                            id: o.operator_id,
                            active: o.active_display,
                            idle: o.idle_display,
                            away: o.away_display,
                            util: `${Math.round(o.utilization_pct)}%`,
                        }))
                    );
                }
            } catch (err) {
                console.error("Failed to fetch top operators:", err);
            }
        };

        load();
        const intervalId = setInterval(load, 10000);

        return () => {
            active = false;
            clearInterval(intervalId);
        };
    }, [data]);

    const list = data ?? rows;

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
                        <TableCell sx={headCell} align="right">Active Time</TableCell>
                        <TableCell sx={headCell} align="right">Idle Time</TableCell>
                        <TableCell sx={headCell} align="right">Away Time</TableCell>
                        <TableCell sx={headCell} align="right">Utilization</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {list.map((row, i) => (
                        <TableRow key={row.id} hover>
                            <TableCell sx={{ ...bodyCell, color: c.muted }}>
                                {i + 1}
                            </TableCell>
                            <TableCell sx={{ ...bodyCell, fontWeight: 600, color: c.title }}>
                                {row.id}
                            </TableCell>
                            <TableCell sx={bodyCell} align="right">
                                {row.active}
                            </TableCell>
                            <TableCell sx={bodyCell} align="right">
                                {row.idle}
                            </TableCell>
                            <TableCell sx={bodyCell} align="right">
                                {row.away}
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