import { useState } from "react";
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    TextField, Button, Snackbar, Alert
} from "@mui/material";
import { requestPasswordReset } from "../../utils/api";

const ForgotPasswordDialog = ({ open, onClose, onOtpSent, showMessage }) => {
    const [email, setEmail] = useState("");
    const [snackbar, setSnackbar] = useState({ open: false, message: "", severity: "success" });

    const handleSubmit = async () => {
        try {
            await requestPasswordReset(email);
            showMessage('OTP sent to your email');
            if (onOtpSent) onOtpSent(email);  // pass email back
        } catch (err) {
            showMessage(err.message || 'Failed to send reset link');
        }
    };

    return (
        <>
            <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
                <DialogTitle>Forgot Password</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        margin="dense"
                        label="Registered Email"
                        type="email"
                        fullWidth
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={onClose}>Cancel</Button>
                    <Button onClick={handleSubmit} color="primary">Send OTP</Button>
                </DialogActions>
            </Dialog>

            <Snackbar
                open={snackbar.open}
                autoHideDuration={6000}
                onClose={() => setSnackbar({ ...snackbar, open: false })}
                anchorOrigin={{ vertical: "top", horizontal: "right" }}
            >
                <Alert severity={snackbar.severity}>{snackbar.message}</Alert>
            </Snackbar>
        </>
    );
};

export default ForgotPasswordDialog;
