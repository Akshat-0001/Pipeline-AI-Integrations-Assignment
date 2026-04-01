import { useState } from 'react';
import {
    Box,
    Button,
    CircularProgress
} from '@mui/material';
import axios from 'axios';

export const HubSpotIntegration = ({ user, org, integrationParams, setIntegrationParams }) => {
    const [isConnecting, setIsConnecting] = useState(false);
    const isConnected = Boolean(integrationParams?.credentials);

    const buildFormData = () => {
        const formData = new FormData();
        formData.append('user_id', user);
        formData.append('org_id', org);
        return formData;
    };

    const handleConnectClick = async () => {
        try {
            setIsConnecting(true);
            const response = await axios.post('http://localhost:8000/integrations/hubspot/authorize', buildFormData());
            const authURL = response?.data;

            const newWindow = window.open(authURL, 'HubSpot Authorization', 'width=600, height=600');

            const pollTimer = window.setInterval(() => {
                if (newWindow?.closed !== false) {
                    window.clearInterval(pollTimer);
                    handleWindowClosed();
                }
            }, 200);
        } catch (e) {
            setIsConnecting(false);
            alert(e?.response?.data?.detail);
        }
    }

    const handleWindowClosed = async () => {
        try {
            const response = await axios.post('http://localhost:8000/integrations/hubspot/credentials', buildFormData());
            const credentials = response.data;

            if (credentials) {
                setIntegrationParams(prev => ({ ...prev, credentials: credentials, type: 'HubSpot' }));
            }
            setIsConnecting(false);
        } catch (e) {
            setIsConnecting(false);
            alert(e?.response?.data?.detail);
        }
    }

    return (
        <Box sx={{mt: 2}}>
            Parameters
            <Box display='flex' alignItems='center' justifyContent='center' sx={{mt: 2}}>
                <Button
                    variant='contained'
                    onClick={handleConnectClick}
                    color={isConnected ? 'success' : 'primary'}
                    disabled={isConnecting || isConnected}
                >
                    {isConnected ? 'HubSpot Connected' : isConnecting ? <CircularProgress size={20} /> : 'Connect to HubSpot'}
                </Button>
            </Box>
        </Box>
    );
}