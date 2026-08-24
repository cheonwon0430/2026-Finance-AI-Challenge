import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import {
  sendChatMessage,
  type ChatbotSummary,
} from "../api";

// 아이콘 라이브러리(lucide-react 등)를 사용 중이라면 아래 아이콘을 활용하세요.
// import { MessageCircle, X } from "lucide-react";

type ChatMessage =
  | {
      id: number;
      role: "user";
      content: string;
    }
  | {
      id: number;
      role: "assistant";
      content: string;
      summaries?: ChatbotSummary[];
    };

export function ChatbotWidget() {
  const [isOpen, setIsOpen] = useState(false);

  // 입력창 값
  const [input, setInput] = useState("");

  // 대화 내용
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // 챗봇 API
  const { mutate, isPending } = useMutation({
    mutationFn: sendChatMessage,

    onSuccess: (response) => {
      const data = response.data;

      // 뉴스가 없는 경우
      if (data.status === "no_candidates") {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            role: "assistant",
            content: `${data.company} 관련 뉴스를 찾지 못했습니다.\n\n검색 조건을 변경해서 다시 시도해보세요.`,
          },
        ]);

        return;
      }

      // 관련 뉴스가 없는 경우
      if (data.status === "no_relevant_news") {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            role: "assistant",
            content:
              `${data.company} 관련 뉴스는 찾았지만 직접적으로 관련된 뉴스를 찾지 못했습니다.` +
              (data.search_quality_reason
                ? `\n\n${data.search_quality_reason}`
                : ""),
          },
        ]);

        return;
      }

      // 백엔드에서 오류 상태를 반환한 경우
      if (data.status === "error") {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            role: "assistant",
            content:
              "뉴스를 조회하는 중 문제가 발생했습니다." +
              (data.errors.length > 0
                ? `\n\n${data.errors.join("\n")}`
                : ""),
          },
        ]);

        return;
      }

      // 정상 응답
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: "assistant",
          content: `${data.company} 관련 최신 뉴스를 정리했습니다.`,
          summaries: data.summaries,
        },
      ]);
    },

    // HTTP 500 / 502 등 요청 자체가 실패한 경우
    onError: () => {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: "assistant",
          content:
            "뉴스를 조회하는 중 문제가 발생했습니다.\n\n잠시 후 다시 시도해주세요.",
        },
      ]);
    },
  });

  const toggleChat = () => setIsOpen((prev) => !prev);

  return (
    // z-50을 주어 다른 페이지 요소들보다 항상 위에 뜨게 합니다.
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      
      {/* 1. 채팅창 영역 (열렸을 때만 렌더링) */}
      {isOpen && (
        <div className="mb-4 flex h-[1000px] w-[2000px] flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl transition-all sm:h-[550px] sm:w-[500px]">

          {/* 채팅창 헤더 */}
          <div className="flex items-center justify-between bg-blue-600 px-4 py-3 text-white">
            <h3 className="font-semibold">최근 제품 뉴스 분석 AI</h3>

            <button
              onClick={toggleChat}
              className="rounded-full p-1 transition-colors hover:bg-blue-700"
              aria-label="닫기"
            >
              {/* <X size={20} /> */}
              <span className="text-xl leading-none">×</span>
            </button>
          </div>

          {/* 대화 내용 영역 */}
          <div className="flex-1 overflow-y-auto bg-gray-50 p-4">
            {messages.length === 0 ? (
              <div className="mt-2 text-center text-sm text-gray-500">
                기업명을 입력해주세요(기업명만)
              </div>
            ) : (
              <div className="space-y-4">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={
                      message.role === "user"
                        ? "flex justify-end"
                        : "flex justify-start"
                    }
                  >
                    {/* 사용자 메시지 */}
                    {message.role === "user" && (
                      <div className="max-w-[80%] rounded-lg bg-blue-600 p-3 text-sm whitespace-pre-wrap text-white">
                        {message.content}
                      </div>
                    )}

                    {/* AI 메시지 */}
                    {message.role === "assistant" && (
                      <div className="max-w-[95%] rounded-lg bg-white p-3 text-sm text-gray-800 shadow-sm">
                        {/* AI 안내 문구 */}
                        <p className="whitespace-pre-wrap leading-6">
                          {message.content}
                        </p>

                        {/* 기사 요약 */}
                        {message.summaries &&
                          message.summaries.length > 0 && (
                            <div className="mt-4 space-y-4">
                              {message.summaries.map(
                                (summary, index) => (
                                  <article
                                    key={summary.summary_id}
                                    className="rounded-lg border border-gray-200 bg-white p-3"
                                  >
                                    {/* 기사 번호 + 제목 */}
                                    <h4 className="font-semibold leading-5">
                                      📰 {index + 1}. {summary.title}
                                    </h4>

                                    {/* 기사 요약 */}
                                    <p className="mt-3 whitespace-pre-wrap leading-6 text-gray-700">
                                      {summary.summary}
                                    </p>

                                    {/* 출처 */}
                                    {summary.sources.length > 0 && (
                                      <div className="mt-4 border-t border-gray-100 pt-3">
                                        <p className="mb-2 text-xs font-semibold text-gray-500">
                                          출처
                                        </p>

                                        <div className="space-y-2">
                                          {summary.sources.map(
                                            (source) => (
                                              <div
                                                key={`${summary.summary_id}-${source.article_id}-${source.url}`}
                                                className="text-xs"
                                              >
                                                <div className="flex items-center gap-1">
                                                  <span className="font-medium text-gray-700">
                                                    {source.role ===
                                                    "primary"
                                                      ? "주요 출처"
                                                      : "관련 출처"}
                                                  </span>

                                                  <span className="text-gray-400">
                                                    ·
                                                  </span>

                                                  <span className="text-gray-600">
                                                    {source.site}
                                                  </span>

                                                  <span className="text-gray-400">
                                                    ·
                                                  </span>

                                                  <span className="text-gray-500">
                                                    {source.published_on ??
                                                      "날짜 없음"}
                                                  </span>
                                                </div>

                                                {source.url && (
                                                  <a
                                                    href={source.url}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="mt-1 inline-block text-blue-600 hover:underline"
                                                  >
                                                    원문 보기 ↗
                                                  </a>
                                                )}
                                              </div>
                                            ),
                                          )}
                                        </div>
                                      </div>
                                    )}
                                  </article>
                                ),
                              )}
                            </div>
                          )}

                        {/* 뉴스 개수 */}
                        {message.summaries &&
                          message.summaries.length > 0 && (
                            <p className="mt-4 text-xs text-gray-500">
                              총 {message.summaries.length}건의
                              뉴스를 확인했습니다.
                            </p>
                          )}
                      </div>
                    )}
                  </div>
                ))}

                {/* API 요청 중 */}
                {isPending && (
                  <div className="flex justify-start">
                    <div className="rounded-lg bg-white p-3 text-sm text-gray-500 shadow-sm">
                      🔎 뉴스를 검색하고 있습니다...
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 입력 창 영역 */}
          <div className="border-t border-gray-200 bg-white p-3">
            <form
              onSubmit={(e) => {
                e.preventDefault();

                const company = input.trim();

                // 빈 입력 또는 요청 중이면 전송하지 않음
                if (!company || isPending) {
                  return;
                }

                // 사용자 메시지 추가
                setMessages((prev) => [
                  ...prev,
                  {
                    id: Date.now(),
                    role: "user",
                    content: company,
                  },
                ]);

                // 입력창 비우기
                setInput("");

                // 백엔드 API 호출
                mutate({
                  company,
                });
              }}
              className="flex gap-2"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="기업명을 입력하세요..."
                disabled={isPending}
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
              />

              <button
                type="submit"
                disabled={isPending || !input.trim()}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isPending ? "..." : "전송"}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* 2. 플로팅 버튼 영역 (닫혀있을 때만 렌더링) */}
      {!isOpen && (
        <button
          onClick={toggleChat}
          className="flex h-14 w-14 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg transition-transform hover:scale-105 hover:bg-blue-700 active:scale-95"
          aria-label="챗봇 열기"
        >
          {/* <MessageCircle size={28} /> */}
          <span className="text-2xl">💬</span>
        </button>
      )}
    </div>
  );
}