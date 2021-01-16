import React from "react";
import { render } from "@testing-library/react";
import VisibilitySwitch from "./VisibilitySwitch";

describe("VisibilitySwitch", () => {
  it("calls onVisibilityChange prop when visibility props changed", () => {
    const onVisibilityChange = jest.fn();

    const { rerender } = render(
      <VisibilitySwitch visible onVisibilityChange={onVisibilityChange} />
    );
    expect(onVisibilityChange).toHaveBeenLastCalledWith(true);

    rerender(
      <VisibilitySwitch
        visible={false}
        onVisibilityChange={onVisibilityChange}
      />
    );
    expect(onVisibilityChange).toHaveBeenLastCalledWith(false);
  });
});
