// Package main provides C-exported wrappers for the TLS client.
// Built with c-archive + clang -shared to produce a dynamic iOS framework.
package main

// #include <stdlib.h>
import "C"
import (
	"unsafe"

	"finanze/tlsclient/core"
)

//export TlsRequest
func TlsRequest(requestJSON *C.char, errOut **C.char) *C.char {
	result, err := core.Request(C.GoString(requestJSON))
	if err != nil {
		*errOut = C.CString(err.Error())
		return nil
	}
	return C.CString(result)
}

//export TlsDestroySession
func TlsDestroySession(sessionID *C.char) {
	core.DestroySession(C.GoString(sessionID))
}

//export TlsFreeString
func TlsFreeString(s *C.char) {
	C.free(unsafe.Pointer(s))
}

func main() {}
