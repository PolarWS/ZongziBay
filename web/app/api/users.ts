// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** 用户登录接口 用户登录并获取 Access Token

- **username**: 用户名 (从 config.yml 配置中读取)
- **password**: 密码 (从 config.yml 配置中读取) POST /api/v1/users/login */
export async function loginForAccessTokenApiV1UsersLoginPost(
  body: API.BodyLoginForAccessTokenApiV1UsersLoginPost,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseToken_>("/api/v1/users/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    data: body,
    ...(options || {}),
  });
}

/** 用户登出接口 用户登出

注意：JWT 是无状态的，服务端无法强制使 Token 失效。
通常由客户端丢弃 Token 即可。
如果需要强制失效，需配合 Redis 黑名单机制。 POST /api/v1/users/logout */
export async function logoutApiV1UsersLogoutPost(options?: {
  [key: string]: any;
}) {
  return request<API.BaseResponse>("/api/v1/users/logout", {
    method: "POST",
    ...(options || {}),
  });
}

/** 获取当前用户信息 获取当前登录用户的详细信息

需要 Header 中携带 Authorization: Bearer <token> GET /api/v1/users/me */
export async function readUsersMeApiV1UsersMeGet(options?: {
  [key: string]: any;
}) {
  return request<API.BaseResponse>("/api/v1/users/me", {
    method: "GET",
    ...(options || {}),
  });
}
