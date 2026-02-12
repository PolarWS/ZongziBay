// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** 动漫花园关键字搜索 调用 Anime Garden /resources，传 search、page、pageSize、fansub。 GET /api/v1/anime/search */
export async function animeGardenSearch(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.animeGardenSearchParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseAnimeGardenSearchResult_>(
    "/api/v1/anime/search",
    {
      method: "GET",
      params: {
        // page has a default value: 1
        page: "1",

        ...params,
      },
      ...(options || {}),
    }
  );
}

/** 获取所有字幕组信息 调用 Anime Garden 字幕组列表接口。 GET /api/v1/anime/teams */
export async function animeGardenTeams(options?: { [key: string]: any }) {
  return request<API.BaseResponseListAnimeGardenTeam_>("/api/v1/anime/teams", {
    method: "GET",
    ...(options || {}),
  });
}
