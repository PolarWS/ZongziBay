// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** 获取电影详情 获取指定电影的详细信息 GET /api/v1/tmdb/movie/${param0} */
export async function getMovieDetailApiV1TmdbMovieMovieIdGet(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getMovieDetailApiV1TmdbMovieMovieIdGetParams,
  options?: { [key: string]: any }
) {
  const { movie_id: param0, ...queryParams } = params;
  return request<API.BaseResponseTMDBMovie_>(`/api/v1/tmdb/movie/${param0}`, {
    method: "GET",
    params: { ...queryParams },
    ...(options || {}),
  });
}

/** 搜索电影 根据关键词搜索电影 GET /api/v1/tmdb/search/movie */
export async function searchMovieApiV1TmdbSearchMovieGet(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.searchMovieApiV1TmdbSearchMovieGetParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseTMDBMovieListResponse_>(
    "/api/v1/tmdb/search/movie",
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

/** 搜索电视剧/番剧 根据关键词搜索电视剧或番剧 GET /api/v1/tmdb/search/tv */
export async function searchTvApiV1TmdbSearchTvGet(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.searchTvApiV1TmdbSearchTvGetParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseTMDBTVListResponse_>(
    "/api/v1/tmdb/search/tv",
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

/** 搜索提示补全 根据输入返回搜索建议（标题补全） GET /api/v1/tmdb/suggestions */
export async function getSuggestionsApiV1TmdbSuggestionsGet(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getSuggestionsApiV1TmdbSuggestionsGetParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseTMDBSuggestionResponse_>(
    "/api/v1/tmdb/suggestions",
    {
      method: "GET",
      params: {
        // limit has a default value: 10
        limit: "10",
        ...params,
      },
      ...(options || {}),
    }
  );
}

/** 获取电视剧详情 获取指定电视剧的详细信息 GET /api/v1/tmdb/tv/${param0} */
export async function getTvDetailApiV1TmdbTvTvIdGet(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getTvDetailApiV1TmdbTvTvIdGetParams,
  options?: { [key: string]: any }
) {
  const { tv_id: param0, ...queryParams } = params;
  return request<API.BaseResponseTMDBTV_>(`/api/v1/tmdb/tv/${param0}`, {
    method: "GET",
    params: { ...queryParams },
    ...(options || {}),
  });
}
