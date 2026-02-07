// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** Get Notifications GET /api/v1/notifications/ */
export async function getNotificationsApiV1NotificationsGet(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getNotificationsApiV1NotificationsGetParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseNotificationPage_>("/api/v1/notifications/", {
    method: "GET",
    params: {
      // page has a default value: 1
      page: "1",
      // page_size has a default value: 20
      page_size: "20",
      ...params,
    },
    ...(options || {}),
  });
}

/** Delete Notification DELETE /api/v1/notifications/${param0} */
export async function deleteNotificationApiV1NotificationsNotificationIdDelete(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.deleteNotificationApiV1NotificationsNotificationIdDeleteParams,
  options?: { [key: string]: any }
) {
  const { notification_id: param0, ...queryParams } = params;
  return request<API.BaseResponseBool_>(`/api/v1/notifications/${param0}`, {
    method: "DELETE",
    params: { ...queryParams },
    ...(options || {}),
  });
}

/** Mark Read PUT /api/v1/notifications/${param0}/read */
export async function markReadApiV1NotificationsNotificationIdReadPut(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.markReadApiV1NotificationsNotificationIdReadPutParams,
  options?: { [key: string]: any }
) {
  const { notification_id: param0, ...queryParams } = params;
  return request<API.BaseResponseBool_>(
    `/api/v1/notifications/${param0}/read`,
    {
      method: "PUT",
      params: { ...queryParams },
      ...(options || {}),
    }
  );
}

/** Mark All Read PUT /api/v1/notifications/read_all */
export async function markAllReadApiV1NotificationsReadAllPut(options?: {
  [key: string]: any;
}) {
  return request<API.BaseResponseInt_>("/api/v1/notifications/read_all", {
    method: "PUT",
    ...(options || {}),
  });
}

/** Get Unread Count GET /api/v1/notifications/unread_count */
export async function getUnreadCountApiV1NotificationsUnreadCountGet(options?: {
  [key: string]: any;
}) {
  return request<API.BaseResponseInt_>("/api/v1/notifications/unread_count", {
    method: "GET",
    ...(options || {}),
  });
}
