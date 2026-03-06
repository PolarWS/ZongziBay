// ASSRT 字幕站 API
import request from '@/request'

/** 搜索字幕 GET /api/v1/subtitle/sub/search */
export async function assrtSearch(params: {
  q: string
  pos?: number
  cnt?: number
  is_file?: boolean
  no_muxer?: boolean
}) {
  return request<API.BaseResponseAssrtSearchResponse_>('/api/v1/subtitle/sub/search', {
    method: 'GET',
    params: {
      q: params.q,
      pos: params.pos ?? 0,
      cnt: params.cnt ?? 15,
      is_file: params.is_file ? 1 : undefined,
      no_muxer: params.no_muxer ? 1 : undefined,
    },
  })
}

/** 字幕详情（含 filelist 下载链接）GET /api/v1/subtitle/sub/detail */
export async function assrtDetail(params: { id: number }) {
  return request<API.BaseResponseAssrtSubDetail_>('/api/v1/subtitle/sub/detail', {
    method: 'GET',
    params: { id: params.id },
  })
}

/** 字幕下载并加入任务队列（HTTP 下载，由监控移动/重命名，不经过 qB）POST /api/v1/subtitle/sub/download */
export async function assrtDownload(params: {
  id: number
  file_index?: number
  target_path?: string
  file_rename?: string
  download_path?: string
}) {
  return request<API.BaseResponseAssrtDownloadResponse_>('/api/v1/subtitle/sub/download', {
    method: 'POST',
    params: {
      id: params.id,
      file_index: params.file_index,
      target_path: params.target_path,
      file_rename: params.file_rename,
      download_path: params.download_path,
    },
  })
}

/** 批量字幕下载：一次请求提交多个文件 POST /api/v1/subtitle/sub/download/batch */
export async function assrtDownloadBatch(body: {
  id: number
  target_path?: string
  download_path?: string
  items: Array<{ file_index?: number; file_rename?: string }>
}) {
  return request<API.BaseResponseAssrtDownloadBatchResponse_>('/api/v1/subtitle/sub/download/batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    data: body,
  })
}
