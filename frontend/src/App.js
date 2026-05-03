import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";

import { AuthProvider } from "./lib/auth";
import ProtectedRoute from "./components/ProtectedRoute";

import Stage0Hook from "./pages/Stage0Hook";
import Stage1Identity from "./pages/Stage1Identity";
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
          {/* Public audit flow */}
          <Route path="/" element={<Stage0Hook />} />
          <Route path="/audit/identity" element={<Stage1Identity />} />

          {/* Return-visit auth */}
          <Route path="/login" element={<Login />} />

          {/* Deep-link short tokens */}
          <Route path="/r/:token" element={<DeepLinkResolver />} />

          {/* Protected */}
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
