export const DownloadTaskStatusMap: Record<string, string> = {
  downloading: '下载中',
  pending_download: '待下载',
  moving: '移动中',
  seeding: '做种中',
  completed: '已完成',
  cancelled: '已取消',
  error: '错误'
}

export const FileTaskStatusMap: Record<string, string> = {
  pending: '等待中',
  processing: '处理中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消'
}

export function formatTaskStatus(status: string | undefined | null): string {
  if (!status) return '未知'
  return DownloadTaskStatusMap[status] || status
}

export function formatFileTaskStatus(status: string | undefined | null): string {
  if (!status) return '未知'
  return FileTaskStatusMap[status] || status
}
