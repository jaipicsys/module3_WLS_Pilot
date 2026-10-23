
import React, { useState } from "react";
import {
  Box,
  Chip,
  Dialog,
  DialogContent,
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

const ALERTS = [
  {
    id: "ALERT-1",
    time: new Date().toISOString(),
    reason: "Rework",
    description:
      "Incorrect towel count reported during box packing. Additional towels are added or excess towels are removed to correct the count.",
    severity: "medium",
    evidenceUrl: "/alert_1_converted.mp4",
  },
];

const SEVERITY_COLOR = {
  high: "error",
  medium: "warning",
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
        description="Select an alert to review the recorded evidence."
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
                    <TableCell sx={{ fontWeight: 600 }}>
                      {alert.id}
                    </TableCell>

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

        <Dialog
          open={Boolean(selected)}
          onClose={handleClose}
          fullWidth
          maxWidth="md"
          slotProps={{
            paper: {
              sx: {
                borderRadius: 2,
                overflow: "hidden",
              },
            },
          }}
        >
          {selected && (
            <Box>
              <Stack
                direction="row"
                alignItems="center"
                justifyContent="space-between"
                sx={{ px: 2.5, py: 1.5 }}
              >
                <Box sx={{ minWidth: 0, pr: 2 }}>
                  <Typography variant="h6" fontWeight={600}>
                    Evidence
                  </Typography>

                  <Typography variant="body2" color="text.secondary">
                    {selected.id} · {selected.reason}
                  </Typography>
                </Box>

                <IconButton
                  onClick={handleClose}
                  aria-label="Close evidence"
                >
                  <CloseIcon />
                </IconButton>
              </Stack>

              <Divider />

              <DialogContent sx={{ p: { xs: 2, sm: 2.5 } }}>
                <Box
                  sx={{
                    bgcolor: "common.black",
                    borderRadius: 1.5,
                    overflow: "hidden",
                    aspectRatio: "16 / 9",
                  }}
                >
                  <video
                    key={selected.id}
                    src={selected.evidenceUrl}
                    controls
                    autoPlay
                    muted
                    playsInline
                    preload="auto"
                    onError={(e) => {
                      console.error(
                        "Video playback error:",
                        e.currentTarget.error
                      );
                      console.error("Video URL:", selected.evidenceUrl);
                    }}
                    style={{
                      width: "100%",
                      height: "100%",
                      display: "block",
                      objectFit: "contain",
                    }}
                  />
                </Box>

                <Stack spacing={2} sx={{ mt: 2.5 }}>
                  <Box>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                    >
                      Reason
                    </Typography>
                    <Typography>{selected.reason}</Typography>
                  </Box>

                  {/* <Box>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                    >
                      Description
                    </Typography>
                    <Typography>{selected.description}</Typography>
                  </Box> */}

                  <Stack
                    direction={{ xs: "column", sm: "row" }}
                    spacing={2}
                  >
                    <Box sx={{ flex: 1 }}>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                      >
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
                </Stack>
              </DialogContent>
            </Box>
          )}
        </Dialog>
      </Box>
    </>
  );
};

export default Alerts;
