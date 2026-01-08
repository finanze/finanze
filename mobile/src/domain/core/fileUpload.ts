export interface FileUpload {
  filename: string
  contentType: string
  contentLength: number
  data: Uint8Array
}
