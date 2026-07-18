// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** 每日放送（本周新番周历） 调用 Bangumi /calendar，返回按周一到周日分组的正在放送番剧。 GET /api/v1/bangumi/calendar */
export async function getBangumiCalendarApiV1BangumiCalendarGet(options?: {
  [key: string]: any;
}) {
  return request<API.BaseResponseListBangumiCalendarDay_>(
    "/api/v1/bangumi/calendar",
    {
      method: "GET",
      ...(options || {}),
    }
  );
}

/** 历史季度新番 按季度聚合 TV/WEB 动画，按首播日归到周一–周日。 GET /api/v1/bangumi/season */
export async function getBangumiSeasonApiV1BangumiSeasonGet(
  params: {
    year: number;
    /** winter | spring | summer | autumn */
    season: string;
  },
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseListBangumiCalendarDay_>(
    "/api/v1/bangumi/season",
    {
      method: "GET",
      params: { ...params },
      ...(options || {}),
    }
  );
}

/** 番剧条目详情 调用 Bangumi /v0/subjects/{id}。 GET /api/v1/bangumi/subject/{subject_id} */
export async function getBangumiSubjectApiV1BangumiSubjectGet(
  params: { subject_id: number },
  options?: { [key: string]: any }
) {
  const { subject_id, ...queryParams } = params;
  return request<API.BaseResponseBangumiSubjectDetail_>(
    `/api/v1/bangumi/subject/${subject_id}`,
    {
      method: "GET",
      params: { ...queryParams },
      ...(options || {}),
    }
  );
}
