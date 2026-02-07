// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** 搜索海盗湾 在海盗湾搜索种子资源。 GET /api/v1/piratebay/search */
export async function searchTorrentsApiV1PiratebaySearchGet(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.searchTorrentsApiV1PiratebaySearchGetParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseListPirateBayTorrent_>(
    "/api/v1/piratebay/search",
    {
      method: "GET",
      params: {
        ...params,
      },
      ...(options || {}),
    }
  );
}
