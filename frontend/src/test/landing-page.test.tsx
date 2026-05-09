import { render, screen } from "@testing-library/react";

import HomePage from "../app/page";

describe("landing page", () => {
  it("renders the main Stellar headline", () => {
    render(<HomePage />);

    expect(screen.getByText(/work smarter\. move faster\./i)).toBeInTheDocument();
  });

  it("renders the navigation and primary CTA", () => {
    render(<HomePage />);

    expect(screen.getByText("Stellar.ai")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /begin free trial/i })).toBeInTheDocument();
  });
});
