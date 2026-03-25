// Package mobile provides gomobile-compatible bindings for the TLS client.
// Used by Android via gomobile bind to produce an AAR.
package mobile

import "finanze/tlsclient/core"

// Request performs an HTTP request with TLS fingerprint impersonation.
// Takes a JSON string with request parameters, returns a JSON string with the response.
func Request(requestJSON string) (string, error) {
	return core.Request(requestJSON)
}

// DestroySession closes and removes a TLS client session.
func DestroySession(sessionID string) {
	core.DestroySession(sessionID)
}
