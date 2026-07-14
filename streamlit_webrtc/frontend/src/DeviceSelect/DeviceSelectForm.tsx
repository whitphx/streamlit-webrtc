import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Alert from "@mui/material/Alert";
import DeviceSelect, { DeviceSelectProps } from "./DeviceSelect";

export interface DeviceSelectFormProps extends DeviceSelectProps {
  onClose: () => void;
  switchError?: Error | null;
}
function DeviceSelectForm({
  onClose,
  switchError,
  ...deviceSelectProps
}: DeviceSelectFormProps) {
  return (
    <Stack spacing={2}>
      <DeviceSelect {...deviceSelectProps} />
      {switchError != null && (
        <Alert severity="error">
          {switchError.name}: {switchError.message}
        </Alert>
      )}
      <Box>
        <Button variant="contained" color="primary" onClick={onClose}>
          Done
        </Button>
      </Box>
    </Stack>
  );
}

export default DeviceSelectForm;
