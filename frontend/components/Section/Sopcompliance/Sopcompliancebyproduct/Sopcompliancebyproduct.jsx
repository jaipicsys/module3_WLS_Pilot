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
  {
    product: "Towel – Standard",
    total: 520,
    compliant: 492,
    nonCompliant: 28,
    adherence: 95,
  },
  {
    product: "Towel – Premium",
    total: 310,
    compliant: 281,
    nonCompliant: 29,
    adherence: 91,
  },
  {
    product: "Hand Towel",
    total: 198,
    compliant: 170,
    nonCompliant: 28,
    adherence: 86,
  },
  {
    product: "Bath Towel",
    total: 150,
    compliant: 123,
    nonCompliant: 27,
    adherence: 82,
  },
  {
    product: "Others",
    total: 70,
    compliant: 50,
    nonCompliant: 20,
    adherence: 71,
  },
];

export default function SopComplianceByProduct({ data = DEFAULT_DATA }) {
  const c = useDashboardColors();

  const adherenceColor = (v) =>
    v >= 90 ? c.green : v >= 80 ? c.orange : c.red;

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
  };

  return (
    <Panel title="SOP Compliance by Product">
      <Table size="small" sx={{ "& td, & th": { px: 1 } }}>
        <TableHead>
          <TableRow>
            <TableCell sx={headCell}>Product</TableCell>
            <TableCell sx={headCell} align="right">
              Total Cycles
            </TableCell>
            <TableCell sx={headCell} align="right">
              Compliant Cycles
            </TableCell>
            <TableCell sx={headCell} align="right">
              Non-Compliant Cycles
            </TableCell>
            <TableCell sx={headCell} align="right">
              SOP Adherence
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data.map((r) => (
            <TableRow key={r.product} hover>
              <TableCell sx={{ ...bodyCell, fontWeight: 600, color: c.title }}>
                {r.product}
              </TableCell>
              <TableCell sx={bodyCell} align="right">
                {r.total}
              </TableCell>
              <TableCell sx={bodyCell} align="right">
                {r.compliant}
              </TableCell>
              <TableCell sx={bodyCell} align="right">
                {r.nonCompliant}
              </TableCell>
              <TableCell
                sx={{
                  ...bodyCell,
                  fontWeight: 700,
                  color: adherenceColor(r.adherence),
                }}
                align="right"
              >
                {r.adherence}%
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Panel>
  );
}
