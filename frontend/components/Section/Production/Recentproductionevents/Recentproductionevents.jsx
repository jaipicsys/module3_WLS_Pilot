import React from "react";
import {
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  Box,
} from "@mui/material";
import Panel from "../../Overview/Panel/Panel";
import useDashboardColors from "../../Overview/Tokens/Tokens";

const buildDefault = (c) => [
  {
    time: "13:42",
    line: "Line 1 – Packing",
    product: "Towel – Standard",
    event: "Output Update",
    color: c.green,
    details: "+20 units detected",
  },
  {
    time: "13:28",
    line: "Line 2 – Carton",
    product: "Towel – Premium",
    event: "Changeover",
    color: c.accent,
    details: "Product change: Standard → Premium",
  },
  {
    time: "13:15",
    line: "Line 3 – Packing",
    product: "Hand Towel",
    event: "Idle Start",
    color: c.orange,
    details: "Waiting for cartons",
  },
  {
    time: "12:58",
    line: "Line 1 – Packing",
    product: "Towel – Standard",
    event: "Output Update",
    color: c.gray,
    details: "+25 units detected",
  },
  {
    time: "12:36",
    line: "Line 2 – Carton",
    product: "Bath Towel",
    event: "QC Hold",
    color: c.red,
    details: "Quality check (5 minutes)",
  },
  {
    time: "12:10",
    line: "Line 3 – Packing",
    product: "Towel – Premium",
    event: "Output Update",
    color: c.green,
    details: "+18 units detected",
  },
];

export default function RecentProductionEvents({ data, onViewAll }) {
  const c = useDashboardColors();
  const rows = data || buildDefault(c);

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
    py: 1,
  };

  return (
    <Panel
      title="Recent Production Events"
      action="View All"
      onActionClick={onViewAll}
    >
      <Box sx={{ overflowX: "auto" }}>
        <Table size="small" sx={{ "& td, & th": { px: 1 }, minWidth: 560 }}>
          <TableHead>
            <TableRow>
              <TableCell sx={{ ...headCell, width: 52 }}>Time</TableCell>
              <TableCell sx={headCell}>Line / Station</TableCell>
              <TableCell sx={headCell}>Product</TableCell>
              <TableCell sx={headCell}>Event</TableCell>
              <TableCell sx={headCell}>Details</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((r, i) => (
              <TableRow key={i} hover>
                <TableCell sx={{ ...bodyCell, color: c.muted }}>
                  {r.time}
                </TableCell>
                <TableCell sx={bodyCell}>{r.line}</TableCell>
                <TableCell sx={bodyCell}>{r.product}</TableCell>
                <TableCell sx={bodyCell}>
                  <Box
                    sx={{ display: "flex", alignItems: "center", gap: 0.75 }}
                  >
                    <Box
                      sx={{
                        width: 9,
                        height: 9,
                        borderRadius: "50%",
                        bgcolor: r.color,
                        flexShrink: 0,
                      }}
                    />
                    {r.event}
                  </Box>
                </TableCell>
                <TableCell sx={{ ...bodyCell, color: c.muted }}>
                  {r.details}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
    </Panel>
  );
}
