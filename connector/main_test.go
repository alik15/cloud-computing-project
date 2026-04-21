package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

// Run locally:
//   cd connector && go test -v ./...

func TestHealthHandler(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	w := httptest.NewRecorder()

	http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	}).ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200 got %d", w.Code)
	}

	var body map[string]string
	if err := json.NewDecoder(w.Body).Decode(&body); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}
	if body["status"] != "ok" {
		t.Errorf("expected status=ok got %s", body["status"])
	}
}

func TestGetEnvWithValue(t *testing.T) {
	t.Setenv("TEST_VAR", "hello")
	if got := getEnv("TEST_VAR", "default"); got != "hello" {
		t.Errorf("expected hello got %s", got)
	}
}

func TestGetEnvWithFallback(t *testing.T) {
	if got := getEnv("NONEXISTENT_VAR_XYZ", "default"); got != "default" {
		t.Errorf("expected default got %s", got)
	}
}

func TestWriteErrStatus(t *testing.T) {
	w := httptest.NewRecorder()
	writeErr(w, http.StatusBadRequest, "something went wrong")

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400 got %d", w.Code)
	}
}

func TestWriteErrBody(t *testing.T) {
	w := httptest.NewRecorder()
	writeErr(w, http.StatusBadRequest, "something went wrong")

	var body map[string]string
	json.NewDecoder(w.Body).Decode(&body)
	if body["error"] != "something went wrong" {
		t.Errorf("unexpected error message: %s", body["error"])
	}
}

func TestWriteJSONSetsContentType(t *testing.T) {
	w := httptest.NewRecorder()
	writeJSON(w, http.StatusOK, map[string]string{"key": "value"})

	ct := w.Header().Get("Content-Type")
	if ct != "application/json" {
		t.Errorf("expected application/json got %s", ct)
	}
}

func TestWriteJSONSetsStatus(t *testing.T) {
	w := httptest.NewRecorder()
	writeJSON(w, http.StatusCreated, map[string]string{"key": "value"})

	if w.Code != http.StatusCreated {
		t.Errorf("expected 201 got %d", w.Code)
	}
}

func TestGetUserIDFromHeader(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/movies", nil)
	req.Header.Set("X-User-ID", "42")

	if got := getUserID(req); got != "42" {
		t.Errorf("expected 42 got %s", got)
	}
}

func TestGetUserIDMissing(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/movies", nil)

	if got := getUserID(req); got != "" {
		t.Errorf("expected empty string got %s", got)
	}
}
