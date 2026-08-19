import { apiClient } from "@/shared/api/axios";

export async function healthCheck() {
  try {
    const response = await apiClient.get("");

    return response.data;
  } catch {
    return {
      message: "Backend connection failed",
    };
  }
}
