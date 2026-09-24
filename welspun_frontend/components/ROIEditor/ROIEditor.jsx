import React, { useRef, useState, useEffect } from "react";
import {
    Box,
    Button,
    Typography,
    Stack,
    ToggleButton,
    ToggleButtonGroup,
    Snackbar,
    Alert,
} from "@mui/material";
import { fetchCameraFrame } from "../../utils/api";

const ROIEditor = ({ camId, onSave }) => {
    const canvasRef = useRef(null);
    const imgRef = useRef(null);
    const [points, setPoints] = useState([]);
    const [image, setImage] = useState(null);
    const [roiType, setRoiType] = useState("roi_coords_car");
    const [snackbar, setSnackbar] = useState({
        open: false,
        severity: "info",
        message: "",
    });

    useEffect(() => {
        fetchCameraFrame(camId)
            .then((img) => setImage(img))
            .catch((err) => {
                console.error("Failed to fetch camera frame:", err);
                showSnackbar("Failed to load camera frame.", "error");
            });
    }, [camId]);

    const showSnackbar = (message, severity = "info") => {
        setSnackbar({ open: true, message, severity });
    };

    const handleCloseSnackbar = () => {
        setSnackbar((prev) => ({ ...prev, open: false }));
    };

    const handleCanvasClick = (e) => {
        const rect = canvasRef.current.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        setPoints((prev) => [...prev, [Math.round(x), Math.round(y)]]);
    };

    const handleReset = () => {
        setPoints([]);
        showSnackbar("Points reset.", "info");
    };

    const SCALE_FACTOR = 0.5;

    const handleSave = () => {
        if (points.length < 3) {
            showSnackbar("Select at least 3 points before saving ROI.", "warning");
            return;
        }

        const scaledPoints = points.map(([x, y]) => [
            Math.round(x / SCALE_FACTOR),
            Math.round(y / SCALE_FACTOR),
        ]);

        onSave(roiType, scaledPoints);
        showSnackbar(`Saved ${roiType.replaceAll("_", " ")} successfully!`, "success");
    };

    useEffect(() => {
        if (!image) return;

        const canvas = canvasRef.current;
        const img = imgRef.current;
        if (!canvas || !img) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const draw = () => {
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0);

            if (points.length > 0) {
                ctx.beginPath();
                ctx.moveTo(points[0][0], points[0][1]);
                points.forEach(([x, y]) => ctx.lineTo(x, y));
                ctx.closePath();
                ctx.strokeStyle =
                    roiType === "roi_coords_car"
                        ? "yellow"
                        : roiType === "roi_coords_bike"
                            ? "cyan"
                            : "magenta";
                ctx.lineWidth = 2;
                ctx.stroke();

                points.forEach(([x, y]) => {
                    ctx.fillStyle = "red";
                    ctx.beginPath();
                    ctx.arc(x, y, 4, 0, 2 * Math.PI);
                    ctx.fill();
                });
            }
        };

        if (img.complete) draw();
        else img.onload = draw;
    }, [points, image, roiType]);

    return (
        <Box sx={{ p: 1 }}>
            <Typography variant="h6" mb={1}>
                ROI Editor — {camId}
            </Typography>

            <Stack direction="row" spacing={2} mb={2}>
                <ToggleButtonGroup
                    color="primary"
                    value={roiType}
                    exclusive
                    onChange={(e, val) => val && setRoiType(val)}
                >
                    <ToggleButton value="roi_coords_car">Car ROI</ToggleButton>
                    <ToggleButton value="roi_coords_bike">Bike ROI</ToggleButton>
                    <ToggleButton value="ignore_roi_coords">Ignore ROI</ToggleButton>
                </ToggleButtonGroup>
            </Stack>

            {image ? (
                <Box position="relative" display="inline-block">
                    <img
                        ref={imgRef}
                        src={image}
                        alt="camera frame"
                        style={{ display: "none" }}
                    />
                    <canvas
                        ref={canvasRef}
                        style={{
                            cursor: "crosshair",
                            border: "1px solid #ccc",
                            maxWidth: "100%",
                            height: "auto",
                        }}
                        onClick={handleCanvasClick}
                    />
                </Box>
            ) : (
                <Typography>Loading frame...</Typography>
            )}

            <Stack direction="row" spacing={2} mt={2}>
                <Button variant="outlined" color="secondary" onClick={handleReset}>
                    Reset
                </Button>
                <Button variant="contained" color="primary" onClick={handleSave}>
                    Save {roiType.replaceAll("_", " ")}
                </Button>
            </Stack>

            {points.length > 0 && (
                <Typography variant="body2" mt={2}>
                    {JSON.stringify(points)}
                </Typography>
            )}

            <Snackbar
                open={snackbar.open}
                autoHideDuration={2500}
                onClose={handleCloseSnackbar}
                anchorOrigin={{ vertical: "top", horizontal: "right" }}
            >
                <Alert
                    onClose={handleCloseSnackbar}
                    severity={snackbar.severity}
                    variant="filled"
                    sx={{ width: "100%" }}
                >
                    {snackbar.message}
                </Alert>
            </Snackbar>
        </Box>
    );
};

export default ROIEditor;
