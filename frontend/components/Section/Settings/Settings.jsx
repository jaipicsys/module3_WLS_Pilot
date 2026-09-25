import React, { useEffect, useState } from "react";
import {
    Box,
    Card,
    CardContent,
    Typography,
    Grid,
    TextField,
    Button,
    CircularProgress,
    Alert,
    IconButton,
    Stack,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
} from "@mui/material";
import { Add, Delete } from "@mui/icons-material";
import { fetchConfigData, updateConfigData } from "../../../utils/api";

const Settings = () => {
    const [config, setConfig] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState(null);

    // Dialog states
    const [addRtspDialogOpen, setAddRtspDialogOpen] = useState(false);
    const [newRtspKey, setNewRtspKey] = useState("");
    const [newRtspValue, setNewRtspValue] = useState("");
    const [deleteRtspDialogOpen, setDeleteRtspDialogOpen] = useState(false);
    const [rtspKeyToDelete, setRtspKeyToDelete] = useState(null);

    const [addLineDialogOpen, setAddLineDialogOpen] = useState(false);
    const [newLineKey, setNewLineKey] = useState("");
    const [addStationDialogOpen, setAddStationDialogOpen] = useState(false);
    const [newStationKey, setNewStationKey] = useState("");
    const [currentLineKey, setCurrentLineKey] = useState("");

    const [addOperationDialogOpen, setAddOperationDialogOpen] = useState(false);
    const [newOperationKey, setNewOperationKey] = useState("");
    const [addStepDialogOpen, setAddStepDialogOpen] = useState(false);
    const [currentOperationKey, setCurrentOperationKey] = useState("");

    useEffect(() => {
        loadConfig();
    }, []);

    const loadConfig = async () => {
        try {
            setLoading(true);
            const data = await fetchConfigData();
            setConfig(data);
            setLoading(false);
        } catch {
            setMessage({ type: "error", text: "Failed to load configuration." });
            setLoading(false);
        }
    };

    const handleChange = (key, value) => {
        setConfig((prev) => ({ ...prev, [key]: value }));
    };

    const handleNestedChange = (section, key, nestedKey, value) => {
        setConfig((prev) => ({
            ...prev,
            [section]: {
                ...prev[section],
                [key]: { ...prev[section][key], [nestedKey]: value },
            },
        }));
    };

    const handleArrayChange = (section, key, arrayKey, index, nestedKey, value) => {
        const updatedArray = [...config[section][key][arrayKey]];
        updatedArray[index] = { ...updatedArray[index], [nestedKey]: value };
        setConfig((prev) => ({
            ...prev,
            [section]: {
                ...prev[section],
                [key]: { ...prev[section][key], [arrayKey]: updatedArray },
            },
        }));
    };

    const handleAddRtsp = () => setAddRtspDialogOpen(true);
    const handleDeleteRtsp = (key) => {
        setRtspKeyToDelete(key);
        setDeleteRtspDialogOpen(true);
    };

    const handleAddLine = () => setAddLineDialogOpen(true);
    const handleAddStation = (lineKey) => {
        setCurrentLineKey(lineKey);
        setAddStationDialogOpen(true);
    };

    const handleAddOperation = () => setAddOperationDialogOpen(true);
    const handleAddStep = (opKey) => {
        setCurrentOperationKey(opKey);
        setAddStepDialogOpen(true);
    };

    const handleSave = async () => {
        try {
            setSaving(true);
            await updateConfigData(config);
            setMessage({ type: "success", text: "Configuration saved successfully!" });
        } catch (err) {
            console.error("Failed to save:", err);
            setMessage({ type: "error", text: "Failed to save configuration." });
        } finally {
            setSaving(false);
        }
    };

    if (loading)
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
                <CircularProgress />
            </Box>
        );
    if (!config) return <Alert severity="error">Configuration could not be loaded.</Alert>;

    return (
        <>
            <Box sx={{ p: 1 }}>
                {message && (
                    <Alert severity={message.type} sx={{ mb: 2 }}>
                        {message.text}
                    </Alert>
                )}

                {/* RTSP URLs */}
                <Card sx={{ mb: 3 }}>
                    <CardContent>
                        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
                            <Typography variant="h6">RTSP URLs</Typography>
                            <Button startIcon={<Add />} variant="contained" onClick={handleAddRtsp}>
                                Add RTSP URL
                            </Button>
                        </Stack>
                        <Grid container spacing={2}>
                            {Object.entries(config.rtsp_urls || {}).map(([key, value]) => (
                                <Grid size={{ xs: 12 }} key={key}>
                                    <Stack direction="row" spacing={1} alignItems="center">
                                        <TextField
                                            label={key}
                                            value={value}
                                            fullWidth
                                            onChange={(e) => handleChange("rtsp_urls", { ...config.rtsp_urls, [key]: e.target.value })}
                                        />
                                        <IconButton color="error" onClick={() => handleDeleteRtsp(key)}>
                                            <Delete />
                                        </IconButton>
                                    </Stack>
                                </Grid>
                            ))}
                        </Grid>
                    </CardContent>
                </Card>

                {/* Lines */}
                <Card sx={{ mb: 3 }}>
                    <CardContent>
                        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
                            <Typography variant="h6">Lines</Typography>
                            <Button startIcon={<Add />} variant="contained" onClick={handleAddLine}>
                                Add Line
                            </Button>
                        </Stack>
                        <Grid container spacing={2}>
                            {Object.entries(config.lines || {}).map(([lineKey, line]) => (
                                <Grid size={{ xs: 12 }} key={lineKey}>
                                    <Card sx={{ p: 2, mb: 2 }}>
                                        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
                                            <Typography variant="subtitle1" fontWeight={600}>
                                                {lineKey}
                                            </Typography>
                                            <IconButton
                                                color="error"
                                                onClick={() => {
                                                    setConfig((prev) => {
                                                        const updated = { ...prev };
                                                        delete updated.lines[lineKey];
                                                        return updated;
                                                    });
                                                }}
                                            >
                                                <Delete />
                                            </IconButton>
                                        </Stack>
                                        <Grid container spacing={2}>
                                            <Grid size={{ xs: 12, md: 4 }}>
                                                <TextField
                                                    label="Product Name"
                                                    value={line.product_name}
                                                    fullWidth
                                                    onChange={(e) => handleNestedChange("lines", lineKey, "product_name", e.target.value)}
                                                />
                                            </Grid>
                                            <Grid size={{ xs: 12, md: 4 }}>
                                                <TextField
                                                    label="Takt Time (seconds)"
                                                    type="number"
                                                    value={line.takt_time_seconds}
                                                    fullWidth
                                                    onChange={(e) => handleNestedChange("lines", lineKey, "takt_time_seconds", e.target.value)}
                                                />
                                            </Grid>
                                            <Grid size={{ xs: 12, md: 4 }}>
                                                <TextField
                                                    label="Yellow Time (seconds)"
                                                    type="number"
                                                    value={line.yellow_time_seconds}
                                                    fullWidth
                                                    onChange={(e) => handleNestedChange("lines", lineKey, "yellow_time_seconds", e.target.value)}
                                                />
                                            </Grid>
                                            <Grid size={{ xs: 12, md: 4 }}>
                                                <TextField
                                                    label="Red Time (seconds)"
                                                    type="number"
                                                    value={line.red_time_seconds}
                                                    fullWidth
                                                    onChange={(e) => handleNestedChange("lines", lineKey, "red_time_seconds", e.target.value)}
                                                />
                                            </Grid>
                                            {/* Shifts */}
                                            <Grid size={{ xs: 12 }}>
                                                <Typography variant="subtitle2" fontWeight={600} mb={1}>
                                                    Shifts
                                                </Typography>
                                                {line.shifts?.map((shift, shiftIndex) => (
                                                    <Card key={shiftIndex} sx={{ p: 2, mb: 2, borderLeft: "4px solid #3f51b5" }}>
                                                        <Grid container spacing={2}>
                                                            <Grid size={{ xs: 12, md: 4 }} >
                                                                <TextField
                                                                    label="Shift Name"
                                                                    value={shift.shift_name}
                                                                    fullWidth
                                                                    onChange={(e) =>
                                                                        handleArrayChange("lines", lineKey, "shifts", shiftIndex, "shift_name", e.target.value)
                                                                    }
                                                                />
                                                            </Grid>
                                                            <Grid size={{ xs: 12, md: 4 }}>
                                                                <TextField
                                                                    label="Timings"
                                                                    value={shift.timings}
                                                                    fullWidth
                                                                    onChange={(e) =>
                                                                        handleArrayChange("lines", lineKey, "shifts", shiftIndex, "timings", e.target.value)
                                                                    }
                                                                />
                                                            </Grid>
                                                            <Grid size={{ xs: 12, md: 4 }}>
                                                                <TextField
                                                                    label="Target Units"
                                                                    type="number"
                                                                    value={shift.target_units}
                                                                    fullWidth
                                                                    onChange={(e) =>
                                                                        handleArrayChange("lines", lineKey, "shifts", shiftIndex, "target_units", e.target.value)
                                                                    }
                                                                />
                                                            </Grid>
                                                        </Grid>
                                                    </Card>
                                                ))}
                                            </Grid>
                                            {/* Stations */}
                                            <Grid size={{ xs: 12 }}>
                                                <Typography variant="subtitle2" fontWeight={600} mb={1}>
                                                    Stations
                                                </Typography>
                                                <Button
                                                    startIcon={<Add />}
                                                    variant="outlined"
                                                    size="small"
                                                    onClick={() => handleAddStation(lineKey)}
                                                    sx={{ mb: 2 }}
                                                >
                                                    Add Station
                                                </Button>
                                                {Object.entries(line.stations || {}).map(([stationKey, station]) => (
                                                    <Card key={stationKey} sx={{ p: 2, mb: 2, borderLeft: "4px solid #3f51b5" }}>
                                                        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
                                                            <Typography variant="body2" fontWeight={600}>
                                                                {stationKey}
                                                            </Typography>
                                                            <IconButton
                                                                color="error"
                                                                size="small"
                                                                onClick={() => {
                                                                    setConfig((prev) => {
                                                                        const updated = { ...prev };
                                                                        delete updated.lines[lineKey].stations[stationKey];
                                                                        return updated;
                                                                    });
                                                                }}
                                                            >
                                                                <Delete />
                                                            </IconButton>
                                                        </Stack>
                                                        <Grid container spacing={2}>
                                                            <Grid size={{ xs: 12, md: 4 }}>
                                                                <TextField
                                                                    label="Camera"
                                                                    value={station.camera}
                                                                    fullWidth
                                                                    onChange={(e) =>
                                                                        handleNestedChange("lines", lineKey, `stations.${stationKey}.camera`, e.target.value)
                                                                    }
                                                                />
                                                            </Grid>
                                                            <Grid size={{ xs: 12, md: 4 }}>
                                                                <TextField
                                                                    label="Operation"
                                                                    value={station.operation}
                                                                    fullWidth
                                                                    onChange={(e) =>
                                                                        handleNestedChange("lines", lineKey, `stations.${stationKey}.operation`, e.target.value)
                                                                    }
                                                                />
                                                            </Grid>
                                                        </Grid>
                                                    </Card>
                                                ))}
                                            </Grid>
                                        </Grid>
                                    </Card>
                                </Grid>
                            ))}
                        </Grid>
                    </CardContent>
                </Card>

                {/* Operations */}
                <Card sx={{ mb: 3 }}>
                    <CardContent>
                        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
                            <Typography variant="h6">Operations</Typography>
                            <Button startIcon={<Add />} variant="contained" onClick={handleAddOperation}>
                                Add Operation
                            </Button>
                        </Stack>
                        <Grid container spacing={2}>
                            {Object.entries(config.operations || {}).map(([opKey, operation]) => (
                                <Grid size={{ xs: 12 }} key={opKey}>
                                    <Card sx={{ p: 2, mb: 2 }}>
                                        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
                                            <Typography variant="subtitle1" fontWeight={600}>
                                                {opKey}
                                            </Typography>
                                            <IconButton
                                                color="error"
                                                onClick={() => {
                                                    setConfig((prev) => {
                                                        const updated = { ...prev };
                                                        delete updated.operations[opKey];
                                                        return updated;
                                                    });
                                                }}
                                            >
                                                <Delete />
                                            </IconButton>
                                        </Stack>
                                        <Grid container spacing={2}>
                                            {/* Sequence Steps */}
                                            <Grid size={{ xs: 12 }}>
                                                <Typography variant="subtitle2" fontWeight={600} mb={1}>
                                                    Sequence Steps
                                                </Typography>
                                                <Button
                                                    startIcon={<Add />}
                                                    variant="outlined"
                                                    size="small"
                                                    onClick={() => handleAddStep(opKey)}
                                                    sx={{ mb: 2 }}
                                                >
                                                    Add Step
                                                </Button>
                                                {operation.sequence?.map((step, stepIndex) => (
                                                    <Card key={stepIndex} sx={{ p: 2, mb: 2, borderLeft: "4px solid #3f51b5" }}>
                                                        <Typography variant="body2" color="textSecondary" mb={1}>
                                                            Step {step.step}
                                                        </Typography>
                                                        <Grid container spacing={2}>
                                                            <Grid size={{ xs: 12, md: 4 }}>
                                                                <TextField
                                                                    label="Name"
                                                                    value={step.name}
                                                                    fullWidth
                                                                    onChange={(e) => {
                                                                        const updatedSequence = [...operation.sequence];
                                                                        updatedSequence[stepIndex].name = e.target.value;
                                                                        handleNestedChange("operations", opKey, "sequence", updatedSequence);
                                                                    }}
                                                                />
                                                            </Grid>
                                                            <Grid size={{ xs: 12, md: 4 }}>
                                                                <TextField
                                                                    label="Description"
                                                                    value={step.description}
                                                                    fullWidth
                                                                    onChange={(e) => {
                                                                        const updatedSequence = [...operation.sequence];
                                                                        updatedSequence[stepIndex].description = e.target.value;
                                                                        handleNestedChange("operations", opKey, "sequence", updatedSequence);
                                                                    }}
                                                                />
                                                            </Grid>
                                                            <Grid size={{ xs: 12, md: 4 }}>
                                                                <TextField
                                                                    label="Yellow Time (seconds)"
                                                                    type="number"
                                                                    value={step.yellow_time_seconds || ""}
                                                                    fullWidth
                                                                    onChange={(e) => {
                                                                        const updatedSequence = [...operation.sequence];
                                                                        updatedSequence[stepIndex].yellow_time_seconds = e.target.value;
                                                                        handleNestedChange("operations", opKey, "sequence", updatedSequence);
                                                                    }}
                                                                />
                                                            </Grid>
                                                            <Grid size={{ xs: 12, md: 4 }}>
                                                                <TextField
                                                                    label="Red Time (seconds)"
                                                                    type="number"
                                                                    value={step.red_time_seconds || ""}
                                                                    fullWidth
                                                                    onChange={(e) => {
                                                                        const updatedSequence = [...operation.sequence];
                                                                        updatedSequence[stepIndex].red_time_seconds = e.target.value;
                                                                        handleNestedChange("operations", opKey, "sequence", updatedSequence);
                                                                    }}
                                                                />
                                                            </Grid>
                                                        </Grid>
                                                    </Card>
                                                ))}
                                            </Grid>
                                        </Grid>
                                    </Card>
                                </Grid>
                            ))}
                        </Grid>
                    </CardContent>
                </Card>

                <Box display="flex" justifyContent="flex-end">
                    <Button variant="contained" color="primary" onClick={handleSave} disabled={saving}>
                        {saving ? "Saving..." : "Save Changes"}
                    </Button>
                </Box>
            </Box>

            {/* Add RTSP Dialog */}
            <Dialog open={addRtspDialogOpen} onClose={() => setAddRtspDialogOpen(false)}>
                <DialogTitle>Add New RTSP URL</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        margin="dense"
                        label="Key (e.g., cam2)"
                        fullWidth
                        value={newRtspKey}
                        onChange={(e) => setNewRtspKey(e.target.value)}
                    />
                    <TextField
                        margin="dense"
                        label="URL"
                        fullWidth
                        value={newRtspValue}
                        onChange={(e) => setNewRtspValue(e.target.value)}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setAddRtspDialogOpen(false)}>Cancel</Button>
                    <Button
                        onClick={() => {
                            if (newRtspKey.trim() && newRtspValue.trim()) {
                                setConfig((prev) => ({
                                    ...prev,
                                    rtsp_urls: { ...prev.rtsp_urls, [newRtspKey]: newRtspValue },
                                }));
                                setNewRtspKey("");
                                setNewRtspValue("");
                            }
                            setAddRtspDialogOpen(false);
                        }}
                        color="primary"
                    >
                        Add
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Delete RTSP Dialog */}
            <Dialog open={deleteRtspDialogOpen} onClose={() => setDeleteRtspDialogOpen(false)}>
                <DialogTitle>Confirm Deletion</DialogTitle>
                <DialogContent>Are you sure you want to delete {rtspKeyToDelete}?</DialogContent>
                <DialogActions>
                    <Button onClick={() => setDeleteRtspDialogOpen(false)}>Cancel</Button>
                    <Button
                        onClick={() => {
                            setConfig((prev) => {
                                const updated = { ...prev };
                                delete updated.rtsp_urls[rtspKeyToDelete];
                                return updated;
                            });
                            setDeleteRtspDialogOpen(false);
                        }}
                        color="error"
                    >
                        Delete
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Add Line Dialog */}
            <Dialog open={addLineDialogOpen} onClose={() => setAddLineDialogOpen(false)}>
                <DialogTitle>Add New Line</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        margin="dense"
                        label="Line Key (e.g., line_2)"
                        fullWidth
                        value={newLineKey}
                        onChange={(e) => setNewLineKey(e.target.value)}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setAddLineDialogOpen(false)}>Cancel</Button>
                    <Button
                        onClick={() => {
                            if (newLineKey.trim()) {
                                setConfig((prev) => ({
                                    ...prev,
                                    lines: {
                                        ...prev.lines,
                                        [newLineKey]: {
                                            product_name: "",
                                            takt_time_seconds: 0,
                                            yellow_time_seconds: 0,
                                            red_time_seconds: 0,
                                            shifts: [],
                                            stations: {},
                                        },
                                    },
                                }));
                                setNewLineKey("");
                            }
                            setAddLineDialogOpen(false);
                        }}
                        color="primary"
                    >
                        Add
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Add Station Dialog */}
            <Dialog open={addStationDialogOpen} onClose={() => setAddStationDialogOpen(false)}>
                <DialogTitle>Add New Station</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        margin="dense"
                        label="Station Key (e.g., station_4)"
                        fullWidth
                        value={newStationKey}
                        onChange={(e) => setNewStationKey(e.target.value)}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setAddStationDialogOpen(false)}>Cancel</Button>
                    <Button
                        onClick={() => {
                            if (newStationKey.trim() && currentLineKey) {
                                setConfig((prev) => ({
                                    ...prev,
                                    lines: {
                                        ...prev.lines,
                                        [currentLineKey]: {
                                            ...prev.lines[currentLineKey],
                                            stations: {
                                                ...prev.lines[currentLineKey].stations,
                                                [newStationKey]: {
                                                    camera: "",
                                                    operation: "",
                                                    expected_cycle_time: 0,
                                                },
                                            },
                                        },
                                    },
                                }));
                                setNewStationKey("");
                            }
                            setAddStationDialogOpen(false);
                        }}
                        color="primary"
                    >
                        Add
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Add Operation Dialog */}
            <Dialog open={addOperationDialogOpen} onClose={() => setAddOperationDialogOpen(false)}>
                <DialogTitle>Add New Operation</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        margin="dense"
                        label="Operation Key (e.g., new_operation)"
                        fullWidth
                        value={newOperationKey}
                        onChange={(e) => setNewOperationKey(e.target.value)}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setAddOperationDialogOpen(false)}>Cancel</Button>
                    <Button
                        onClick={() => {
                            if (newOperationKey.trim()) {
                                setConfig((prev) => ({
                                    ...prev,
                                    operations: {
                                        ...prev.operations,
                                        [newOperationKey]: {
                                            cycles: 1,
                                            roi_line_x: null,
                                            overlap_frames: 0,
                                            sequence: [],
                                        },
                                    },
                                }));
                                setNewOperationKey("");
                            }
                            setAddOperationDialogOpen(false);
                        }}
                        color="primary"
                    >
                        Add
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Add Step Dialog */}
            <Dialog open={addStepDialogOpen} onClose={() => setAddStepDialogOpen(false)}>
                <DialogTitle>Add New Step</DialogTitle>
                <DialogContent>
                    <Typography variant="body2" color="textSecondary" mb={2}>
                        Adding step to operation: {currentOperationKey}
                    </Typography>
                    <Button
                        variant="contained"
                        onClick={() => {
                            const newStep = {
                                step: config.operations[currentOperationKey].sequence.length + 1,
                                name: "",
                                description: "",
                                hand: "",
                                tool: "",
                                part: null,
                                trigger: "",
                                repeat: 1,
                                overlap_frames: 0,
                                yellow_time_seconds: 5,
                                red_time_seconds: 30,
                            };
                            setConfig((prev) => ({
                                ...prev,
                                operations: {
                                    ...prev.operations,
                                    [currentOperationKey]: {
                                        ...prev.operations[currentOperationKey],
                                        sequence: [...prev.operations[currentOperationKey].sequence, newStep],
                                    },
                                },
                            }));
                            setAddStepDialogOpen(false);
                        }}
                    >
                        Add Default Step
                    </Button>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setAddStepDialogOpen(false)}>Cancel</Button>
                </DialogActions>
            </Dialog>
        </>
    );
};

export default Settings;