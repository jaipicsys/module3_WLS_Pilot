// store/productSlice.js
import { createSlice } from "@reduxjs/toolkit";

const initialState = {
    products: ["K192323"], // your 3 products
    selectedProduct: "K192323", // default
};

const productSlice = createSlice({
    name: "product",
    initialState,
    reducers: {
        setSelectedProduct: (state, action) => {
            state.selectedProduct = action.payload;
        },
        setProducts: (state, action) => {
            state.products = action.payload;
        },
    },
});

export const { setSelectedProduct, setProducts } = productSlice.actions;
export default productSlice.reducer;