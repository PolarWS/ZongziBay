// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** 添加下载任务 添加新的下载任务 (原子性操作)
- 插入数据库
- 提交到 qBittorrent POST /api/v1/tasks/add */
export async function addTaskApiV1TasksAddPost(
  body: API.AddTaskRequest,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseInt_>("/api/v1/tasks/add", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    data: body,
    ...(options || {}),
  });
}

/** 取消任务 取消下载任务
- 仅限 downloading 状态
- 会从 qBittorrent 删除任务和文件
- 更新数据库状态为 cancelled POST /api/v1/tasks/cancel/${param0} */
export async function cancelTaskApiV1TasksCancelTaskIdPost(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.cancelTaskApiV1TasksCancelTaskIdPostParams,
  options?: { [key: string]: any }
) {
  const { task_id: param0, ...queryParams } = params;
  return request<any>(`/api/v1/tasks/cancel/${param0}`, {
    method: "POST",
    params: { ...queryParams },
    ...(options || {}),
  });
}

/** 获取任务列表 获取下载任务列表，支持分页 GET /api/v1/tasks/list */
export async function listTasksApiV1TasksListGet(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.listTasksApiV1TasksListGetParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseTaskListResponse_>("/api/v1/tasks/list", {
    method: "GET",
    params: {
      // page has a default value: 1
      page: "1",
      // page_size has a default value: 10
      page_size: "10",
      ...params,
    },
    ...(options || {}),
  });
}
