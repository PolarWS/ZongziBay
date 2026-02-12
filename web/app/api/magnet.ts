// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** 检查 qBittorrent 连接 检查是否能成功连接到配置的 qBittorrent 服务 GET /api/v1/magnet/check */
export async function checkConnectionApiV1MagnetCheckGet(options?: {
  [key: string]: any;
}) {
  return request<API.BaseResponseBool_>("/api/v1/magnet/check", {
    method: "GET",
    ...(options || {}),
  });
}

/** 推送 Magnet 链接到 qBittorrent 下载 推送 Magnet 链接到 qBittorrent 下载（在线程池执行，不阻塞其他 API） POST /api/v1/magnet/download */
export async function downloadMagnetApiV1MagnetDownloadPost(
  body: API.MagnetDownloadRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseDict_>("/api/v1/magnet/download", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** 解析 Magnet 链接 通过 Magnet 链接获取文件列表（在线程池执行，不阻塞其他 API） POST /api/v1/magnet/parse */
export async function parseMagnetApiV1MagnetParsePost(
  body: API.MagnetRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseMagnetParseResponse_>("/api/v1/magnet/parse", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}
