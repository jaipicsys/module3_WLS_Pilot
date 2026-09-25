import { useState } from "react";
import { useFormik } from "formik";
import * as Yup from "yup";
import { useDispatch } from "react-redux";
import { setUser } from "../../store/authSlice";
import {
  TextField,
  Button,
  Container,
  Typography,
  Box,
  IconButton,
  InputAdornment,
  Snackbar,
  Divider,
  CircularProgress,
} from "@mui/material";
import ChangePasswordDialog from "./ChangePasswordDialog";
import ForgotPasswordDialog from "./ForgotPasswordDialog";
import { Visibility, VisibilityOff } from "@mui/icons-material";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import { useRouter } from "next/router";
import Slide from "@mui/material/Slide";
import { loginUser, fetchCurrentUser } from "../../utils/api";
import ResetPasswordDialog from "./ResetPasswordDialog";
import { useTheme } from "@mui/material/styles";

const SlideTransition = (props) => <Slide {...props} direction="down" />;

const Login = () => {
  const dispatch = useDispatch();
  const router = useRouter();
  const theme = useTheme();
  const isDarkMode = theme.palette.mode === "dark";

  const [showPassword, setShowPassword] = useState(false);
  const [errorOpen, setErrorOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [forgotOpen, setForgotOpen] = useState(false);
  const [changeOpen, setChangeOpen] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetEmail, setResetEmail] = useState("");
  const [loading, setLoading] = useState(false);

  const formik = useFormik({
    initialValues: { username: "", password: "" },
    validationSchema: Yup.object({
      username: Yup.string().required("Required"),
      password: Yup.string().required("Required"),
    }),
    onSubmit: async (values) => {
      setLoading(true);
      try {
        await loginUser(values);
        const user = await fetchCurrentUser();
        dispatch(setUser(user));
        router.push("/overview");
      } catch (err) {
        setErrorMessage(err.message || "Login failed");
        setErrorOpen(true);
      } finally {
        setLoading(false);
      }
    },
  });

  const handleCloseError = () => {
    setErrorOpen(false);
  };

  return (
    <Container maxWidth="xs">
      <Box
        my={12}
        sx={{
          padding: "1rem",
          borderRadius: "1rem",
          backgroundColor: isDarkMode ? theme.palette.background.paper : "#fff",
          // boxShadow: '0 4px 8px 0 rgba(0, 0, 0, 0.5), 0 6px 20px 0 rgba(0, 0, 0, 0.19)',
          transition: "all 0.3s ease",
          border: "1px solid #cacaca",
        }}
      >
        <Box
          sx={{
            display: "flex",
            justifyContent: "center",
            bgcolor: "#000",
            borderRadius: "1rem",
            border: "2px solid #00c389",
          }}
        >
          <Box
            component="img"
            src="/logo.svg"
            alt="Logo"
            sx={{
              width: 200,
              height: 70,
              objectFit: "contain",
            }}
          />
        </Box>
        <form onSubmit={formik.handleSubmit}>
          {/* <Divider sx={{ mb: 1 }} /> */}
          <Typography
            variant="h6"
            component="h1"
            align="center"
            sx={{ fontWeight: "bolder", mt: 2, color: "#00c389" }}
            gutterBottom
          >
            LOGIN
          </Typography>
          {/* <Divider sx={{ mb: 1 }} /> */}

          <TextField
            fullWidth
            margin="normal"
            label="Username"
            name="username"
            type="text"
            value={formik.values.username}
            onChange={formik.handleChange}
            error={formik.touched.username && Boolean(formik.errors.username)}
            helperText={formik.touched.username && formik.errors.username}
            variant="outlined"
          />

          <TextField
            fullWidth
            margin="normal"
            label="Password"
            name="password"
            type={showPassword ? "text" : "password"}
            value={formik.values.password}
            onChange={formik.handleChange}
            error={formik.touched.password && Boolean(formik.errors.password)}
            helperText={formik.touched.password && formik.errors.password}
            variant="outlined"
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    onClick={() => setShowPassword(!showPassword)}
                    edge="end"
                    aria-label="toggle password visibility"
                  >
                    {showPassword ? <VisibilityOff /> : <Visibility />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />

          <Button
            type="submit"
            fullWidth
            variant="contained"
            // color="warning"
            sx={{ mt: 2, mb: 2, bgcolor: "#00c389", fontWeight: 900 }}
            disabled={loading}
          >
            {loading ? <CircularProgress size={24} color="inherit" /> : "Login"}
          </Button>

          <Box display="flex" justifyContent="space-between">
            <Button
              size="small"
              sx={{ color: "#00c389", fontWeight: 900 }}
              onClick={() => setForgotOpen(true)}
            >
              Forgot Password?
            </Button>
            <Button
              size="small"
              sx={{ color: "#00c389", fontWeight: 900 }}
              onClick={() => setChangeOpen(true)}
            >
              Change Password
            </Button>
          </Box>
        </form>
      </Box>

      <Snackbar
        open={errorOpen}
        autoHideDuration={6000}
        onClose={handleCloseError}
        message={
          <Box display="flex" alignItems="center">
            <ErrorOutlineIcon fontSize="small" sx={{ mr: 1 }} />
            {errorMessage}
          </Box>
        }
        anchorOrigin={{ vertical: "top", horizontal: "right" }}
        ContentProps={{
          sx: {
            backgroundColor: theme.palette.error.main,
            color: theme.palette.getContrastText(theme.palette.error.main),
          },
        }}
        TransitionComponent={SlideTransition}
      />

      {/* Forgot Password */}
      <ForgotPasswordDialog
        open={forgotOpen}
        onClose={() => setForgotOpen(false)}
        onOtpSent={(email) => {
          setForgotOpen(false);
          setResetEmail(email);
          setResetOpen(true);
        }}
        showMessage={(msg) => {
          setErrorMessage(msg);
          setErrorOpen(true);
        }}
      />

      {/* Reset Password */}
      <ResetPasswordDialog
        open={resetOpen}
        onClose={() => setResetOpen(false)}
        email={resetEmail}
      />

      {/* Change Password */}
      <ChangePasswordDialog
        open={changeOpen}
        onClose={() => setChangeOpen(false)}
        showMessage={(msg) => {
          setErrorMessage(msg);
          setErrorOpen(true);
        }}
      />
    </Container>
  );
};

export default Login;
