import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import ReviewSiteLoader from "./ReviewSite";
import "./review.css";
import "./styles.css";

const root = document.getElementById("root");
if (root === null) throw new Error("Missing application root");

createRoot(root).render(
  <StrictMode>
    <ReviewSiteLoader />
  </StrictMode>,
);
