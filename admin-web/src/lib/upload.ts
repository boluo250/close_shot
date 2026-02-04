import type { UploadRequestOptions } from "element-plus";
import { api } from "./api";
import axios from "axios";

export type PresignResponse = {
  method: string;
  url: string;
  headers: Record<string, string>;
  public_url?: string | null;
  proxy_url?: string | null;
  object_key: string;
};

export async function uploadViaPresign(
  opts: UploadRequestOptions,
  { prefix = "uploads" }: { prefix?: string } = {}
): Promise<{ publicUrl: string | null; objectKey: string }> {
  const file = opts.file as File;
  const presign = await api.post<PresignResponse>("/upload/presign", {
    filename: file.name,
    content_type: file.type || undefined,
    prefix
  });

  const { method, url, headers, public_url, proxy_url, object_key } = presign.data;
  if (method.toUpperCase() !== "PUT") throw new Error("仅支持 PUT 预签名（MVP）");

  await axios.put(url, file, {
    headers: {
      ...(headers || {}),
      // 某些 S3 兼容实现对 Content-Type 敏感
      ...(file.type ? { "Content-Type": file.type } : {})
    },
    // 预签名 URL 可能较长，关闭默认 transform 避免异常
    transformRequest: [(d) => d]
  });

  const apiBase = api.defaults.baseURL || "";
  const fallback = proxy_url ? apiBase.replace(/\/$/, "") + proxy_url : null;
  return { publicUrl: public_url || fallback, objectKey: object_key };
}

