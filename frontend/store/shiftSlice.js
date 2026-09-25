import { createSlice } from "@reduxjs/toolkit";

const initialState = {
  selectedShift: 1,
};

const shiftSlice = createSlice({
  name: "shift",
  initialState,
  reducers: {
    setSelectedShift: (state, action) => {
      state.selectedShift = action.payload;
    },

    resetShift: (state) => {
      state.selectedShift = 1;
    },
  },
});

export const { setSelectedShift, resetShift } = shiftSlice.actions;

export default shiftSlice.reducer;