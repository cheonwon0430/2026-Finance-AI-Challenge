import { httpClient } from "@/shared/api";

export interface ChatbotRequest {
  company: string;
}

export interface ChatbotSource {
  article_id: number;
  title: string | null;
  url: string;
  site: string;
  published_on: string | null;
  role: "primary" | "related";
}

export interface ChatbotSummary {
  summary_id: number;
  title: string;
  summary: string;
  article_ids: number[];
  duplicate_group: number;
  sources: ChatbotSource[];
}

export interface ChatbotResponse {
  company: string;
  status: "ok" | "no_candidates" | "no_relevant_news" | "error";
  search_quality: "sufficient" | "insufficient" | null;
  search_quality_reason: string | null;
  summaries: ChatbotSummary[];
  sources: ChatbotSource[];
  errors: string[];
}

export const sendChatMessage = (request: ChatbotRequest) => {
  return httpClient.post<ChatbotResponse>("/chat", request);
};