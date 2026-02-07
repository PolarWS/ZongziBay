// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** 服务健康检查 健康检查接口
返回服务运行状态 GET /api/v1/health */
export async function healthCheckApiV1HealthGet(options?: {
  [key: string]: any;
}) {
  return request<API.BaseResponse>("/api/v1/health", {
    method: "GET",
    ...(options || {}),
  });
}
