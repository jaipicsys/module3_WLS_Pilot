// components/HealthDrawer.js
import React, { useEffect, useState } from "react";
import {
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Typography,
  Divider,
  Box,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { fetchHealthNotifications } from "../../utils/api";

const HealthDrawer = ({ open, onClose }) => {
  const [notifications, setNotifications] = useState([]);

  useEffect(() => {
    let interval;

    const loadNotifications = async () => {
      const data = await fetchHealthNotifications();
      setNotifications(data);
    };

    if (open) {  // fetch only when open
      loadNotifications();
      interval = setInterval(loadNotifications, 10000);
    }

    return () => clearInterval(interval);
  }, [open]);

  return (
    <Drawer anchor="right" open={open} onClose={onClose}>
      <Box sx={{ width: 350, p: 2 }}>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">Health Notifications</Typography>
          <IconButton onClick={onClose}>
            <CloseIcon />
          </IconButton>
        </Box>
        <Divider sx={{ my: 1 }} />

        <List>
          {notifications.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
              No notifications yet
            </Typography>
          ) : (
            notifications.map((note) => (
              <ListItem key={note.id} divider>
                <ListItem key={note.id} divider>
                  <ListItemText
                    primary={`Camera: ${note.camera_name} | Status: ${note.status}`}
                    secondary={note.timestamp}
                  />
                </ListItem>
              </ListItem>
            ))
          )}
        </List>
      </Box>
    </Drawer>
  );
};

export default HealthDrawer;
