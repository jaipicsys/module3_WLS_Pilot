import { useState } from 'react';
import { Formik, Form } from 'formik';
import * as Yup from 'yup';
import {
    TextField,
    Button,
    Container,
    Typography,
    Box,
    Snackbar,
    Divider,
    IconButton,
    InputAdornment,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { useRouter } from 'next/router';
import Slide from '@mui/material/Slide';
import { Visibility, VisibilityOff } from '@mui/icons-material';
import { registerUser } from '../../utils/api';

const SlideTransition = (props) => {
    return <Slide {...props} direction="down" />;
};

const Register = () => {
    const router = useRouter();
    const [errorOpen, setErrorOpen] = useState(false);
    const [errorMessage, setErrorMessage] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);

    const handleCloseError = () => {
        setErrorOpen(false);
    };

    const handleLogin = () => {
        router.push('/auth/login');
    };

    return (
        <Container maxWidth="xs">
            <Box my={12} sx={{ borderRadius: '1rem', backgroundColor: 'white', boxShadow: '0 4px 8px 0 rgba(0, 0, 0, 0.5), 0 6px 20px 0 rgba(0, 0, 0, 0.19)' }}>
                <Formik
                    initialValues={{ name: '', email: '', password: '', confirmPassword: ''}}
                    validationSchema={Yup.object({
                        name: Yup.string().required('Required'),
                        email: Yup.string().email('Invalid email address').required('Required'),
                        password: Yup.string()
                            .min(8, 'Must be at least 8 characters')
                            .matches(/[a-z]/, 'Must contain a lowercase letter')
                            .matches(/[A-Z]/, 'Must contain an uppercase letter')
                            .matches(/[0-9]/, 'Must contain a number')
                            .matches(/[!@#$%^&*]/, 'Must contain a special character')
                            .required('Required'),
                        confirmPassword: Yup.string().required('Required').oneOf([Yup.ref('password'), null], 'Passwords must match'),
                    })}
                    onSubmit={(values) => {
                        registerUser(values)
                            .then(() => router.push("/auth/login"))
                            .catch((err) => {
                                setErrorMessage(err.message);
                                setErrorOpen(true);
                            });
                    }}
                >
                    {({ handleSubmit, handleChange, values, errors, touched }) => (
                        <Form onSubmit={handleSubmit} style={{ padding: '1rem' }}>
                            <Typography color='#1976d2' variant="h6" component="h1" align='center'>
                                Register
                            </Typography>
                            <Divider sx={{ height: '10px' }} />
                            <TextField
                                fullWidth
                                margin="normal"
                                label="Name"
                                name="name"
                                value={values.name}
                                onChange={handleChange}
                                error={touched.name && Boolean(errors.name)}
                                helperText={touched.name && errors.name}
                            />
                            <TextField
                                fullWidth
                                margin="normal"
                                label="Email"
                                name="email"
                                type="email"
                                value={values.email}
                                onChange={handleChange}
                                error={touched.email && Boolean(errors.email)}
                                helperText={touched.email && errors.email}
                            />
                            <TextField
                                fullWidth
                                margin="normal"
                                label="Password"
                                name="password"
                                type={showPassword ? 'text' : 'password'}
                                value={values.password}
                                onChange={handleChange}
                                error={touched.password && Boolean(errors.password)}
                                helperText={touched.password && errors.password}
                                slotProps={{
                                    input: {
                                        endAdornment: (
                                            <InputAdornment position="end">
                                                <IconButton
                                                    aria-label="toggle password visibility"
                                                    onClick={() => setShowPassword(!showPassword)}
                                                    edge="end"
                                                >
                                                    {showPassword ? <VisibilityOff /> : <Visibility />}
                                                </IconButton>
                                            </InputAdornment>
                                        ),
                                    },
                                }}
                            />
                            <TextField
                                fullWidth
                                margin="normal"
                                label="Confirm Password"
                                name="confirmPassword"
                                type={showConfirmPassword ? 'text' : 'password'}
                                value={values.confirmPassword}
                                onChange={handleChange}
                                error={touched.confirmPassword && Boolean(errors.confirmPassword)}
                                helperText={touched.confirmPassword && errors.confirmPassword}
                                slotProps={{
                                    input: {
                                        endAdornment: (
                                            <InputAdornment position="end">
                                                <IconButton
                                                    aria-label="toggle password visibility"
                                                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                                    edge="end"
                                                >
                                                    {showConfirmPassword ? <VisibilityOff /> : <Visibility />}
                                                </IconButton>
                                            </InputAdornment>
                                        ),
                                    },
                                }}
                            />
                            <Button type="submit" fullWidth variant="contained" color="primary">
                                Register
                            </Button>
                            <Grid container justifyContent="center" mt={2}>
                                <Button fullWidth variant='outlined' onClick={handleLogin} color="error">
                                    Login
                                </Button>
                            </Grid>
                        </Form>
                    )}
                </Formik>
            </Box>
            <Snackbar
                open={errorOpen}
                autoHideDuration={6000}
                onClose={handleCloseError}
                message={errorMessage}
                anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
                slotProps={{
                    content: {
                        style: {
                            backgroundColor: '#d32f2f',
                            color: '#fff',
                        },
                    }
                }}
                slots={{ transition: SlideTransition }}
            />
        </Container>
    );
};

export default Register;