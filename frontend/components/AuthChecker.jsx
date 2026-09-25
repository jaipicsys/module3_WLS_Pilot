import { useEffect } from "react";
import { useDispatch } from "react-redux";
import Cookies from "js-cookie";
import { logout } from "../store/authSlice";

const AuthChecker = () => {
    const dispatch = useDispatch();

    useEffect(() => {
        const checkTokenExpiration = () => {
            const token = Cookies.get("token");
            if (!token) {
                dispatch(logout());
            }
        };

        checkTokenExpiration(); // Check immediately on component mount
        const interval = setInterval(checkTokenExpiration, 60000); // Check every 1 minute

        return () => clearInterval(interval);
    }, [dispatch]);

    return null; // This component does not render anything
};

export default AuthChecker;
