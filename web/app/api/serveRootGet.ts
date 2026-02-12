// @ts-ignore
/* eslint-disable */
import request from "@/request";

/** Serve Root GET / */
export async function serveRootGet(options?: { [key: string]: any }) {
  return request<any>("/", {
    method: "GET",
    ...(options || {}),
  });
}
