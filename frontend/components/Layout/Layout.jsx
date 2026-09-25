import React from 'react';
import Grid from '@mui/material/Grid';
import { useRouter } from 'next/router';
import Header from './Header/Header';
import SideNav from './SideNav/SideNav';

export default function Layout({ children }) {
    const router = useRouter();
    const showNav = router.pathname === '/' || router.pathname === '/auth/login' || router.pathname === '/auth/register' || router.pathname === '/access-denied' || router.pathname === '/home';
    const showHeader = router.pathname === '/' || router.pathname === '/auth/login' || router.pathname === '/auth/register' || router.pathname === '/access-denied'

    const mainGridSize = {
        sm: showNav ? 12 : 12,
        md: showNav ? 12 : 9.5,
        lg: showNav ? 12 : 10.5,
    };

    const sideNavGridSize = {
        sm: showNav ? 0 : 0,
        md: showNav ? 0 : 2.5,
        lg: showNav ? 0 : 1.5,
    };

    return (
        <>
            <main>
                {/* {!showHeader &&
                    < Header />
                } */}
                <Grid container>
                   {!showNav && (
                        <Grid size={sideNavGridSize}>
                            <SideNav />
                        </Grid>
                    )}

                    <Grid sx={{ height: '100vh', overflowY: 'auto', bgcolor:'#f2f2f2' }} size={mainGridSize}>
                        {children}
                    </Grid>

                     
                </Grid>
            </main>
        </>
    );
}