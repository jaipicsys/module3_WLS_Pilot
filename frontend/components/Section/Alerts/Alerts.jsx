import React, { useState } from "react";
import {
  Box,
  Chip,
  Drawer,
  IconButton,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
  Button,
  Divider,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import PlayCircleOutlineIcon from "@mui/icons-material/PlayCircleOutline";
import Header from "../../Layout/Header/Header";

// TODO: replace with API data
const ALERTS = [
  {
    id: "ALT-1042",
    time: "2026-10-22T09:14:32",
    reason: "Unauthorized person detected in restricted zone",
    severity: "critical",
    evidenceUrl: "https://www.w3schools.com/html/mov_bbb.mp4",
  },
  {
    id: "ALT-1041",
    time: "2026-10-22T08:57:10",
    reason: "Safety helmet not worn",
    severity: "high",
    evidenceUrl: "https://www.w3schools.com/html/mov_bbb.mp4",
  },
  {
    id: "ALT-1040",
    time: "2026-10-22T08:31:45",
    reason: "Vehicle parked in no-parking area",
    severity: "medium",
    evidenceUrl: "https://www.w3schools.com/html/mov_bbb.mp4",
  },
  {
    id: "ALT-1039",
    time: "2026-10-21T22:03:19",
    reason: "Camera feed lost for 30 seconds",
    severity: "low",
    evidenceUrl: "https://www.w3schools.com/html/mov_bbb.mp4",
  },
];

const SEVERITY_COLOR = {
  critical: "error",
  high: "warning",
  medium: "info",
  low: "success",
};

const formatTime = (iso) =>
  new Date(iso).toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

const SeverityChip = ({ severity }) => (
  <Chip
    size="small"
    label={severity.charAt(0).toUpperCase() + severity.slice(1)}
    color={SEVERITY_COLOR[severity] || "default"}
    variant="outlined"
    sx={{ fontWeight: 600 }}
  />
);

const Alerts = () => {
  const [selected, setSelected] = useState(null);

  const handleClose = () => setSelected(null);

  return (
    <>
      <Header
        title="Alerts"
        description="Select evidence to review the recorded footage for an alerts"
      />
      <Box sx={{ p: { xs: 2, md: 3 } }}>
        <TableContainer component={Paper} variant="outlined">
          <Table size="medium">
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>Time</TableCell>
                <TableCell>Reason</TableCell>
                <TableCell>Severity</TableCell>
                <TableCell align="right">Evidence</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {ALERTS.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} align="center" sx={{ py: 6 }}>
                    <Typography color="text.secondary">
                      No alerts yet.
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                ALERTS.map((alert) => (
                  <TableRow key={alert.id} hover>
                    <TableCell sx={{ fontWeight: 600 }}>{alert.id}</TableCell>
                    <TableCell sx={{ whiteSpace: "nowrap" }}>
                      {formatTime(alert.time)}
                    </TableCell>
                    <TableCell>{alert.reason}</TableCell>
                    <TableCell>
                      <SeverityChip severity={alert.severity} />
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="View evidence video">
                        <Button
                          size="small"
                          startIcon={<PlayCircleOutlineIcon />}
                          onClick={() => setSelected(alert)}
                        >
                          View
                        </Button>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>

        <Drawer
          anchor="right"
          open={Boolean(selected)}
          onClose={handleClose}
          PaperProps={{ sx: { width: { xs: "100%", sm: 480, md: 560 } } }}
        >
          {selected && (
            <Box
              sx={{ display: "flex", flexDirection: "column", height: "100%" }}
            >
              <Stack
                direction="row"
                alignItems="center"
                justifyContent="space-between"
                sx={{ px: 2, py: 1.5 }}
              >
                <Box>
                  <Typography variant="h6" fontWeight={600}>
                    Evidence
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {selected.id}
                  </Typography>
                </Box>
                <IconButton onClick={handleClose} aria-label="Close evidence">
                  <CloseIcon />
                </IconButton>
              </Stack>

              <Divider />

              <Box sx={{ p: 2 }}>
                <Box
                  sx={{
                    bgcolor: "common.black",
                    borderRadius: 1,
                    overflow: "hidden",
                    aspectRatio: "16 / 9",
                  }}
                >
                  <video
                    key={selected.id}
                    src={selected.evidenceUrl}
                    controls
                    autoPlay
                    style={{ width: "100%", height: "100%", display: "block" }}
                  />
                </Box>

                <Stack spacing={2} sx={{ mt: 3 }}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Reason
                    </Typography>
                    <Typography>{selected.reason}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Time
                    </Typography>
                    <Typography>{formatTime(selected.time)}</Typography>
                  </Box>
                  <Box>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      component="div"
                      sx={{ mb: 0.5 }}
                    >
                      Severity
                    </Typography>
                    <SeverityChip severity={selected.severity} />
                  </Box>
                </Stack>
              </Box>
            </Box>
          )}
        </Drawer>
      </Box>
    </>
  );
};

export default Alerts;
