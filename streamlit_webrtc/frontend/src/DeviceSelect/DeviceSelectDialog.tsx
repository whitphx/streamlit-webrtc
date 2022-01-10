import React from "react";
import Dialog from "@mui/material/Dialog";
import DeviceSelect, { DeviceSelectProps } from "./DeviceSelect";

interface DeviceSelectDialogProps extends DeviceSelectProps {
  open: boolean;
  onClose: () => void;
}
const DeviceSelectDialog: React.VFC<DeviceSelectDialogProps> = (props) => {
  const { open, onClose, ...deviceSelectProps } = props;

  return (
    <Dialog onClose={onClose} open={open}>
      <DeviceSelect {...deviceSelectProps} />
    </Dialog>
  );
};

export default DeviceSelectDialog;
