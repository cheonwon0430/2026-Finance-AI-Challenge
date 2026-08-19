import { useState } from "react";

import { healthCheck } from "@/domains/system/api";

export function HealthPage() {
  const [message, setMessage] = useState("");

  const handleHealthCheck = async () => {
    const result = await healthCheck();

    setMessage(result.message);
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-100">
      <div className="flex flex-col items-center gap-6">
        <h1 className="text-2xl font-semibold text-gray-900">
          Backend Connection
        </h1>

        <button
          type="button"
          onClick={handleHealthCheck}
          className="rounded-lg bg-black px-6 py-3 text-sm font-medium text-white transition hover:bg-gray-800"
        >
          Check Backend
        </button>

        {message && (
          <div className="rounded-lg bg-white px-6 py-4 text-gray-700 shadow">
            {message}
          </div>
        )}
      </div>
    </main>
  );
}
