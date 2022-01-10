import React from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import DeviceSelect, { DeviceSelectProps } from "./DeviceSelect";

export interface DeviceSelectFormProps extends DeviceSelectProps {
  onClose: () => void;
}
const DeviceSelectForm: React.VFC<DeviceSelectFormProps> = ({
  onClose,
  ...deviceSelectProps
}) => {
  return (
    <Stack spacing={2}>
      <DeviceSelect {...deviceSelectProps} />
      <Box>
        <Button variant="contained" color="primary" onClick={onClose}>
          Done
        </Button>
      </Box>
    </Stack>
  );
};

export default DeviceSelectForm;
