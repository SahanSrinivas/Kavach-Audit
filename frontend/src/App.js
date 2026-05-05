import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";

import { AuthProvider } from "./lib/auth";
import ProtectedRoute from "./components/ProtectedRoute";

import Stage0Hook from "./pages/Stage0Hook";
import Landing from "./pages/Landing";
import Stage1Identity from "./pages/Stage1Identity";
import Stage2Family from "./pages/Stage2Family";
import Stage3Money from "./pages/Stage3Money";
import Stage4Policies from "./pages/Stage4Policies";
import Stage5Lifestyle from "./pages/Stage5Lifestyle";
import Stage6Audit from "./pages/Stage6Audit";
import Stage7Recommendations from "./pages/Stage7Recommendations";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Settings from "./pages/Settings";
import DeepLinkResolver from "./pages/DeepLinkResolver";
import NotFound from "./pages/NotFound";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="top-center" richColors closeButton />
        <Routes>
          {/* Marketing landing + audit entry */}
          <Route path="/" element={<Landing />} />
          <Route path="/audit/start" element={<Stage0Hook />} />

          {/* Audit flow */}
          <Route path="/audit/identity" element={<Stage1Identity />} />
          <Route
            path="/audit/family"
            element={
              <ProtectedRoute>
                <Stage2Family />
              </ProtectedRoute>
            }
          />
          <Route
            path="/audit/money"
            element={
              <ProtectedRoute>
                <Stage3Money />
              </ProtectedRoute>
            }
          />
          <Route
            path="/audit/policies"
            element={
              <ProtectedRoute>
                <Stage4Policies />
              </ProtectedRoute>
            }
          />
          <Route
            path="/audit/lifestyle"
            element={
              <ProtectedRoute>
                <Stage5Lifestyle />
              </ProtectedRoute>
            }
          />
          <Route
            path="/audit/report"
            element={
              <ProtectedRoute>
                <Stage6Audit />
              </ProtectedRoute>
            }
          />

          {/* Recommendations (Stage 7) */}
          <Route
            path="/recommendations"
            element={
              <ProtectedRoute>
                <Stage7Recommendations />
              </ProtectedRoute>
            }
          />

          {/* Login + deep link */}
          <Route path="/login" element={<Login />} />
          <Route path="/r/:token" element={<DeepLinkResolver />} />

          {/* Dashboard (Stage 8) */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard/settings"
            element={
              <ProtectedRoute>
                <Settings />
              </ProtectedRoute>
            }
          />

          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
