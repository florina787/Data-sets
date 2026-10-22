import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { MotionConfig } from "framer-motion";
import App from "./App";
import { AppStateProvider } from "./app/AppState";
import "./styles/index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <MotionConfig reducedMotion="user">
        <AppStateProvider>
          <App />
        </AppStateProvider>
      </MotionConfig>
    </BrowserRouter>
  </StrictMode>,
);
