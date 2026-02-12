// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** Serve Spa GET /${param0} */
export async function serveSpaPathGet(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.serveSpaPathGetParams,
  options?: { [key: string]: any }
) {
  const { path: param0, ...queryParams } = params;
  return request<any>(`/${param0}`, {
    method: "GET",
    params: { ...queryParams },
    ...(options || {}),
  });
}
