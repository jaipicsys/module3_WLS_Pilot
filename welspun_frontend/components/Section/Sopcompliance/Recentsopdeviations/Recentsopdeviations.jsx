import React from "react";
import {
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  Link,
} from "@mui/material";
import Panel from "../../Overview/Panel/Panel";
import useDashboardColors from "../../Overview/Tokens/Tokens"

const DEFAULT_DATA = [
  {
    time: "13:39",
    station: "Line 1",
    operator: "OP-132",
    deviation: "Towel not folded as per sequence",
  },
  {
    time: "12:54",
    station: "Line 2",
    operator: "OP-095",
    deviation: "Incorrect stacking count",
  },
  {
    time: "11:46",
    station: "Line 1",
    operator: "OP-118",
    deviation: "Missing packing tag",
  },
  {
    time: "10:32",
    station: "Line 3",
    operator: "OP-076",
    deviation: "Wrapper placed in pack",
  },
  {
    time: "09:15",
    station: "Line 1",
    operator: "OP-104",
    deviation: "Seal not applied",
  },
];

export default function RecentSopDeviations({
  data = DEFAULT_DATA,
  onViewAll,
  onView,
}) {
  const c = useDashboardColors();

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
      title="Recent SOP Deviations"
      action="View All"
      onActionClick={onViewAll}
    >
      <Table size="small" sx={{ "& td, & th": { px: 1 } }}>
        <TableHead>
          <TableRow>
            <TableCell sx={{ ...headCell, width: 52 }}>Time</TableCell>
            <TableCell sx={headCell}>Station</TableCell>
            <TableCell sx={headCell}>Operator</TableCell>
            <TableCell sx={headCell}>Deviation</TableCell>
            <TableCell sx={headCell} align="right">
              Video
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data.map((r, i) => (
            <TableRow key={i} hover>
              <TableCell sx={{ ...bodyCell, color: c.muted }}>
                {r.time}
              </TableCell>
              <TableCell sx={bodyCell}>{r.station}</TableCell>
              <TableCell sx={{ ...bodyCell, fontWeight: 600, color: c.title }}>
                {r.operator}
              </TableCell>
              <TableCell sx={bodyCell}>{r.deviation}</TableCell>
              <TableCell sx={bodyCell} align="right">
                <Link
                  component="button"
                  type="button"
                  underline="hover"
                  onClick={() => onView?.(r)}
                  sx={{ fontSize: 12.5, fontWeight: 600, color: c.accent }}
                >
                  View
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Panel>
  );
}
