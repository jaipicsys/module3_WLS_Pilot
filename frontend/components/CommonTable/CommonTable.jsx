import * as React from 'react';
import { DataGrid } from '@mui/x-data-grid';
import { Box, Modal, IconButton, Card, CardContent } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';

export default function CommonTable({
    rows, columns, onRowClick, page, setPage, pageSize, setPageSize, totalRows
}) {
    const [open, setOpen] = React.useState(false);
    const [selectedImage, setSelectedImage] = React.useState(null);

    const handleClose = () => {
        setOpen(false);
        setSelectedImage(null);
    };

    const handleRowClick = (params, event) => {
        if (event.target.tagName === 'IMG') {
            setSelectedImage(event.target.src);
            setOpen(true);
        } else {
            if (onRowClick) onRowClick(params);
        }
    };

    return (
        <Box>
            <DataGrid
                rows={rows}
                columns={columns}
                paginationModel={{ page, pageSize }}
                rowCount={totalRows}
                paginationMode="server"
                onPaginationModelChange={(model) => {
                    setPage(model.page);
                    setPageSize(model.pageSize);
                }}
                disableSelectionOnClick
                onRowClick={handleRowClick}
                columnHeaderHeight={40}
                sx={{
                    "& .MuiDataGrid-columnHeaders": { backgroundColor: "#f2f2f2" },
                    "& .MuiDataGrid-columnHeaderTitle": { fontWeight: "bold", color: "grey" },
                    "& .highlight-row": {
                        backgroundColor: "#2b2604ff",
                        "&:hover": { backgroundColor: "#2b2604ff" }
                    },
                    // Add this to remove hover effect for all rows
                    "& .MuiDataGrid-row:hover": {
                        backgroundColor: "transparent !important",
                    },
                }}
            />


            <Modal open={open} onClose={handleClose} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Card sx={{ position: 'relative', width: '600px', bgcolor: '#fff', borderRadius: 2, overflow: 'hidden', p: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                        <IconButton onClick={handleClose} sx={{ backgroundColor: 'rgba(0,0,0,0.05)', '&:hover': { backgroundColor: 'rgba(0,0,0,0.1)' } }}>
                            <CloseIcon />
                        </IconButton>
                    </Box>
                    <CardContent sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', mb: 3 }}>
                        {selectedImage && (
                            <img src={selectedImage} alt="Preview" style={{ maxHeight: '337px', objectFit: 'contain' }} />
                        )}
                    </CardContent>
                </Card>
            </Modal>
        </Box>
    );
}