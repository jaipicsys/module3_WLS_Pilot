import React, { useState } from 'react';
import {
    TextField,
    MenuItem,
    Button,
    Grid,
    Typography,
    Paper,
    Divider,
    useTheme,
    Snackbar,
    Alert
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import ClearAllIcon from '@mui/icons-material/ClearAll';
import FilterAltIcon from '@mui/icons-material/FilterAlt';
import { fetchReports } from '../../../utils/api';

const Report = () => {
    const theme = useTheme();
    const isDarkMode = theme.palette.mode === "dark";

    const [filters, setFilters] = useState({
        line_id: '',
        station_id: '',
        // shift_id: '',
        product_name: '',
        start_time: '',
        end_time: '',
        // severity: ''
    });

    const [notification, setNotification] = useState({
        open: false,
        message: '',
        severity: 'success',
    });

    const handleNotificationClose = () => {
        setNotification(prev => ({ ...prev, open: false }));
    };

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFilters(prev => ({ ...prev, [name]: value }));
    };

    const handleClear = () => {
        setFilters({
            line_id: '',
            station_id: '',
            // shift_id: '',
            product_name: '',
            start_time: '',
            end_time: '',
            // severity: '',
        });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!filters.line_id.trim()) {
            setNotification({
                open: true,
                message: "Line ID is required.",
                severity: "warning",
            });
            return;
        }

        if (
            (filters.start_time && !filters.end_time) ||
            (!filters.start_time && filters.end_time)
        ) {
            setNotification({
                open: true,
                message: "Please select both Start Time and End Time.",
                severity: "warning",
            });
            return;
        }

        try {
            const requestPayload = {
                line_id: filters.line_id,
                station_id: filters.station_id,
                // shift_id: filters.shift_id,
                product_name: filters.product_name,
                start_time: filters.start_time,
                end_time: filters.end_time,
                // severity: filters.severity,   // ✅ NEW
            };

            const { blob, contentType } = await fetchReports(requestPayload);


            // console.log(`${contentType} IS THE CURRENT FORMAT COMMING FROM BACKEND`);


            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            // ✅ Decide extension based on backend response
            let fileName = "station_report";

            if (contentType.includes("pdf")) {
                fileName += ".pdf";
            } else if (contentType.includes("csv")) {
                fileName += ".csv";
            } else {
                fileName += ".dat"; // fallback
            }
            link.setAttribute("download", fileName);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            setNotification({
                open: true,
                message: 'Report downloaded successfully!',
                severity: 'success',
            });
        } catch (err) {
            console.error(err);
            setNotification({
                open: true,
                message: 'Failed to fetch report',
                severity: 'error',
            });
        }
    };

    const isSubmitDisabled = !(
        filters.line_id ||
        filters.station_id ||
        // filters.shift_id ||
        filters.product_name ||
        filters.start_time ||
        filters.end_time
        // filters.severity
    );

    return (
        <Paper
            elevation={6}
            sx={{
                p: 4,
                maxWidth: 900,
                margin: 'auto',
                mt: 5,
                borderRadius: 3,
                bgcolor: isDarkMode ? 'background.paper' : '#ffffff',
            }}
        >

            <Typography
                variant="h6"
                sx={{
                    pb: 1,
                    fontWeight: 'bold',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    textTransform: 'uppercase'
                }}
            >
                <FilterAltIcon color="primary" />
                Station Performance Report
            </Typography>

            <Divider sx={{ mb: 2 }} />

            <form onSubmit={handleSubmit}>
                <Grid container spacing={2}>

                    <Grid size={{ xs: 12 }}>
                        <TextField
                            fullWidth
                            label="Line ID (e.g. L-01)"
                            name="line_id"
                            value={filters.line_id}
                            onChange={handleChange}
                        />
                    </Grid>

                    <Grid size={{ xs: 12 }}>
                        <TextField
                            fullWidth
                            label="Station ID (e.g. S-01)"
                            name="station_id"
                            value={filters.station_id}
                            onChange={handleChange}
                        />
                    </Grid>

                    {/* <Grid size={{ xs: 12 }}>
                        <TextField
                            fullWidth
                            label="Shift ID"
                            name="shift_id"
                            value={filters.shift_id}
                            onChange={handleChange}
                        />
                    </Grid> */}

                    <Grid size={{ xs: 12 }}>
                        <TextField
                            fullWidth
                            label="Product Name"
                            name="product_name"
                            value={filters.product_name}
                            onChange={handleChange}
                        />
                    </Grid>

                    {/* <Grid size={{ xs: 12 }}>
                        <TextField
                            fullWidth
                            select
                            label="Severity"
                            name="severity"
                            value={filters.severity}
                            onChange={handleChange}
                        >
                            <MenuItem value="">All</MenuItem>
                            <MenuItem value="RED">Critical (Red)</MenuItem>
                            <MenuItem value="YELLOW">Warning (Yellow)</MenuItem>
                        </TextField>
                    </Grid> */}

                    <Grid size={{ xs: 12 }}>
                        <TextField
                            fullWidth
                            type="datetime-local"
                            label="Start Time"
                            name="start_time"
                            value={filters.start_time}
                            onChange={handleChange}
                            InputLabelProps={{ shrink: true }}
                        />
                    </Grid>

                    <Grid size={{ xs: 12 }}>
                        <TextField
                            fullWidth
                            type="datetime-local"
                            label="End Time"
                            name="end_time"
                            value={filters.end_time}
                            onChange={handleChange}
                            InputLabelProps={{ shrink: true }}
                        />
                    </Grid>

                       {/* ADDING FORMAT OPTION  */}
                    <Grid size={{ xs: 12 }}>
                        <TextField
                            fullWidth
                            select
                            label="Report Format"
                            name="report_format"
                            value={filters.report_format}
                            onChange={handleChange}
                        >
                            <MenuItem value="pdf">
                                📄 PDF Report
                            </MenuItem>

                            <MenuItem value="csv">
                                📊 CSV Report
                            </MenuItem>
                        </TextField>
                    </Grid>

                    <Grid size={{ xs: 12 }} sx={{ mt: 3, display: 'flex', gap: 2 }}>
                        <Button
                            variant="outlined"
                            fullWidth
                            onClick={handleClear}
                            startIcon={<ClearAllIcon />}
                        >
                            Clear Filters
                        </Button>

                        <Button
                            variant="contained"
                            color="success"
                            fullWidth
                            type="submit"
                            startIcon={<DownloadIcon />}
                            disabled={isSubmitDisabled}
                        >
                            Generate Report
                        </Button>
                    </Grid>
                </Grid>
            </form>

            <Snackbar
                open={notification.open}
                autoHideDuration={4000}
                onClose={handleNotificationClose}
                anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            >
                <Alert onClose={handleNotificationClose} severity={notification.severity}>
                    {notification.message}
                </Alert>
            </Snackbar>
        </Paper>
    );
};

export default Report;