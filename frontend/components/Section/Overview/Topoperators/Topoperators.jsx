import React from "react";
import {
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
} from "@mui/material";
import Panel from "../Panel/Panel";
import useDashboardColors from "../Tokens/Tokens";

/* Static operator rows */
const ROWS = [
  { id: "OP7", active: "29m 42s", idle: "0s", away: "11s", util: "99%" },
  { id: "OP6", active: "29m 31s", idle: "0s", away: "22s", util: "99%" },
  { id: "OP5", active: "24m 11s", idle: "2m 2s", away: "3m 41s", util: "81%" },
  { id: "OP4", active: "20m 26s", idle: "6m 28s", away: "2m 59s", util: "68%" },
  { id: "OP3", active: "17m 14s", idle: "3m 57s", away: "8m 37s", util: "58%" },
  { id: "OP1", active: "16m 51s", idle: "4m 58s", away: "8m 2s", util: "57%" },
  { id: "OP2", active: "15m 53s", idle: "8m 31s", away: "5m 28s", util: "53%" },
];

export default function TopOperators({ onViewAll }) {
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
    <Panel title="Top Operators" action="View All" onActionClick={onViewAll}>
      <Table size="small" sx={{ "& td, & th": { px: 1 } }}>
        <TableHead>
          <TableRow>
            <TableCell sx={{ ...headCell, width: 32 }}>#</TableCell>
            <TableCell sx={headCell}>Operator ID</TableCell>
            <TableCell sx={headCell} align="right">
              Active Time
            </TableCell>
            <TableCell sx={headCell} align="right">
              Idle Time
            </TableCell>
            <TableCell sx={headCell} align="right">
              Away Time
            </TableCell>
            <TableCell sx={headCell} align="right">
              Utilization
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {ROWS.map((row, i) => (
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
