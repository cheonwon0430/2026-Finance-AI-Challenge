import { useState } from "react";
// 아이콘 라이브러리(lucide-react 등)를 사용 중이라면 아래 아이콘을 활용하세요.
// import { MessageCircle, X } from "lucide-react";

export function ChatbotWidget() {
  const [isOpen, setIsOpen] = useState(false);

  const toggleChat = () => setIsOpen((prev) => !prev);

  return (
    // z-50을 주어 다른 페이지 요소들보다 항상 위에 뜨게 합니다.
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      
      {/* 1. 채팅창 영역 (열렸을 때만 렌더링) */}
      {isOpen && (
        <div className="mb-4 flex h-[450px] w-[320px] flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl transition-all sm:h-[500px] sm:w-[360px]">
          
          {/* 채팅창 헤더 */}
          <div className="flex items-center justify-between bg-blue-600 px-4 py-3 text-white">
            <h3 className="font-semibold">AI 어시스턴트</h3>
            <button
              onClick={toggleChat}
              className="rounded-full p-1 transition-colors hover:bg-blue-700"
              aria-label="닫기"
            >
              {/* <X size={20} /> */}
              <span className="text-xl leading-none">×</span>
            </button>
          </div>

          {/* 대화 내용 영역 (스크롤) */}
          <div className="flex-1 overflow-y-auto bg-gray-50 p-4">
            <div className="mt-2 text-center text-sm text-gray-500">
              무엇을 도와드릴까요?
            </div>
            {/* 
              여기에 실제 메시지 말풍선들이 렌더링됩니다. 
              예시: <div className="mt-4 rounded-lg bg-blue-100 p-3">안녕하세요!</div> 
            */}
          </div>

          {/* 입력 창 영역 */}
          <div className="border-t border-gray-200 bg-white p-3">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                // TODO: 메시지 전송 로직 구현
              }}
              className="flex gap-2"
            >
              <input
                type="text"
                placeholder="메시지를 입력하세요..."
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <button
                type="submit"
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
              >
                전송
              </button>
            </form>
          </div>
        </div>
      )}

      {/* 2. 플로팅 버튼 영역 (닫혀있을 때 렌더링) */}
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