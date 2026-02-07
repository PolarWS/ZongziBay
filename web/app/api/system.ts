// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** Get Path Config 获取系统路径配置 GET /api/v1/system/paths */
export async function getPathConfigApiV1SystemPathsGet(options?: {
  [key: string]: any;
}) {
  return request<API.BaseResponse>("/api/v1/system/paths", {
    method: "GET",
    ...(options || {}),
  });
}
