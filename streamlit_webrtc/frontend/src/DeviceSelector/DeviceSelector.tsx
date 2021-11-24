import React, { useCallback } from "react";
import Select, { SelectProps } from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import { styled } from "@mui/material/styles";

const StyledSelect = styled(Select)(({ theme }) => ({
  marginTop: theme.spacing(2),
}));

interface DeviceSelecterProps {
  labelId: SelectProps["labelId"];
  value: MediaDeviceInfo | null;
  devices: MediaDeviceInfo[];
  onChange: (device: MediaDeviceInfo | null) => void;
}
const DeviceSelecter: React.VFC<DeviceSelecterProps> = ({
  labelId,
  value,
  devices,
  onChange: onChangeProp,
}) => {
  const onChange = useCallback<NonNullable<SelectProps["onChange"]>>(
    (e) => {
      const selected = devices.find((d) => d.deviceId === e.target.value);
      onChangeProp(selected || null);
    },
    [devices, onChangeProp]
  );

  if (devices.length === 0) {
    return (
      <Select value="" disabled>
        <option aria-label="None" value="" />
      </Select>
    );
  }

  if (value == null) {
    setImmediate(() => onChangeProp(devices[0]));
    return null;
  }

  return (
    <StyledSelect labelId={labelId} value={value.deviceId} onChange={onChange}>
      {devices.map((device) => (
        <MenuItem key={device.deviceId} value={device.deviceId}>
          {device.label}
        </MenuItem>
      ))}
    </StyledSelect>
  );
};

export default DeviceSelecter;
