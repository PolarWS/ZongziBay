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

/** Get Trackers 获取 BT Tracker 列表 GET /api/v1/system/trackers */
export async function getTrackersApiV1SystemTrackersGet(options?: {
  [key: string]: any;
}) {
  return request<API.BaseResponse>("/api/v1/system/trackers", {
    method: "GET",
    ...(options || {}),
  });
}
