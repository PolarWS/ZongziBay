// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** Get System Status 检查系统初始化状态 GET /api/v1/system/status */
export async function getSystemStatusApiV1SystemStatusGet(options?: { [key: string]: any }) {
  return request<API.BaseResponse & { data?: { initialized: boolean; username: string } }>(
    "/api/v1/system/status",
    { method: "GET", ...(options || {}) }
  );
}

/** Get Env Config 获取 Docker 环境变量 GET /api/v1/system/env-config */
export async function getEnvConfigApiV1SystemEnvConfigGet(options?: { [key: string]: any }) {
  return request<API.BaseResponse & { data?: { parsed: Record<string, string>; raw: Record<string, string> } }>(
    "/api/v1/system/env-config",
    { method: "GET", ...(options || {}) }
  );
}

/** Get Existing Config 读取已有配置文件供引导页预填 GET /api/v1/system/existing-config */
export async function getExistingConfigApiV1SystemExistingConfigGet(options?: { [key: string]: any }) {
  return request<API.BaseResponse & { data?: Record<string, any> }>(
    "/api/v1/system/existing-config",
    { method: "GET", ...(options || {}) }
  );
}

/** Test Connection 测试各服务连通性 POST /api/v1/system/test-connection */
export async function testConnectionApiV1SystemTestConnectionPost(
  body: Record<string, any>,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponse & { data?: { results: Record<string, { success: boolean; message: string }>; all_success: boolean } }>(
    "/api/v1/system/test-connection",
    { method: "POST", data: body, ...(options || {}) }
  );
}

/** Setup System 一键初始化系统 POST /api/v1/system/setup */
export async function setupSystemApiV1SystemSetupPost(
  body: Record<string, any>,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponse>(
    "/api/v1/system/setup",
    { method: "POST", data: body, ...(options || {}) }
  );
}

/** Get Path Config 获取系统路径配置（下载路径、归档路径等） GET /api/v1/system/paths */
export async function getPathConfigApiV1SystemPathsGet(options?: {
  [key: string]: any;
}) {
  return request<API.BaseResponse>("/api/v1/system/paths", {
    method: "GET",
    ...(options || {}),
  });
}

/** Get Rename Templates 获取智能重命名模板 GET /api/v1/system/rename-templates */
export async function getRenameTemplatesApiV1SystemRenameTemplatesGet(options?: {
  [key: string]: any;
}) {
  return request<API.BaseResponse & { data?: { movie?: string; tv?: string; anime?: string } }>(
    "/api/v1/system/rename-templates",
    { method: "GET", ...(options || {}) }
  )
}

/** Get Trackers 获取 BT Tracker 列表 GET /api/v1/system/trackers */
export async function getTrackersApiV1SystemTrackersGet(options?: {
  [key: string]: any;
}) {
  return request<API.BaseResponse>("/api/v1/system/trackers", {
    method: "GET",
    ...(options || {}),
  });
}

/** Get Config 获取完整配置（供设置页编辑） GET /api/v1/system/config */
export async function getConfigApiV1SystemConfigGet(options?: { [key: string]: any }) {
  return request<API.BaseResponse & { data?: Record<string, any> }>("/api/v1/system/config", {
    method: "GET",
    ...(options || {}),
  });
}

/** Save Config 保存配置 PUT /api/v1/system/config */
export async function saveConfigApiV1SystemConfigPut(
  body: Record<string, any>,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponse>("/api/v1/system/config", {
    method: "PUT",
    data: body,
    ...(options || {}),
  });
}

/** Apply Default TMDB Key 使用项目提供的 TMDB 默认密钥 POST /api/v1/system/config/apply-default-tmdb-key */
export async function applyDefaultTmdbKeyApiV1SystemConfigApplyDefaultTmdbKeyPost(options?: {
  [key: string]: any;
}) {
  return request<API.BaseResponse>(
    "/api/v1/system/config/apply-default-tmdb-key",
    { method: "POST", ...(options || {}) }
  );
}

/** Apply Default ASSRT Key 使用项目提供的 ASSRT 默认密钥 POST /api/v1/system/config/apply-default-assrt-key */
export async function applyDefaultAssrtKeyApiV1SystemConfigApplyDefaultAssrtKeyPost(options?: {
  [key: string]: any;
}) {
  return request<API.BaseResponse>(
    "/api/v1/system/config/apply-default-assrt-key",
    { method: "POST", ...(options || {}) }
  );
}

/** Get Preferences 获取显示偏好 GET /api/v1/system/preferences */
export async function getPreferencesApiV1SystemPreferencesGet(options?: { [key: string]: any }) {
  return request<API.BaseResponse & { data?: { show_zongzibay_chan: boolean } }>(
    "/api/v1/system/preferences",
    { method: "GET", ...(options || {}) }
  );
}

/** Save Preferences 保存显示偏好 PUT /api/v1/system/preferences */
export async function savePreferencesApiV1SystemPreferencesPut(
  body: { show_zongzibay_chan: boolean },
  options?: { [key: string]: any }
) {
  return request<API.BaseResponse>(
    "/api/v1/system/preferences",
    { method: "PUT", data: body, ...(options || {}) }
  );
}
