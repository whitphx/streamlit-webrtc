import { describe, it } from "vitest";
import { render } from "@testing-library/react";
import Placeholder from "./Placeholder";

describe("<Placeholder />", () => {
  it("is rendered", () => {
    render(<Placeholder loading={false} />);
  });
});
