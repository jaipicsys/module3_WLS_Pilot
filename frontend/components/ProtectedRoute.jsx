import { useEffect, useState } from "react";
import { useSelector, useDispatch } from "react-redux";
import { useRouter } from "next/router";
import { CircularProgress, Container, Typography, Box } from "@mui/material";
import { logout, setUser } from "../store/authSlice";
import dynamic from "next/dynamic";
import { fetchCurrentUser } from "../utils/api";  // Adjust import based on your structure

const ProtectedRoute = ({ component: Component, roles }) => {
    const router = useRouter();
    const dispatch = useDispatch();
    const user = useSelector((state) => state.auth.user);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const checkAuth = async () => {
            try {
                const userData = await fetchCurrentUser();  // API call, expects HTTP-only cookie
                dispatch(setUser(userData));

                if (roles && !roles.includes(userData.role)) {
                    router.push("/access-denied");
                }
            } catch (err) {
                dispatch(logout());
                router.push("/auth/login");
            } finally {
                setLoading(false);
            }
        };

        checkAuth();
    }, [dispatch, router, roles]);

    if (loading || !user) {
        return (
            <Container maxWidth="xs">
                <Box my={4} textAlign="center">
                    <CircularProgress />
                    <Typography variant="body1">Loading...</Typography>
                </Box>
            </Container>
        );
    }

    const DynamicComponent = dynamic(() => Promise.resolve(Component), { ssr: false });

    return <DynamicComponent />;
};

export default ProtectedRoute;
