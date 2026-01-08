export interface DeleteTemplate {
  execute(templateId: string): Promise<void>
}
