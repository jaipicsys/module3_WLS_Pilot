
import React, { useState } from "react";

import {
    Button,
    Menu,
    MenuItem,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogContentText,
    DialogActions,
    IconButton,
    Tooltip,
     Box,
    Divider,
    Typography,
} from "@mui/material";

import ArrowDropDownIcon from "@mui/icons-material/ArrowDropDown";
import CloseIcon from "@mui/icons-material/Close";

import { useDispatch, useSelector } from "react-redux";
import { setSelectedShift } from "../../../store/shiftSlice";
import CalendarMonthOutlinedIcon from "@mui/icons-material/CalendarMonthOutlined";
import CloudDownloadOutlinedIcon from "@mui/icons-material/CloudDownloadOutlined";


const shifts = [
    {
        id: 2,
        name: "06/19/2026 (2 shift)",
    },
    {
        id: 3,
        name: "Load Default Data",
    },
];

const ShiftSelector = ({ onShiftChange }) => {
    const dispatch = useDispatch();

    const selectedShiftId = useSelector(
        (state) => state.shift.selectedShift
    );

    const selectedShift =
        shifts.find((s) => s.id === selectedShiftId) || shifts[0];

    const [anchorEl, setAnchorEl] = useState(null);
    const [pendingShift, setPendingShift] = useState(null);
    const [loadDialogOpen, setLoadDialogOpen] = useState(false);

    const open = Boolean(anchorEl);

    // Open menu
    const handleMenuOpen = (event) => {
        setAnchorEl(event.currentTarget);
    };

    // Close menu
    const handleMenuClose = () => {
        setAnchorEl(null);
    };

    // User selects an option
    const handleShiftClick = (shift) => {
        handleMenuClose();

        // Load default data
        if (shift.id === 3) {
            setLoadDialogOpen(true);
            return;
        }

        // Normal 2-shift option
        setPendingShift(shift);
    };

    // =========================================
    // 2 SHIFT DATA -> YES
    // Delete existing DB
    // =========================================
    const handleConfirmShift = () => {
        if (!pendingShift) return;

        dispatch(setSelectedShift(pendingShift.id));

        if (onShiftChange) {
            onShiftChange(
                pendingShift.id,
                true,   // deleteDb
                false   // load
            );
        }

        setPendingShift(null);
    };

    // =========================================
    // 2 SHIFT DATA -> NO
    // Keep existing DB
    // =========================================
    const handleCancelShift = () => {
        if (!pendingShift) return;

        dispatch(setSelectedShift(pendingShift.id));

        if (onShiftChange) {
            onShiftChange(
                pendingShift.id,
                false,  // deleteDb
                false   // load
            );
        }

        setPendingShift(null);
    };

    // =========================================
    // LOAD DEFAULT DATA -> YES
    // shift = 3
    // delete_db = true
    // load = true
    // =========================================
    const handleConfirmLoad = () => {
        if (onShiftChange) {
            onShiftChange(
                3,      // shift
                true,   // deleteDb
                true    // load
            );
        }

        setLoadDialogOpen(false);
    };

    // =========================================
    // LOAD DEFAULT DATA -> NO
    // No API call
    // =========================================
    const handleCancelLoad = () => {
        setLoadDialogOpen(false);
    };

    return (
        <>
            {/* ================================= */}
            {/* SHIFT SELECTOR BUTTON */}
            {/* ================================= */}
            <Tooltip
                title={selectedShift?.tooltip || ""}
                arrow
                placement="top"
            >
                <Button
                    variant="outlined"
                    color="inherit"
                    onClick={handleMenuOpen}
                    endIcon={<ArrowDropDownIcon />}
                    sx={{
                        textTransform: "none",
                        borderRadius: 2,
                        px: 2,
                        minWidth: 130,
                        // fontWeight: 600,
                    }}
                >
                    {selectedShift.name}
                </Button>
            </Tooltip>

            {/* ================================= */}
            {/* MENU */}
            {/* ================================= */}

            <Menu
                anchorEl={anchorEl}
                open={open}
                onClose={handleMenuClose}
                PaperProps={{
                    sx: {
                        mt: 1,
                        minWidth: 230,
                        borderRadius: 2,
                        border: "1px solid",
                        borderColor: "divider",
                        boxShadow:
                            "0 8px 24px rgba(0,0,0,0.12)",
                        overflow: "hidden",
                    },
                }}
            >
                {shifts.map((shift, index) => (
                    <React.Fragment key={shift.id}>
                        {index === 1 && (
                            <Divider />
                        )}

                        <MenuItem
                            onClick={() =>
                                handleShiftClick(shift)
                            }
                            sx={{
                                py: 1.3,
                                px: 1.8,
                                gap: 1.5,

                                "&:hover": {
                                    backgroundColor:
                                        "action.hover",
                                },
                            }}
                        >
                            {shift.id === 2 ? (
                                <CalendarMonthOutlinedIcon
                                    sx={{
                                        fontSize: 20,
                                        color: "primary.main",
                                    }}
                                />
                            ) : (
                                <CloudDownloadOutlinedIcon
                                    sx={{
                                        fontSize: 20,
                                        color: "success.main",
                                    }}
                                />
                            )}

                            <Box>
                                <Typography
                                    sx={{
                                        fontSize: 15,
                                        // fontWeight: 600,
                                        lineHeight: 1.3,
                                    }}
                                >
                                    {shift.name}
                                </Typography>

                                <Typography
                                    sx={{
                                        fontSize: 10,
                                        color: "text.secondary",
                                        mt: 0.3,
                                    }}
                                >
                                    {shift.id === 2
                                        ? "Shift configuration"
                                        : "Restore default data"}
                                </Typography>
                            </Box>
                        </MenuItem>
                    </React.Fragment>
                ))}
            </Menu>

            {/* ================================= */}
            {/* 2 SHIFT DATA - CONFIRMATION */}
            {/* ================================= */}
            <Dialog
                open={Boolean(pendingShift)}
                onClose={() => setPendingShift(null)}
                maxWidth="xs"
                fullWidth
            >
                <DialogTitle
                    sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                    }}
                >
                    Shift Change

                    <IconButton
                        onClick={() => setPendingShift(null)}
                    >
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>

                <DialogContent>
                    <DialogContentText>
                        Do you want to{" "}
                        <span
                            style={{
                                color: "#d32f2f",
                                fontWeight: 600,
                            }}
                        >
                            delete
                        </span>{" "}
                        existing data and continue?
                    </DialogContentText>
                </DialogContent>

                <DialogActions>
                    <Button
                        variant="outlined"
                        onClick={handleCancelShift}
                    >
                        No
                    </Button>

                    <Button
                        variant="contained"
                        onClick={handleConfirmShift}
                    >
                        <span
                            style={{
                                color: "#d32f2f",
                                fontWeight: 600,
                            }}
                        >
                            Yes
                        </span>
                    </Button>
                </DialogActions>
            </Dialog>

            {/* ================================= */}
            {/* LOAD DEFAULT DATA - CONFIRMATION */}
            {/* ================================= */}
            <Dialog
                open={loadDialogOpen}
                onClose={handleCancelLoad}
                maxWidth="xs"
                fullWidth
            >
                <DialogTitle
                    sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                    }}
                >
                    Load Data

                    <IconButton
                        onClick={handleCancelLoad}
                    >
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>

                <DialogContent>
                    <DialogContentText>
                        Do you want to continue loading data?
                    </DialogContentText>
                </DialogContent>

                <DialogActions>
                    <Button
                        variant="outlined"
                        onClick={handleCancelLoad}
                    >
                        No
                    </Button>

                    <Button
                        variant="contained"
                        onClick={handleConfirmLoad}
                    >
                        Yes
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    );
};

export default ShiftSelector;

