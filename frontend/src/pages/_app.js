// pages/_app.js
import * as React from "react";
import { Provider } from "react-redux";
import { store } from "../../store/store";
import {CssBaseline } from "@mui/material";
import Layout from "../../components/Layout/Layout";
import { ColorModeProvider } from "../../context/ColorModeContext";
import Header from "../../components/Layout/Header/Header";

export default function App({ Component, pageProps }) {
  
  

  return (
    <ColorModeProvider>
      <Provider store={store}>
        <CssBaseline />
        <Layout>
          <Component {...pageProps} />
        </Layout>
      </Provider>
    </ColorModeProvider>
  );
}
