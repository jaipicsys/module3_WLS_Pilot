import React, { useMemo, useState } from "react";
import {
    Box,
    Table,
    TableHead,
    TableBody,
    TableRow,
    TableCell,
    TextField,
    InputAdornment,
    Button,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import FileDownloadOutlinedIcon from "@mui/icons-material/FileDownloadOutlined";
import Panel from "../../Overview/Panel/Panel";
import useDashboardColors from "../../Overview/Tokens/Tokens";

const buildDefault = (c) => [
    { id: "OP-104", name: "Ramesh K.", line: "Line 1", product: "Towel – Standard", output: 220, eff: 94, util: 86, active: "6h 13m", idle: "1h 3m", status: c.green },
    { id: "OP-087", name: "Sunita P.", line: "Line 2", product: "Towel – Premium", output: 198, eff: 91, util: 82, active: "5h 48m", idle: "1h 16m", status: c.green },
    { id: "OP-118", name: "Amit S.", line: "Line 1", product: "Hand Towel", output: 186, eff: 89, util: 78, active: "5h 32m", idle: "1h 32m", status: c.green },
    { id: "OP-132", name: "Latha M.", line: "Line 3", product: "Bath Towel", output: 142, eff: 62, util: 68, active: "4h 18m", idle: "2h 46m", status: c.red },
    { id: "OP-095", name: "Vijay T.", line: "Line 2", product: "Towel – Standard", output: 148, eff: 84, util: 72, active: "5h 6m", idle: "1h 54m", status: c.green },
    { id: "OP-021", name: "Meena S.", line: "Line 1", product: "Towel – Premium", output: 176, eff: 87, util: 76, active: "5h 28m", idle: "1h 42m", status: c.green },
    { id: "OP-076", name: "Suresh V.", line: "Line 3", product: "Hand Towel", output: 160, eff: 82, util: 71, active: "5h 12m", idle: "2h 8m", status: c.green },
    { id: "OP-143", name: "Kavitha R.", line: "Line 2", product: "Towel – Standard", output: 154, eff: 79, util: 70, active: "4h 56m", idle: "2h 24m", status: c.orange },
    { id: "OP-067", name: "Arun N.", line: "Line 1", product: "Bath Towel", output: 138, eff: 76, util: 68, active: "4h 42m", idle: "2h 38m", status: c.orange },
    { id: "OP-119", name: "Divya K.", line: "Line 3", product: "Towel – Premium", output: 132, eff: 71, util: 66, active: "4h 36m", idle: "2h 44m", status: c.red },
];

export default function OperatorPerformanceTable({ data, onExport }) {
    const c = useDashboardColors();
    const rows = useMemo(() => data || buildDefault(c), [data, c]);
    const [query, setQuery] = useState("");

    const filtered = useMemo(() => {
        const q = query.trim().toLowerCase();
        if (!q) return rows;
        return rows.filter((r) =>
            [r.id, r.name, r.line, r.product, r.status]
                .join(" ")
                .toLowerCase()
                .includes(q)
        );
    }, [rows, query]);

    const headCell = {
        fontSize: 11.5,
        fontWeight: 600,
        color: c.muted,
        borderBottom: `1px solid ${c.cardBorder}`,
        py: 1,
        whiteSpace: "nowrap",
    };
    const bodyCell = {
        fontSize: 12.5,
        color: c.text,
        borderBottom: `1px solid ${c.cardBorder}`,
        py: 0.9,
        whiteSpace: "nowrap",
    };

    const headerRight = (
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <TextField
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                size="small"
                placeholder="Search operator, station…"
                InputProps={{
                    startAdornment: (
                        <InputAdornment position="start">
                            <SearchIcon sx={{ fontSize: 16, color: c.muted }} />
                        </InputAdornment>
                    ),
                }}
                sx={{
                    width: 220,
                    "& .MuiOutlinedInput-root": {
                        height: 34,
                        borderRadius: "8px",
                        fontSize: 12.5,
                        bgcolor: c.cardBg,
                    },
                    "& .MuiOutlinedInput-notchedOutline": {
                        borderColor: c.cardBorder,
                    },
                }}
            />
            <Button
                onClick={onExport}
                startIcon={<FileDownloadOutlinedIcon sx={{ fontSize: 16 }} />}
                sx={{
                    height: 34,
                    textTransform: "none",
                    fontSize: 12.5,
                    fontWeight: 600,
                    color: c.accent,
                    bgcolor: c.accentSoft,
                    borderRadius: "8px",
                    px: 1.5,
                    "&:hover": { bgcolor: c.accentSoft, filter: "brightness(0.97)" },
                }}
            >
                Export
            </Button>
        </Box>
    );

    return (
        <Panel title="Operator Performance" headerRight={headerRight}>
            <Box sx={{ overflowX: "auto" }}>
                <Table size="small" sx={{ "& td, & th": { px: 1 }, minWidth: 760 }}>
                    <TableHead>
                        <TableRow>
                            <TableCell sx={{ ...headCell, width: 28 }}>#</TableCell>
                            <TableCell sx={headCell}>Operator ID</TableCell>
                            <TableCell sx={headCell}>Name</TableCell>
                            <TableCell sx={headCell}>Station / Line</TableCell>
                            <TableCell sx={headCell}>Product</TableCell>
                            <TableCell sx={headCell} align="right">Output</TableCell>
                            <TableCell sx={headCell} align="right">Efficiency</TableCell>
                            <TableCell sx={headCell} align="right">Utilization</TableCell>
                            <TableCell sx={headCell}>Active Time</TableCell>
                            <TableCell sx={headCell}>Idle Time</TableCell>
                            <TableCell sx={headCell}>Status</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {filtered.map((r, i) => (
                            <TableRow key={r.id} hover>
                                <TableCell sx={{ ...bodyCell, color: c.muted }}>
                                    {i + 1}
                                </TableCell>
                                <TableCell sx={{ ...bodyCell, fontWeight: 600, color: c.title }}>
                                    {r.id}
                                </TableCell>
                                <TableCell sx={bodyCell}>{r.name}</TableCell>
                                <TableCell sx={bodyCell}>{r.line}</TableCell>
                                <TableCell sx={bodyCell}>{r.product}</TableCell>
                                <TableCell sx={bodyCell} align="right">{r.output}</TableCell>
                                <TableCell
                                    sx={{
                                        ...bodyCell,
                                        fontWeight: 600,
                                        color: r.eff < 70 ? c.red : c.text,
                                    }}
                                    align="right"
                                >
                                    {r.eff}%
                                </TableCell>
                                <TableCell sx={bodyCell} align="right">{r.util}%</TableCell>
                                <TableCell sx={bodyCell}>{r.active}</TableCell>
                                <TableCell sx={bodyCell}>{r.idle}</TableCell>
                                <TableCell sx={bodyCell}>
                                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
                                        <Box
                                            sx={{
                                                width: 8,
                                                height: 8,
                                                borderRadius: "50%",
                                                bgcolor: r.status,
                                            }}
                                        />
                                        Active
                                    </Box>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </Box>
        </Panel>
    );
}