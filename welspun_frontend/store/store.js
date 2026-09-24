import { configureStore } from "@reduxjs/toolkit";
import authReducer from "./authSlice";
import productReducer from "./productSlice"
import shiftReducer from "./shiftSlice";


export const store = configureStore({
  reducer: {
    auth: authReducer,
    product: productReducer,
    shift: shiftReducer,
  },
});