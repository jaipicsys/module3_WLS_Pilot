import { Button, Container, Typography, Box } from '@mui/material';
import { useRouter } from 'next/router';

const AccessDenied = () => {
  const router = useRouter();

  const handleBackPage = () => {
    router.push('/overview');
  };

  return (
    <Container maxWidth="md" textAlign="center">
      <Box my={4}>
        <Typography variant="h4" component="h1" gutterBottom>
          Access Denied
        </Typography>
        <Typography variant="body1">
          You do not have access to this page. Please log in with the correct credentials then try again.
        </Typography>
        <Button variant="contained" color="primary" onClick={handleBackPage} sx={{ mt: 2 }}>
          Go To dashboard
        </Button>
      </Box>
    </Container>
  );
};

export default AccessDenied;