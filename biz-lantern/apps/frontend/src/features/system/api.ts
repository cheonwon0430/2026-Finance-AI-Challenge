import { httpClient } from "@/shared/api";

export async function healthCheck() {
  try {
    const response = await httpClient.get("");

    return response.data;
  } catch {
    return {
      message: "Backend connection failed",
    };
  }
}
