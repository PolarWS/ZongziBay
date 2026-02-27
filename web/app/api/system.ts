// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** Get Path Config 获取系统路径配置（下载路径、归档路径等） GET /api/v1/system/paths */
export async function getPathConfigApiV1SystemPathsGet(options?: {
  [key: string]: any;
}) {
  return request<API.BaseResponse>("/api/v1/system/paths", {
    method: "GET",
    ...(options || {}),
  });
}

/** Get Rename Templates 获取智能重命名模板 GET /api/v1/system/rename-templates */
export async function getRenameTemplatesApiV1SystemRenameTemplatesGet(options?: {
  [key: string]: any;
}) {
  return request<API.BaseResponse & { data?: { movie?: string; tv?: string; anime?: string } }>(
    "/api/v1/system/rename-templates",
    { method: "GET", ...(options || {}) }
  )
}

/** Get Trackers 获取 BT Tracker 列表 GET /api/v1/system/trackers */
export async function getTrackersApiV1SystemTrackersGet(options?: {
  [key: string]: any;
}) {
  return request<API.BaseResponse>("/api/v1/system/trackers", {
    method: "GET",
    ...(options || {}),
  });
}

/** Get Config 获取完整配置（供设置页编辑） GET /api/v1/system/config */
export async function getConfigApiV1SystemConfigGet(options?: { [key: string]: any }) {
  return request<API.BaseResponse & { data?: Record<string, any> }>("/api/v1/system/config", {
    method: "GET",
    ...(options || {}),
  });
}

/** Save Config 保存配置 PUT /api/v1/system/config */
export async function saveConfigApiV1SystemConfigPut(
  body: Record<string, any>,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponse>("/api/v1/system/config", {
    method: "PUT",
    data: body,
    ...(options || {}),
  });
}
