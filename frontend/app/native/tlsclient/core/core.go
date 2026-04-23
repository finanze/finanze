// Package core contains the shared TLS client logic used by both
// the iOS c-archive (package main) and the Android gomobile bindings.
package core

import (
	"encoding/json"
	"fmt"
	"io"
	"strings"
	"sync"

	http "github.com/bogdanfinn/fhttp"
	tls_client "github.com/bogdanfinn/tls-client"
	"github.com/bogdanfinn/tls-client/profiles"
)

var sessions sync.Map

func defaultProfile() profiles.ClientProfile {
	return profiles.Firefox_135
}

func resolveProfile(name string) profiles.ClientProfile {
	switch name {
	case "safari_ios_18_0":
		return profiles.Safari_IOS_18_0
	case "safari_ios_18_5":
		return profiles.Safari_IOS_18_5
	case "chrome_133":
		return profiles.Chrome_133
	case "firefox_135":
		return profiles.Firefox_135
	default:
		return defaultProfile()
	}
}

func getOrCreateSession(sessionID string, profile string, forceHttp1 bool, disableHttp3 bool) error {
	if _, ok := sessions.Load(sessionID); ok {
		return nil
	}

	p := defaultProfile()
	if profile != "" {
		p = resolveProfile(profile)
	}

	opts := []tls_client.HttpClientOption{
		tls_client.WithClientProfile(p),
		tls_client.WithNotFollowRedirects(),
		tls_client.WithTimeoutSeconds(30),
	}
	if forceHttp1 {
		opts = append(opts, tls_client.WithForceHttp1())
	} else if disableHttp3 {
		opts = append(opts, tls_client.WithDisableHttp3())
	}

	client, err := tls_client.NewHttpClient(nil, opts...)
	if err != nil {
		return fmt.Errorf("failed to create tls client: %w", err)
	}

	sessions.Store(sessionID, client)
	return nil
}

type requestInput struct {
	SessionID    string            `json:"sessionId"`
	Profile      string            `json:"profile"`
	Method       string            `json:"method"`
	URL          string            `json:"url"`
	Headers      map[string]string `json:"headers"`
	Body         string            `json:"body"`
	ForceHttp1   bool              `json:"forceHttp1"`
	DisableHttp3 bool              `json:"disableHttp3"`
}

type responseOutput struct {
	Status  int               `json:"status"`
	Headers map[string]string `json:"headers"`
	Data    string            `json:"data"`
}

// Request performs an HTTP request with TLS fingerprint impersonation.
// Takes a JSON string with request parameters, returns a JSON string with the response.
func Request(requestJSON string) (string, error) {
	var req requestInput
	if err := json.Unmarshal([]byte(requestJSON), &req); err != nil {
		return "", fmt.Errorf("invalid request JSON: %w", err)
	}

	if req.SessionID == "" {
		req.SessionID = "default"
	}

	if err := getOrCreateSession(req.SessionID, req.Profile, req.ForceHttp1, req.DisableHttp3); err != nil {
		return "", err
	}

	val, _ := sessions.Load(req.SessionID)
	client := val.(tls_client.HttpClient)

	var bodyReader io.Reader
	if req.Body != "" {
		bodyReader = strings.NewReader(req.Body)
	}

	httpReq, err := http.NewRequest(req.Method, req.URL, bodyReader)
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	for k, v := range req.Headers {
		httpReq.Header.Set(k, v)
	}

	resp, err := client.Do(httpReq)
	if err != nil {
		return "", fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to read response: %w", err)
	}

	headers := make(map[string]string)
	for k := range resp.Header {
		headers[k] = resp.Header.Get(k)
	}

	out := responseOutput{
		Status:  resp.StatusCode,
		Headers: headers,
		Data:    string(bodyBytes),
	}

	result, err := json.Marshal(out)
	if err != nil {
		return "", fmt.Errorf("failed to marshal response: %w", err)
	}

	return string(result), nil
}

// DestroySession closes and removes a TLS client session.
func DestroySession(sessionID string) {
	if val, ok := sessions.LoadAndDelete(sessionID); ok {
		val.(tls_client.HttpClient).CloseIdleConnections()
	}
}
